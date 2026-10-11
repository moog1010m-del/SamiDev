"""Authenticated Crazy 8 integration using real HTTP/WebSockets and Node GameHost."""
import asyncio, json, os, subprocess
import aiohttp
from aiohttp import web
from multigame_ws import ROOT, GH_PORT, GH, app, receive
from gamehost_client import GameHostError
from game_views import client_state
from store import StoreError

async def main():
    results=[];sessions=[];sockets=[];runner=None
    proc=subprocess.Popen(['node',str(ROOT/'gamehost/server.js')],cwd=ROOT,
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
        async def ws(s):
            w=await s.ws_connect(url+'/ws');sockets.append(w);return w
        clients=[]
        for i in range(7):
            s=client();clients.append(s)
            async with s.post(url+'/api/auth/register',json={'username':f'crazy8_user_{i}','password':'Test-password-123','displayName':f'Player {i}'}) as r:assert r.status==200,await r.text()
        async with probe.get(url+'/api/games') as r:
            catalog=await r.json();assert {g['id'] for g in catalog['games']}=={'carrom','tablesoccer','crazy8','pool'}
        async with probe.get(url+'/games/crazy8/index.html') as r:assert r.status==200
        for mode,cap in enumerate([2,3,4,6,4]):
            connections=[await ws(s) for s in clients[:cap]]
            await connections[0].send_json({'type':'create_room','settings':{'gameId':'crazy8','seats':mode,'live':0,'special':0}})
            created=await receive(connections[0],'created');assert created['type']=='created',created
            rid=created['roomId'];assert created['capacity']==cap
            await connections[0].send_json({'type':'create_invite'});invite=(await receive(connections[0],'invite_created'))['inviteToken']
            for i,w in enumerate(connections[1:]):
                await w.send_json({'type':'join_invite','inviteToken':invite} if i==0 else {'type':'join_room','roomId':rid})
                assert (await receive(w,'joined'))['type']=='joined'
            def private(payload,seat):
                snap=payload['snapshot'];d=snap['d'];assert '_samidev_clientViews' not in snap and 'kc' not in d
                assert all(c==-1 for c in d['stock'])
                for s,hand in enumerate(d['hands']):
                    visible=s==seat or mode==4 and seat>=0 and s%2==seat%2
                    assert all(c>=0 for c in hand) if visible else all(c==-1 for c in hand),(seat,s,hand)
                return d
            starts=[]
            for seat,w in enumerate(connections):
                start=await receive(w,'start');assert start['type']=='start',start;private(start,seat);starts.append(start)
            assert (await app.SERVICE.gamehost.state(rid))['waitingForClients']
            for w in connections:await w.send_json({'type':'runtime_ready'})
            for w in connections:assert (await receive(w,'begin_match'))['type']=='begin_match'
            assert not (await app.SERVICE.gamehost.state(rid))['waitingForClients']
            watcher=await ws(clients[-1]);await watcher.send_json({'type':'watch_room','roomId':rid})
            assert (await receive(watcher,'watching'))['type']=='watching';private(await receive(watcher,'start'),-1)
            await watcher.send_json({'type':'move','packet':{'i':'illegal','n':0,'m':{'d':1}}})
            assert (await receive(watcher,'error'))['code']=='SPECTATOR_READ_ONLY'
            authority=await app.SERVICE.gamehost.state(rid);turn=authority['turn'][0];other=(turn+1)%cap
            await connections[other].send_json({'type':'move','packet':{'i':'wrong','n':0,'m':{'d':1}}})
            assert (await receive(connections[other],'error'))['code']=='MOVE_REJECTED'
            sequence=authority['sequence']
            async def move(seat,m):
                n=sequence[seat];await connections[seat].send_json({'type':'move','packet':{'i':f'move-{seat}-{n}','n':n,'m':m}})
                responses=[]
                for w in connections:
                    event=await receive(w,'move');assert event['type']=='move',event;responses.append(event)
                sequence[seat]+=1
                return responses
            before=authority['snapshot']['d']['hands'][turn]
            replies=await move(turn,{'d':1})
            for seat,event in enumerate(replies):
                rev=event.get('reveal',{});allowed=seat==turn or mode==4 and seat%2==turn%2
                assert allowed or not any(k in rev for k in ('d','rd','rda'))
            # Snapshot injection and reconnect preserve the server's deal and privacy.
            await connections[0].send_json({'type':'snapshot','state':{'hacked':True},'moveCount':999})
            assert (await receive(connections[0],'snapshot_ignored'))['type']=='snapshot_ignored'
            for seat,w in enumerate(connections):
                await w.send_json({'type':'resync'});state=await receive(w,'resync_state');d=private(state,seat)
                if seat==turn:assert len(d['hands'][turn])==len(before)+1
            await watcher.send_json({'type':'resync'});private(await receive(watcher,'resync_state'),-1)
            await connections[0].close();replacement=await ws(clients[0]);connections[0]=replacement
            await replacement.send_json({'type':'join_room','roomId':rid,'token':created['token']})
            assert (await receive(replacement,'joined'))['seat']==0;private(await receive(replacement,'start'),0)
            # Simulate host outage: fallback checkpoints are still seat-specific.
            real=app.SERVICE.gamehost.state
            async def unavailable(*a,**k):raise GameHostError('GAMEHOST_OFFLINE','injected outage')
            app.SERVICE.gamehost.state=unavailable
            try:
                await replacement.send_json({'type':'resync'});private(await receive(replacement,'resync_state'),0)
            finally:app.SERVICE.gamehost.state=real
            original=(await real(rid))['snapshot']['d']
            async with probe.delete(GH+'/v1/room/'+rid,headers={'X-SamiDev-Service-Key':'integration-test-key'}) as r:assert r.status==200
            restored=await app.SERVICE._ensure_authority(rid,renew=True)
            assert restored['snapshot']['d']['hands']==original['hands'] and restored['snapshot']['d']['stock']==original['stock']
            # Resign all opponents: result is finalized by GameHost.
            for seat in ([1,3] if mode==4 else list(range(1,cap))):await move(seat,{'q':1})
            assert (await real(rid))['gameOver']
            assert (await app.SERVICE.store.get_room_state(rid))['finished']
            for w in connections:await w.close()
            await watcher.close()
            results.append({'seatMode':mode,'capacity':cap,'privacy':True,'draw':True,'spectator':True,'reconnect':True,'outageFallback':True,'hostRestore':True,'resignation':True})
        try:client_state({'snapshot':{'d':{'hands':[[9],[10]]}}},{'gameId':'crazy8'},0);raise AssertionError('private state leaked')
        except StoreError as e:assert e.code=='PRIVATE_STATE_UNAVAILABLE'
        print(json.dumps({'ok':True,'authenticated':True,'results':results},indent=2))
    finally:
        for w in sockets:await w.close()
        if runner:await runner.cleanup()
        for s in sessions:await s.close()
        proc.terminate()
        try:proc.wait(timeout=3)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()
if __name__=='__main__':asyncio.run(main())
