"""Real HTTP/WS: AFK final push privacy and server-owned pool cosmetics."""
import asyncio, json, os, subprocess
import aiohttp
from aiohttp import web
from multigame_ws import ROOT, GH_PORT, GH, app, receive

async def main():
    sessions=[];sockets=[];runner=None;results=[]
    proc=subprocess.Popen(['node','--require',str(ROOT/'tests/fixtures/fast_alarms.cjs'),str(ROOT/'gamehost/server.js')],cwd=ROOT,
        env=dict(os.environ,SAMIDEV_GAMEHOST_HOST='127.0.0.1',SAMIDEV_GAMEHOST_PORT=str(GH_PORT)),stdout=subprocess.DEVNULL)
    def client():
        s=aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True),headers={'Origin':'http://localhost'});sessions.append(s);return s
    try:
        probe=client()
        for _ in range(100):
            try:
                async with probe.get(GH+'/health') as r:
                    if r.status==200:break
            except aiohttp.ClientError:pass
            await asyncio.sleep(.05)
        runner=web.AppRunner(app.make_app());await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
        url=f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'
        clients=[client() for _ in range(3)]
        for i,s in enumerate(clients):
            async with s.post(url+'/api/auth/register',json={'username':f'turn_user_{i}','password':'Test-password-123','displayName':f'Player {i}'}) as r:assert r.status==200,await r.text()
        async with clients[0].post(url+'/api/store/equip',json={'itemId':'pool_emerald'}) as r:assert r.status==200
        async def ws(s):
            w=await s.ws_connect(url+'/ws');sockets.append(w);return w
        for game in ['crazy8','pool']:
            seats=[await ws(s) for s in clients[:2]]
            settings={'gameId':game,'live':1,**({'seats':0,'special':0} if game=='crazy8' else {'gameType':0,'break':0,'trickShots':0})}
            await seats[0].send_json({'type':'create_room','settings':settings});rid=(await receive(seats[0],'created'))['roomId']
            await seats[1].send_json({'type':'join_room','roomId':rid});assert (await receive(seats[1],'joined'))['type']=='joined'
            starts=[await receive(w,'start') for w in seats]
            if game=='pool':
                for start in starts:
                    assert start['cosmetics']=={'0':{'pool_theme':'pool_emerald'},'1':{'pool_theme':'pool_midnight'}},start.get('cosmetics')
                # Payload cannot equip or impersonate another account.
                await seats[1].send_json({'type':'refresh_cosmetics','cosmetics':{'0':{'pool_theme':'https://bad.invalid/theme'}}})
                for w in seats:
                    state=await receive(w,'room_state')
                    while state.get('cosmetics',{}).get('0',{}).get('pool_theme')!='pool_emerald':state=await receive(w,'room_state')
                    assert not any(k in state for k in ['inventory','ledger','coins'])
            for w in seats:await w.send_json({'type':'runtime_ready'})
            for w in seats:assert (await receive(w,'begin_match'))['type']=='begin_match'
            watcher=await ws(clients[2]);await watcher.send_json({'type':'watch_room','roomId':rid})
            assert (await receive(watcher,'watching'))['type']=='watching';await receive(watcher,'start')
            if game=='pool':
                await seats[0].send_json({'type':'move','packet':{'i':'ready','n':0,'m':{'__ready':1}}})
                for w in seats:assert (await receive(w,'move'))['type']=='move'
            # No resync command, player move or reload after this point.
            for seat,w in enumerate([*seats,watcher]):
                final=await receive(w,'resync_state');assert final.get('reason')=='game_finished' and final['gameOver'],final
                assert final['turn']==[] and final['history']==[]
                if game=='crazy8':
                    snap=final['snapshot'];assert '_samidev_clientViews' not in snap and 'kc' not in snap['d']
                    assert all(c==-1 for c in snap['d']['stock'])
                    for hand_seat,hand in enumerate(snap['d']['hands']):
                        if hand_seat!=seat:assert all(c==-1 for c in hand),'private cards leaked in terminal push'
                    assert sum(final['snapshot']['am'])==2 if 'am' in final['snapshot'] else final['snapshot']['d']['won']==-2
            assert (await app.SERVICE.store.get_room_state(rid))['finished']
            for w in [*seats,watcher]:await w.close()
            results.append({'game':game,'finalPushWithoutInput':True,'spectatorFinalPush':True,'privateHands':game=='crazy8','trustedCosmetics':game=='pool'})
        print(json.dumps({'ok':True,'results':results},indent=2))
    finally:
        for w in sockets:await w.close()
        if runner:await runner.cleanup()
        for s in sessions:await s.close()
        proc.terminate()
        try:proc.wait(timeout=3)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()
if __name__=='__main__':asyncio.run(main())
