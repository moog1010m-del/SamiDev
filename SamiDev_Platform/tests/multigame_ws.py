"""Real HTTP/WebSocket integration against a temporary memory backend and Node host."""
import asyncio, json, os, socket, subprocess, sys, tempfile
from pathlib import Path
import aiohttp
from aiohttp import web
ROOT=Path(__file__).resolve().parents[1]
def port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0)); return s.getsockname()[1]
GH_PORT=port(); GH=f'http://127.0.0.1:{GH_PORT}'
os.environ.update(SAMIDEV_STORE='memory', SAMIDEV_REQUIRE_GAME_AUTH='1', SAMIDEV_GAMEHOST_URL=GH,
    SAMIDEV_GAMEHOST_SERVICE_KEY='integration-test-key', SAMIDEV_ALLOWED_ORIGINS='http://localhost')
sys.path.insert(0,str(ROOT/'backend'))
import app
from gamehost_client import GameHostError
async def receive(ws,kind):
    async def wait():
        while True:
            raw=await ws.receive()
            assert raw.type==aiohttp.WSMsgType.TEXT, raw
            data=json.loads(raw.data)
            if data.get('type') in (kind,'error','desync'): return data
    return await asyncio.wait_for(wait(),8)
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
                    if r.status==200: break
            except aiohttp.ClientError: pass
            await asyncio.sleep(.05)
        runner=web.AppRunner(app.make_app());await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
        url=f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'
        async def req(s,path,body=None):
            async with s.request('GET' if body is None else 'POST',url+path,json=body) as r: return r.status,await r.json()
        async def ws(s):
            w=await s.ws_connect(url+'/ws');sockets.append(w);return w
        users=[]; clients=[]
        for i in range(5):
            s=client();clients.append(s)
            status,d=await req(s,'/api/auth/register',{'username':f'multi_user_{i}','password':'Test-password-123','displayName':f'Player {i}'})
            assert status==200,d;users.append(d['user'])
        assert (await req(probe,'/api/auth/login',{'username':'multi_user_0','password':'wrong'}))[0]==401
        assert (await req(clients[0],'/api/auth/login',{'username':'multi_user_0','password':'Test-password-123'}))[0]==200
        try: await ws(probe);raise AssertionError('anonymous WebSocket accepted')
        except aiohttp.WSServerHandshakeError as e: assert e.status==401
        status,catalog=await req(probe,'/api/games');assert status==200 and len(catalog['games'])==4,catalog
        results.append('shared registration/login; anonymous socket rejected; both games catalogued')
        rooms=[]
        for game,players,live in [('carrom',0,1),('tablesoccer',0,0),('tablesoccer',1,1)]:
            cap=4 if players else 2
            connections=[await ws(s) for s in clients[:cap]]
            await connections[0].send_json({'type':'create_room','settings':{'gameId':game,'players':players,'live':live,'gamemode':0,'break':0,'goalsToWin':0,'passes':1}})
            created=await receive(connections[0],'created'); assert created['type']=='created',created
            rid=created['roomId'];assert created['settings']['gameId']==game
            invite_token=None
            if game=='tablesoccer' and cap==2:
                await connections[0].send_json({'type':'create_invite'})
                invite_token=(await receive(connections[0],'invite_created'))['inviteToken']
            for w in connections[1:]:
                await w.send_json({'type':'join_invite','inviteToken':invite_token} if invite_token else {'type':'join_room','roomId':rid})
                assert (await receive(w,'joined'))['type']=='joined'
            if invite_token:
                replay=await ws(clients[4]);await replay.send_json({'type':'join_invite','inviteToken':invite_token})
                assert (await receive(replay,'joined')).get('code')=='INVITE_INVALID'
                results.append('Table Soccer invite accepted once; replay rejected')
            for w in connections: assert (await receive(w,'start'))['type']=='start'
            if game=='carrom':
                real=app.SERVICE.gamehost.ensure_room
                async def fail(*a,**k):raise GameHostError('GAMEHOST_OFFLINE','injected startup failure')
                app.SERVICE.gamehost.ensure_room=fail
                try:
                    await connections[0].send_json({'type':'runtime_ready'})
                    assert (await receive(connections[0],'error'))['type']=='error'
                    assert not (await app.SERVICE.store.get_room_state(rid))['begun']
                finally:app.SERVICE.gamehost.ensure_room=real
                results.append('transient startup failure leaves begun=false and ready retry succeeds')
            for w in connections: await w.send_json({'type':'runtime_ready'})
            for w in connections: assert (await receive(w,'begin_match'))['type']=='begin_match'
            sequence=[0]*cap
            async def move(seat,m,expected='move'):
                n=sequence[seat]
                await connections[seat].send_json({'type':'move','packet':{'i':f'{game}-{seat}-{n}','n':n,'m':m}})
                response=await receive(connections[seat],expected)
                assert response['type']==expected,response
                if expected=='move':
                    sequence[seat]+=1
                    for i,w in enumerate(connections):
                        if i!=seat:assert (await receive(w,'move'))['type']=='move'
                return response
            if game=='carrom':
                await move(0,{'m':0});await move(1,{'m':3},'error');await move(0,{'m':6,'ps':.5})
            else:
                await move(0,{'a':5,'team':'Red.c.h'});await move(2 if players else 1,{'a':5,'team':'Blue.c.h'})
                for i in range(cap):await move(i,{'__ready':1})
                if live==0:await move(0,{'a':0,'id':100,'impulse':[100,0]})
                else:
                    for seat,id in [(0,100),(1,101),(2,150),(3,151)]:await move(seat,{'a':1,'id':id,'impulse':[100,0]})
            authority=await app.SERVICE.gamehost.state(rid)
            assert authority['gameId']==game and authority['sequence']==sequence,authority
            watcher=await ws(clients[4]);await watcher.send_json({'type':'watch_room','roomId':rid})
            assert (await receive(watcher,'watching'))['type']=='watching'
            start=await receive(watcher,'start');assert start['settings']['gameId']==game
            if game=='tablesoccer':assert start['snapshot'] and start['snapshot']['n']==sequence
            await connections[0].close();replacement=await ws(clients[0]);connections[0]=replacement
            await replacement.send_json({'type':'join_room','roomId':rid,'token':created['token']})
            joined=await receive(replacement,'joined');assert joined['seat']==0 and joined['settings']['gameId']==game
            assert (await receive(replacement,'start'))['type']=='start'
            if game=='tablesoccer':
                async with probe.delete(GH+'/v1/room/'+rid,headers={'X-SamiDev-Service-Key':'integration-test-key'}) as r:assert r.status==200
                restored=await app.SERVICE._ensure_authority(rid,renew=True)
                assert restored['sequence']==sequence,(restored,sequence)
            await move(2 if players else 1,{'a':3} if game=='tablesoccer' else {'m':4})
            if players:await move(3,{'a':3})
            authority=await app.SERVICE.gamehost.state(rid);assert authority['gameOver']
            rooms.append(rid);results.append(f'{game} players={cap} live={live}: start, moves, spectator, reconnect, resignation'+(', snapshot restore' if game=='tablesoccer' else ''))
        assert len(set(rooms))==3
        w=await ws(clients[4]);await w.send_json({'type':'create_room','settings':{'gameId':'unknown'}})
        assert (await receive(w,'created')).get('code')=='UNKNOWN_GAME'
        results.append('unsupported game rejected; three independent matches on one backend')
        print(json.dumps({'ok':True,'results':results},ensure_ascii=False,indent=2))
    finally:
        for w in sockets: await w.close()
        if runner:await runner.cleanup()
        for s in sessions:await s.close()
        proc.terminate()
        try:proc.wait(timeout=3)
        except subprocess.TimeoutExpired:proc.kill();proc.wait()
if __name__=='__main__':asyncio.run(main())
