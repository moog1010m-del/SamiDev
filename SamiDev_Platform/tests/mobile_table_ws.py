"""Retained waiting table + real community/profile HTTP reads and room events.

Temporary local memory backend only; this does not simulate Flutter rendering.
"""
import asyncio
import os
import subprocess
import aiohttp
from aiohttp import web
from multigame_ws import ROOT, GH_PORT, GH, app, receive


async def main():
    process = subprocess.Popen(['node', str(ROOT/'gamehost/server.js')], cwd=ROOT,
        env=dict(os.environ, SAMIDEV_GAMEHOST_HOST='127.0.0.1', SAMIDEV_GAMEHOST_PORT=str(GH_PORT)), stdout=subprocess.DEVNULL)
    runner = web.AppRunner(app.make_app())
    clients = [aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True), headers={'Origin':'http://localhost'}) for _ in range(2)]
    sockets = []
    try:
        for _ in range(100):
            try:
                async with clients[0].get(GH+'/health') as r:
                    if r.status == 200: break
            except aiohttp.ClientError: pass
            await asyncio.sleep(.05)
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0); await site.start()
        base = f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'
        users = []
        for i, client in enumerate(clients):
            async with client.post(base+'/api/auth/register', json={'username':f'retained_player_{i}','displayName':f'لاعب {i}','password':'Test-password-123'}) as r:
                assert r.status == 200, await r.text()
                users.append((await r.json())['user'])
            async with client.post(base+'/api/communities/majlis/enter', json={}) as r:
                assert r.status == 200, await r.text()
        for game in ['pool','carrom','crazy8','tablesoccer']:
            owner, other = [await c.ws_connect(base+'/ws') for c in clients]; sockets.extend([owner,other])
            await owner.send_json({'type':'create_room','communityId':'majlis','settings':{'gameId':game,'players':0,'seats':0,'live':1}})
            created = await receive(owner,'created'); assert created['type']=='created', created
            rid = created['roomId']
            assert len([p for p in created['roster'] if p and p.get('name')]) == 1
            # Browsing uses HTTP, leaving the same game socket/seat connected.
            for route in ['/api/communities/majlis','/api/store',f"/api/public-profile/{users[1]['id']}"]:
                async with clients[0].get(base+route) as r:
                    assert r.status==200, await r.text()
                    data=await r.json(); assert data.get('ok') is not False
                    if 'public-profile' in route: assert data['user']['id']==users[1]['id']
            state = await app.SERVICE.store.get_room_state(rid)
            assert state['roster'][0]['connected'] and not state['begun']
            await other.send_json({'type':'join_room','roomId':rid})
            assert (await receive(other,'joined'))['type']=='joined'
            while True:
                update = await receive(owner,'room_state'); assert update['type']=='room_state', update
                occupied = [p for p in update['roster'] if p and p.get('name')]
                if len(occupied)==2: break
            assert {p['accountId'] for p in occupied} == {u['id'] for u in users}
            assert occupied[0]['connected'] and occupied[1]['connected']
            assert (await receive(owner,'start'))['type']=='start'
            assert not (await app.SERVICE.store.get_room_state(rid))['begun']  # no fake local startup
            await owner.send_json({'type':'leave_room'})
            assert (await receive(owner,'left_room'))['type']=='left_room'
            await owner.close(); await other.close()
        print('PASS: four actual rooms retained during community/store/profile reads; live opponent metadata; start waits for ready; explicit leave acknowledged')
    finally:
        for socket in sockets: await socket.close()
        for client in clients: await client.close()
        await runner.cleanup()
        process.terminate()
        try: process.wait(timeout=3)
        except subprocess.TimeoutExpired: process.kill(); process.wait()


if __name__=='__main__': asyncio.run(main())
