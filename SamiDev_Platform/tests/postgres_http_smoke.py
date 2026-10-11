"""Production-mode HTTP/WebSocket smoke test with a running real GameHost.

Set test database/Redis URLs and SAMIDEV_GAMEHOST_SERVICE_KEY matching the host.
"""
import asyncio
import json
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
prefix = 'httptest' + secrets.token_hex(6)
os.environ.update({
    'SAMIDEV_PLATFORM_PREFIX': prefix,
    'SAMIDEV_DATABASE_URL': os.environ['SAMIDEV_TEST_DATABASE_URL'],
    'SAMIDEV_REDIS_URL': os.environ['SAMIDEV_TEST_REDIS_URL'],
    'SAMIDEV_STORE': 'redis', 'SAMIDEV_PLATFORM_STORE': 'postgres',
    'SAMIDEV_PRODUCTION': '1', 'SAMIDEV_REQUIRE_GAME_AUTH': '1',
    'SAMIDEV_ALLOWED_ORIGINS': 'https://game.example.test',
    'SAMIDEV_TRUST_PROXY': '1',
    'SAMIDEV_ADMIN_USERNAME': '', 'SAMIDEV_ADMIN_PASSWORD': '',
})
from aiohttp.test_utils import TestClient, TestServer
import app


async def receive(ws, kind):
    async with asyncio.timeout(10):
        while True:
            message = await ws.receive_json()
            if message.get('type') == 'error':
                raise AssertionError(message)
            if message.get('type') == kind: return message


async def main():
    client = TestClient(TestServer(app.make_app()))
    ws = None
    await client.start_server()
    headers = {'Origin': 'https://game.example.test', 'X-Forwarded-Proto': 'https'}
    uid = None
    checks = []
    try:
        health = await client.get('/health')
        assert health.status == 200
        assert (await health.json())['storage']['platform'] == 'postgres'
        checks.append('real PostgreSQL/Redis/GameHost startup in production mode')
        insecure = await client.post('/api/auth/register', json={}, headers={'Origin': headers['Origin']})
        assert insecure.status == 426
        body = {'username': 'http_' + secrets.token_hex(5), 'password': 'Test-password-123', 'displayName': 'Postgres Player'}
        registered = await client.post('/api/auth/register', json=body, headers=headers)
        assert registered.status == 200, await registered.text()
        uid = (await registered.json())['user']['id']
        token = registered.cookies['samidev_session'].value
        assert registered.cookies['samidev_session']['secure']
        # Simulate the secure reverse proxy's Cookie header over the local test socket.
        headers['Cookie'] = 'samidev_session=' + token
        me = await client.get('/api/me', headers=headers)
        assert me.status == 200 and (await me.json())['user']['id'] == uid
        login = await client.post('/api/auth/login', json=body, headers=headers)
        assert login.status == 200
        headers['Cookie'] = 'samidev_session=' + login.cookies['samidev_session'].value
        checks.append('registration, secure cookie, profile and login over HTTP API')
        await app.SERVICE.platform.award_daily_match_coins(uid, 'HTTP01')
        bought = await client.post('/api/store/buy', json={'itemId': 'profile_star'}, headers=headers)
        assert bought.status == 200, await bought.text()
        store = await client.get('/api/store', headers=headers)
        assert store.status == 200
        snapshot = await store.json()
        assert snapshot['coins'] == 0 and snapshot['starsCount'] == 1, snapshot
        checks.append('wallet reward and purchase through HTTP API')
        ticket_response = await client.post('/api/game-ticket', json={}, headers=headers)
        assert ticket_response.status == 200
        ticket = (await ticket_response.json())['ticket']
        ws = await client.ws_connect('/ws?ticket=' + ticket, headers=headers)
        await ws.send_json({'type': 'create_room', 'name': 'Spoofed',
                            'settings': {'players': 0, 'gamemode': 0, 'live': 1, 'break': 0}})
        created = await receive(ws, 'created')
        room_response = await client.get('/api/lobby/rooms', headers=headers)
        rooms = (await room_response.json())['rooms']
        room = next(x for x in rooms if x['roomId'] == created['roomId'])
        assert room['hostName'] == 'Postgres Player'
        await ws.send_json({'type': 'ping', 't': 123})
        assert (await receive(ws, 'pong'))['t'] == 123
        checks.append('authenticated WebSocket, room creation and lobby identity')
        await ws.close()
        await app.SERVICE.platform.close()
        failed = await client.get('/health')
        assert failed.status == 503 and not (await failed.json())['dependencies']['database']
        await app.SERVICE.platform.r.start()
        restored = await client.get('/health')
        assert restored.status == 200
        assert (await app.SERVICE.platform.get_user(uid))['starsCount'] == '1'
        checks.append('database readiness failure returns 503 and recovers without data loss')
        print(json.dumps({'ok': True, 'checks': checks, 'count': len(checks)}))
    finally:
        if ws: await ws.close()
        if app.SERVICE.platform.r.pool:
            async with app.SERVICE.platform.r.pool.acquire() as conn:
                await conn.execute('DELETE FROM samidev_social_documents WHERE key LIKE $1', prefix + ':%')
        async for key in app.SERVICE.store.r.scan_iter(match=prefix + ':*'):
            await app.SERVICE.store.r.delete(key)
        await client.close()


if __name__ == '__main__': asyncio.run(main())
