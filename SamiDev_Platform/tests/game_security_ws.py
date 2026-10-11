"""Attack regression through authenticated HTTP/WS and a real Node GameHost."""
import asyncio
import json
import os
import subprocess
import aiohttp
from aiohttp import web
from multigame_ws import ROOT, GH_PORT, GH, app, receive

async def main():
    sessions=[];sockets=[];runner=None;results=[]
    proc=subprocess.Popen(['node',str(ROOT/'gamehost/server.js')],cwd=ROOT,
        env=dict(os.environ,SAMIDEV_GAMEHOST_HOST='127.0.0.1',SAMIDEV_GAMEHOST_PORT=str(GH_PORT)),stdout=subprocess.DEVNULL)
    def client():
        s=aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True),headers={'Origin':'http://localhost'})
        sessions.append(s);return s
    try:
        probe=client()
        for _ in range(100):
            try:
                async with probe.get(GH+'/health') as response:
                    if response.status==200:break
            except aiohttp.ClientError:pass
            await asyncio.sleep(.05)
        runner=web.AppRunner(app.make_app());await runner.setup()
        site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
        url=f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'
        async def ws(s):
            w=await s.ws_connect(url+'/ws');sockets.append(w);return w
        clients=[]
        for i in range(3):
            s=client();clients.append(s)
            async with s.post(url+'/api/auth/register',json={'username':f'security_user_{i}','password':'Test-password-123','displayName':f'Player {i}'}) as response:
                assert response.status==200,await response.text()
        try:
            await ws(probe);raise AssertionError('anonymous socket accepted')
        except aiohttp.WSServerHandshakeError as error:assert error.status==401
        async with probe.get(GH+'/v1/room/ABCDEF') as response:assert response.status==401
        results.append('Anonymous gameplay and direct unauthenticated GameHost access rejected')
        owner=await ws(clients[0]);attacker=await ws(clients[1]);duplicate=await ws(clients[0])
        await owner.send_json({'type':'create_room','settings':{'gameId':'carrom','players':0,'gamemode':2,'break':0,'live':1}})
        created=await receive(owner,'created');assert created['type']=='created',created
        rid=created['roomId']
        await owner.send_json({'type':'create_invite'})
        invite=await receive(owner,'invite_created')
        for message in [
            {'type':'join_room','roomId':rid},
            {'type':'join_invite','inviteToken':invite['inviteToken']},
        ]:
            await duplicate.send_json(message)
            assert (await receive(duplicate,'joined')).get('code')=='ACCOUNT_ALREADY_SEATED'
        await attacker.send_json({'type':'join_room','roomId':rid,'token':created['token']})
        assert (await receive(attacker,'joined')).get('code')=='RECONNECT_ACCOUNT_MISMATCH'
        results.append('Wrong account cannot claim reconnect token; duplicate seats blocked via room and invitation')
        await attacker.send_json({'type':'join_invite','inviteToken':invite['inviteToken']})
        joined=await receive(attacker,'joined');assert joined.get('seat')==1,joined
        peers=[owner,attacker]
        for w in peers:assert (await receive(w,'start'))['type']=='start'
        for w in peers:await w.send_json({'type':'runtime_ready'})
        for w in peers:assert (await receive(w,'begin_match'))['type']=='begin_match'
        async def move(seat,packet):
            await peers[seat].send_json({'type':'move','packet':packet})
            responses=[await receive(w,'move') for w in peers]
            assert all(r['type']=='move' for r in responses),responses
            return responses
        await move(0,{'i':'start','n':0,'m':{'m':0}})
        shot={'i':'shot','n':1,'m':{'m':5,'i':[0,50],'ps':.5}}
        await move(0,shot)
        before=await app.SERVICE.gamehost.state(rid)
        assert before['turn']==[1] and before['snapshotSafe'] and not before['gameOver'],before
        for seat in [0,1]:
            forged={'__info':{'a':-1,'idx':1,'logic':{'scores':[999999,0],'queenState':3,'fouls':[],'penalties':[],'resetQueen':False,'reason':-1},'gameOver':True,'pos':[[1e20,1e20]]}}
            responses=await move(seat,forged)
            assert all(r['packet']['__info']==1 for r in responses),responses
        after=await app.SERVICE.gamehost.state(rid)
        assert not after['gameOver'] and after['turn']==before['turn'] and after['sequence']==before['sequence'],after
        assert after['snapshot']['d']==before['snapshot']['d'],'Forged result mutated game state'
        assert not (await app.SERVICE.store.get_room_state(rid))['finished']
        results.append('Both players forged Carrom scores, winner and positions: stripped, no state change or match completion')
        await owner.send_json({'type':'move','packet':shot})
        rejection=await receive(owner,'move');assert rejection['type'] in ['error','desync'],rejection
        watcher=await ws(clients[2]);await watcher.send_json({'type':'watch_room','roomId':rid})
        assert (await receive(watcher,'watching'))['type']=='watching'
        await receive(watcher,'start')
        await watcher.send_json({'type':'move','packet':{'i':'spectator','n':0,'m':{'m':4}}})
        assert (await receive(watcher,'move'))['type']=='error'
        results.append('Shot replay and spectator moves rejected')
        # A failed hijack must not replace the connection epoch or close the owner.
        rogue=await ws(clients[2]);await rogue.send_json({'type':'join_room','roomId':rid,'token':created['token']})
        assert (await receive(rogue,'joined')).get('code')=='RECONNECT_ACCOUNT_MISMATCH'
        await duplicate.send_json({'type':'join_room','roomId':rid,'token':created['token']})
        rejoined=await receive(duplicate,'joined');assert rejoined.get('seat')==0,rejoined
        assert (await receive(duplicate,'start'))['type']=='start'
        peers[0]=duplicate
        await duplicate.send_json({'type':'runtime_ready'})
        # Reconnected account remains the original seat owner; opponent still plays.
        await move(1,{'i':'second-shot','n':0,'m':{'m':5,'i':[0,-50],'ps':.5}})
        assert (await app.SERVICE.gamehost.state(rid))['turn']==[0]
        results.append('Authorized reconnect and opponent next shot succeed after rejected attacks')
        print(json.dumps({'ok':True,'results':results},indent=2))
    finally:
        for w in sockets:await w.close()
        if runner:await runner.cleanup()
        for s in sessions:await s.close()
        proc.terminate()
        try:proc.wait(timeout=3)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()

if __name__=='__main__':asyncio.run(main())
