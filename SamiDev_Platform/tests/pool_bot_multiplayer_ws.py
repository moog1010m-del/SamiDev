"""External agents fill real three/four-seat tables and make accepted physical shots."""
import asyncio,json,os,subprocess,sys,tempfile,time
from pathlib import Path
import aiohttp
from aiohttp import web
from multigame_ws import ROOT,GH_PORT,GH,app,receive
WORKER=ROOT.parent/'experiments/pool-bots/worker.py'


async def main():
    host=subprocess.Popen(['node',str(ROOT/'gamehost/server.js')],cwd=ROOT,env={**os.environ,'SAMIDEV_GAMEHOST_HOST':'127.0.0.1','SAMIDEV_GAMEHOST_PORT':str(GH_PORT)},stdout=subprocess.DEVNULL)
    runner=None;worker=None;extra_sessions=[];extra_sockets=[]
    try:
        async with aiohttp.ClientSession() as probe:
            for _ in range(100):
                try:
                    async with probe.get(GH+'/health') as response:
                        if response.status==200:break
                except aiohttp.ClientError:pass
                await asyncio.sleep(.05)
        runner=web.AppRunner(app.make_app());await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
        base='http://127.0.0.1:'+str(site._server.sockets[0].getsockname()[1]);app.ALLOWED_ORIGINS.add(base)
        p=app.SERVICE.platform;admin=await p.create_user('MultiAgentAdmin','Test-password-123',role='admin');token=await p.create_session(admin['id'])
        results=[]
        async with aiohttp.ClientSession(cookies={'samidev_session':token},headers={'Origin':base}) as control:
            for mode,capacity,human_fill in [(6,3,False),(1,4,False),(2,4,False),(4,4,False),(5,4,False),(6,3,True)]:
                suffix=str(mode)+('_human' if human_fill else '')
                cid='multi_'+suffix
                async with control.post(base+'/api/admin/communities',json={'id':cid,'name':'Multi '+str(mode)}) as response:assert response.status==200,await response.text()
                async with control.post(base+'/api/admin/bots',json={'room':cid,'addCount':capacity-1,'enabled':True}) as response:assert response.status==200
                user=await p.create_user('MultiHuman'+suffix,'Test-password-123');session=await p.create_session(user['id'])
                with tempfile.TemporaryDirectory() as directory:
                    logpath=Path(directory)/'worker.jsonl'
                    async with aiohttp.ClientSession(cookies={'samidev_session':session},headers={'Origin':base}) as human:
                        async with human.post(base+'/api/game-ticket',json={'communityId':cid}) as response:ticket=(await response.json())['ticket']
                        async with human.ws_connect(base+'/ws?ticket='+ticket) as socket:
                            await socket.send_json({'type':'create_room','settings':{'gameId':'pool','gameType':mode,'break':1,'live':1}})
                            created=await receive(socket,'created');assert created['type']=='created',created
                            rid=created['roomId'];start_time=time.monotonic()
                            with logpath.open('w') as log:
                                worker=await asyncio.create_subprocess_exec(sys.executable,str(WORKER),'--base-url',base,'--enable-play','--max-games','1','--test-time-scale','.02',env={**os.environ,'PLAZR_POOL_WORKER_ADMIN_SESSION':token},stdout=log,stderr=log)
                                if human_fill:
                                    # A real player takes the last seat after the first bot;
                                    # the next scheduled bot must never enter that match.
                                    async def wait_for_first_bot():
                                        while len((await app.SERVICE.store.get_room_state(rid))['roster'])<2:await asyncio.sleep(.02)
                                    await asyncio.wait_for(wait_for_first_bot(),15)
                                    late_user=await p.create_user('MultiLateHuman','Test-password-123');late_token=await p.create_session(late_user['id'])
                                    late=aiohttp.ClientSession(cookies={'samidev_session':late_token},headers={'Origin':base});extra_sessions.append(late)
                                    async with late.post(base+'/api/game-ticket',json={'communityId':cid}) as response:late_ticket=(await response.json())['ticket']
                                    late_socket=await late.ws_connect(base+'/ws?ticket='+late_ticket);extra_sockets.append(late_socket)
                                    await late_socket.send_json({'type':'join_room','roomId':rid});assert (await receive(late_socket,'joined'))['type']=='joined'
                                    assert (await receive(late_socket,'start'))['type']=='start';await late_socket.send_json({'type':'runtime_ready'})
                                async def read_until(kind):
                                    while True:
                                        frame=await socket.receive();assert frame.type==aiohttp.WSMsgType.TEXT,frame
                                        data=json.loads(frame.data)
                                        assert data.get('type') not in ('error','desync'),data
                                        if data.get('type')==kind:return data
                                await asyncio.wait_for(read_until('start'),30)
                                state=await app.SERVICE.store.get_room_state(rid)
                                assert state['capacity']==capacity and len(state['roster'])==capacity
                                await socket.send_json({'type':'runtime_ready'});await asyncio.wait_for(read_until('begin_match'),10)
                                moves=[]
                                if human_fill:
                                    # The last real player can own the opening turn. Do not
                                    # require a bot to play out of turn in this seat-race case.
                                    await asyncio.sleep(2.2)
                                    filled=await app.SERVICE.store.get_room_state(rid)
                                    assert filled['begun'] and len(filled['roster'])==capacity
                                    assert not (await app.SERVICE.gamehost.state(rid))['gameOver']
                                else:
                                    for _ in range(15):
                                        move=await asyncio.wait_for(read_until('move'),15);moves.append(move['packet']['m'])
                                        if move['packet']['m'].get('a')==1:break
                                    assert any(move.get('a')==1 for move in moves),moves
                                    assert sum(move.get('a')==3 for move in moves)>=3
                                worker.terminate();await asyncio.wait_for(worker.wait(),15);assert (worker.returncode in (0,1) if os.name=='nt' else worker.returncode==0);worker=None
                            events=[json.loads(line) for line in logpath.read_text().splitlines() if line.startswith('{')]
                            joins=[event for event in events if event.get('event')=='bot_joined' and event['room']==rid]
                            expected=capacity-2 if human_fill else capacity-1
                            assert len(joins)==expected,events
                            assert [event['confirmedBotJoins'] for event in joins]==list(range(1,expected+1))
                            assert not any(event.get('event')=='match_stopped' for event in events),events
                            results.append({'mode':mode,'seats':capacity,'bots':len(joins),'humanFilledLastSeat':human_fill,'acceptedShot':any(move.get('a')==1 for move in moves),'elapsedTestSeconds':round(time.monotonic()-start_time,2)})
                            print(json.dumps(results[-1]),flush=True)
        print(json.dumps({'ok':True,'cases':results,'note':'Local-only scaled waits; production timing tested separately at exact boundaries'}))
    finally:
        if worker and worker.returncode is None:worker.terminate();await worker.wait()
        for socket in extra_sockets:await socket.close()
        for session in extra_sessions:await session.close()
        if runner:await runner.cleanup()
        host.terminate()
        try:host.wait(timeout=3)
        except subprocess.TimeoutExpired:host.kill();host.wait()


if __name__=='__main__':asyncio.run(main())
