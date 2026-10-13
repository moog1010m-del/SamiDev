"""Authenticated real gateway/GameHost integration for every pool mode."""
import asyncio, os, subprocess
import aiohttp
from aiohttp import web
from multigame_ws import app, ROOT, GH, GH_PORT, receive

async def main():
    proc=subprocess.Popen(['node',str(ROOT/'gamehost/server.js')],cwd=ROOT,env=dict(os.environ,SAMIDEV_GAMEHOST_HOST='127.0.0.1',SAMIDEV_GAMEHOST_PORT=str(GH_PORT)),stdout=subprocess.DEVNULL)
    clients=[];sockets=[];runner=None
    try:
        for index in range(4):
            clients.append(aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True),headers={'Origin':'http://localhost'}))
        for _ in range(100):
            try:
                async with clients[0].get(GH+'/health') as response:
                    if response.status==200:break
            except aiohttp.ClientError:pass
            await asyncio.sleep(.05)
        runner=web.AppRunner(app.make_app());await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
        base=f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'
        for index,client in enumerate(clients):
            async with client.post(base+'/api/auth/register',json={'username':f'pool_modes_{index}','password':'Test-password-123'}) as response:assert response.status==200
        for mode,capacity in enumerate([2,4,4,2,4,4,3,2,2,2]):
            current=[await client.ws_connect(base+'/ws') for client in clients[:capacity]];sockets.extend(current)
            await current[0].send_json({'type':'create_room','settings':{'gameId':'pool','gameType':mode}})
            created=await receive(current[0],'created');assert created['type']=='created',created
            rid=created['roomId'];assert created['settings']['gameType']==mode
            for socket in current[1:]:
                await socket.send_json({'type':'join_room','roomId':rid});assert (await receive(socket,'joined'))['type']=='joined'
            for socket in current:
                start=await receive(socket,'start');assert start['capacity']==capacity,start
                assert start['settings']['gameType']==mode,start
                await socket.send_json({'type':'runtime_ready'})
            for socket in current:assert (await receive(socket,'begin_match'))['type']=='begin_match'
            lease=await app.SERVICE.store.get_authority(rid)
            state=await app.SERVICE.gamehost.state(rid,shard=lease['shard'])
            seq=state['sequence'][0]
            await current[0].send_json({'type':'move','packet':{'i':f'mode-{mode}-shot','n':seq,'m':{'a':1,'st':.8,'an':-1.5707963267948966,'sp':[0,0]}}})
            for socket in current:
                move=await receive(socket,'move');assert move['type']=='move',move
                assert move['reveal']['pool']['freePool']==(mode==7),move
            for socket in current:await socket.close()
        print('PASS ten pool modes: authenticated create/join/start/physics/fanout and capacities 2/3/4')
    finally:
        for socket in sockets:await socket.close()
        if runner:await runner.cleanup()
        for client in clients:await client.close()
        proc.terminate();proc.wait(timeout=5)

if __name__=='__main__':asyncio.run(main())
