"""Real PostgreSQL + Redis + two HTTP gateways + Chromium delivery timing.
Requires dedicated SAMIDEV_TEST_DATABASE_URL and localhost SAMIDEV_TEST_REDIS_URL.
Uses unique prefixes; never flushes databases or changes production settings.
"""
import asyncio
import json
import os
from pathlib import Path
import secrets
import sys
import tempfile
from urllib.parse import urlsplit

from aiohttp import web
import redis.asyncio as redis

ROOT = Path(__file__).resolve().parents[1]
prefix = 'chatdiag' + secrets.token_hex(8)
os.environ.update(SAMIDEV_STORE='memory', SAMIDEV_PLATFORM_STORE='memory',
                  SAMIDEV_FIREBASE_AUTH='0', SAMIDEV_PRODUCTION='0',
                  SAMIDEV_ADMIN_USERNAME='', SAMIDEV_ADMIN_PASSWORD='',
                  SAMIDEV_PLATFORM_PREFIX=prefix, SAMIDEV_ALLOWED_ORIGINS='*')
sys.path.insert(0, str(ROOT / 'backend'))
import app
from postgres_platform import PostgresPlatformService
from social_platform import PlatformHttp, PlatformError
from store import RedisStore, StoreError, sanitize_settings
from room_policy import DEFAULTS


async def admission_checks(services, stores):
    users = [await services[0].accounts.guest() for _ in range(3)]
    # The ordinary transaction guard must stay strict after the admission fix.
    async with services[0].r.transaction([services[0].k_user(users[0]['id'])]):
        try:
            await services[0].get_user(users[1]['id'])
            raise AssertionError('unlocked document access was allowed')
        except RuntimeError as error:
            assert 'unlocked social key' in str(error)
    await services[0].room_policy.configure('majlis', {**DEFAULTS, 'maxMembers': 1})
    async def enter(i):
        try:
            return await services[i].touch_community(users[i]['id'], 'majlis')
        except PlatformError as error:
            return error.code
    entered = await asyncio.gather(enter(0), enter(1))
    assert entered.count('majlis') == 1 and entered.count('COMMUNITY_FULL') == 1, entered
    for i in range(2):
        await services[i].leave_community(users[i]['id'], 'majlis')
    await services[0].room_policy.configure('majlis', {**DEFAULTS, 'maxTables': 1})
    async def create(i):
        policy = services[i].room_policy
        try:
            async with policy.transaction():
                await policy.admit(stores[i], users[0]['id'], 'majlis', 'create_room', {})
                return await stores[i].create_room('Test', sanitize_settings({'gameId':'pool'}),
                    'diagnostic', f'owner-{i}', users[0]['id'], 'majlis')
        except StoreError as error:
            return error.code
    created = await asyncio.gather(create(0), create(1))
    assert sum(isinstance(v, dict) for v in created) == 1 and 'ACCOUNT_IN_MATCH' in created, created
    index = 0 if isinstance(created[0], dict) else 1
    room = created[index]
    async with services[1].room_policy.transaction():
        try:
            await services[1].room_policy.admit(stores[1], users[2]['id'], 'majlis', 'create_room', {})
            raise AssertionError('table capacity bypassed')
        except StoreError as error:
            assert error.code == 'COMMUNITY_TABLE_LIMIT'
    async with services[1].room_policy.transaction():
        await services[1].room_policy.admit(stores[1], users[1]['id'], 'majlis', 'join_room', {'roomId':room['roomId']})
        joined = await stores[1].join_room(room['roomId'], 'Other', None, 'diagnostic', 'other', users[1]['id'])
    await stores[0].runtime_ready(room['roomId'], 0, f'owner-{index}', 1)
    await stores[1].runtime_ready(room['roomId'], joined['seat'], 'other', 1)
    await services[0].room_policy.finish(stores[0], room['roomId'])
    for user in users[:2]:
        assert await services[1].room_policy.read('cooldown:'+user['id']) > await services[1].room_policy.clock()
    await services[0].room_policy.configure('majlis', DEFAULTS)
    return ['strict document transaction guard', 'concurrent member cap',
            'one active match per account across gateways', 'table cap',
            'short-match cooldown persisted across gateways',
            'no admission deadlock with document pools limited to one connection']


async def main():
    database = os.environ['SAMIDEV_TEST_DATABASE_URL']
    redis_url = os.environ['SAMIDEV_TEST_REDIS_URL']
    assert urlsplit(database).hostname in {'127.0.0.1','localhost'}
    assert urlsplit(redis_url).hostname in {'127.0.0.1','localhost'}
    out = Path(os.environ.get('SAMIDEV_CHAT_DIAGNOSTIC_DIR', '/tmp/samidev-chat-diagnostic'))
    out.mkdir(parents=True, exist_ok=True)
    services, runners, redis_clients, stores = [], [], [], []
    try:
        bases = []
        for _ in range(2):
            r = redis.from_url(redis_url, decode_responses=True); redis_clients.append(r)
            # This is deliberately minimal: waiting admissions must not consume
            # the document connection needed by their current lock holder.
            service = PostgresPlatformService(database, r, max_connections=1)
            services.append(service); await service.start()
            store = RedisStore(redis_url, prefix=prefix+'rt'); stores.append(store)
            gateway = app.SamiDevRealtime()
            gateway.store = store; gateway.platform = service
            gateway.platform_http = PlatformHttp(service, store)
            app.SERVICE = gateway; application = app.make_app()
            # Test the real HTTP handlers, SQL and Redis; no game simulation is
            # required for community chat. Manage these dependencies explicitly.
            application.on_startup.clear(); application.on_cleanup.clear(); application.on_shutdown.clear()
            async def shutdown(application, service=service): await service.live.close()
            application.on_shutdown.append(shutdown)
            runner = web.AppRunner(application); runners.append(runner); await runner.setup()
            site = web.TCPSite(runner, '127.0.0.1', 0); await site.start()
            bases.append(f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}')
        checks = await asyncio.wait_for(admission_checks(services, stores), 30)
        marks = {}
        for service in services:
            original, publish = service.append_community_chat, service.live.publish
            async def timed(uid, cid, text, nonce=None, sticker=None, original=original):
                start = asyncio.get_running_loop().time()
                result = await original(uid, cid, text, nonce, sticker)
                marks.setdefault(nonce,{})['appendMs'] = round((asyncio.get_running_loop().time()-start)*1000, 3)
                return result
            async def timed_publish(cid, event, publish=publish):
                start = asyncio.get_running_loop().time(); await publish(cid, event)
                marks.setdefault(event.get('message',{}).get('clientMessageId'),{})['publishMs'] = round((asyncio.get_running_loop().time()-start)*1000, 3)
            service.append_community_chat = timed; service.live.publish = timed_publish
        async def scenario(control):
            rooms = {}
            for room in (['majlis'] if control else ['majlis','square','diwan','elite']):
                pair = []
                for i, service in enumerate(services):
                    user = await service.accounts.guest(); token = await service.create_session(user['id'])
                    pair.append(dict(base=bases[i], token=token))
                rooms[room] = pair
            with tempfile.TemporaryDirectory() as directory:
                config = Path(directory)/'sessions.json'
                config.write_text(json.dumps(dict(rooms=rooms, samplesPerDirection=4 if control else 8,
                                                  legacy=control, disableLive=control)))
                config.chmod(0o600)
                report = out/('polling.json' if control else 'live.json')
                process = await asyncio.create_subprocess_exec('node', str(ROOT/'tests/community_latency_browser.mjs'),
                    env=dict(os.environ, SAMIDEV_CHAT_BENCH_CONFIG=str(config), SAMIDEV_CHAT_BENCH_REPORT=str(report)))
                assert await process.wait() == 0, 'browser timing failed; see '+str(report)
        await scenario(False)
        await scenario(True)
        (out/'server.json').write_text(json.dumps(marks, indent=2))
        (out/'admission.json').write_text(json.dumps(checks, indent=2))
        print('POSTGRES_COMMUNITY_LATENCY_PASS: '+str(out))
    finally:
        for runner in runners: await runner.cleanup()
        for service in services:
            if service.r.pool:
                async with service.r.pool.acquire() as conn:
                    await conn.execute('DELETE FROM samidev_social_documents WHERE key LIKE $1', prefix+':%')
                await service.close()
        if redis_clients:
            r = redis_clients[0]
            keys = [k async for k in r.scan_iter(prefix+'*')]
            if keys: await r.delete(*keys)
        for store in stores: await store.r.aclose()
        for r in redis_clients: await r.aclose()

if __name__ == '__main__': asyncio.run(main())
