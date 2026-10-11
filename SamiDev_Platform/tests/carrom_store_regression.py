"""Verify authenticated theme selection, wallet isolation and persistent store state."""
from __future__ import annotations
import asyncio
import os
import sys
from pathlib import Path
os.environ.setdefault('SAMIDEV_STORE', 'memory')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from social_platform import PlatformService, PlatformHttp, PlatformError, STORE_CATALOG

@web.middleware
async def errors(request, handler):
    try:
        return await handler(request)
    except PlatformError as exc:
        return web.json_response({'ok': False, 'error': exc.code}, status=exc.status)

class RedisStoreDouble:
    """Exercise the Redis service branch across independent service instances."""
    def __init__(self): self.hashes = {}; self.sets = {}
    async def get(self, key): return None
    async def hgetall(self, key): return dict(self.hashes.get(key, {}))
    async def hget(self, key, field): return self.hashes.get(key, {}).get(field)
    async def hset(self, key, field=None, value=None, mapping=None):
        self.hashes.setdefault(key, {}).update(mapping if mapping is not None else {field:value})
    async def smembers(self, key): return set(self.sets.get(key, set()))
    async def sismember(self, key, item): return item in self.sets.get(key, set())
    async def lrange(self, key, start, end): return []

async def main():
    service = PlatformService(None)
    api = PlatformHttp(service, None)
    app = web.Application(middlewares=[errors])
    for method, route, handler in [('POST','/api/auth/register',api.register), ('POST','/api/auth/login',api.login), ('POST','/api/auth/logout',api.logout), ('GET','/api/store',api.store_state), ('POST','/api/store/equip',api.store_equip)]:
        app.router.add_route(method, route, handler)
    app.router.add_static('/images/', ROOT/'game/images')
    app.router.add_static('/games/', ROOT/'game/games')
    async with TestClient(TestServer(app)) as client:
        assert (await client.get('/api/store')).status == 401
        assert (await client.post('/api/store/equip', json={'itemId':'carrom_cat'})).status == 401
        response = await client.post('/api/auth/register', json={'username':'theme_user','password':'Test-password-123','displayName':'Theme User'})
        assert response.status == 200, await response.text()
        uid = (await response.json())['user']['id']
        snapshot = await (await client.get('/api/store')).json()
        assert snapshot['equipped']['carrom_theme'] == 'carrom_classic'
        assert len(snapshot['catalog']) == len(STORE_CATALOG) and all(i['owned'] for i in snapshot['catalog'])
        assert snapshot['equipped']['pool_cue'] == 'pool_cue_classic'
        assert (await client.post('/api/store/equip', json={'itemId':'pool_cue_moon'})).status == 200
        moon_snapshot = await (await client.get('/api/store')).json()
        assert moon_snapshot['equipped']['pool_cue'] == 'pool_cue_moon'
        assert moon_snapshot['coins'] == snapshot['coins']
        assert moon_snapshot['equipped']['carrom_theme'] == 'carrom_classic'
        for item in snapshot['catalog']:
            assert (await client.get(item['asset'])).status == 200, item['asset']
        assert (await client.get('/images/themes/cat-atlas.webp')).status == 200
        balance = snapshot['coins']
        response = await client.post('/api/store/equip', json={'itemId':'carrom_cat','uid':'someone_else','price':-9999})
        assert response.status == 200, await response.text()
        snapshot = await (await client.get('/api/store')).json()
        assert snapshot['equipped']['carrom_theme'] == 'carrom_cat'
        assert snapshot['coins'] == balance and snapshot['ledger'] == []
        assert next(i for i in snapshot['catalog'] if i['id']=='carrom_cat')['equipped'] is True
        assert (await client.post('/api/store/equip', json={'itemId':'../../images/evil'})).status == 404
        await client.post('/api/auth/logout', json={})
        assert (await client.get('/api/store')).status == 401
        await client.post('/api/auth/register', json={'username':'theme_other','password':'Test-password-123'})
        assert (await (await client.get('/api/store')).json())['equipped']['carrom_theme'] == 'carrom_classic'
        await client.post('/api/auth/logout', json={})
        await client.post('/api/auth/login', json={'username':'theme_user','password':'Test-password-123'})
        assert (await (await client.get('/api/store')).json())['equipped']['carrom_theme'] == 'carrom_cat'
        await client.post('/api/store/equip', json={'itemId':'carrom_classic'})
        assert (await (await client.get('/api/store')).json())['equipped']['carrom_theme'] == 'carrom_classic'
        # Future inventory-only products must still enforce ownership.
        STORE_CATALOG['test_inventory_only'] = {'slot':'test_slot','price':100}
        try:
            response = await client.post('/api/store/equip', json={'itemId':'test_inventory_only'})
            assert response.status == 403, await response.text()
        finally:
            del STORE_CATALOG['test_inventory_only']
    redis = RedisStoreDouble()
    first = PlatformService(redis)
    await redis.hset(first.k_user(uid), mapping=await service.get_user(uid))
    assert (await first.store_snapshot(uid))['equipped']['carrom_theme'] == 'carrom_classic'
    await first.equip_store_item(uid, 'carrom_cat')
    second = PlatformService(redis)
    assert (await second.store_snapshot(uid))['equipped']['carrom_theme'] == 'carrom_cat'
    await second.equip_store_item(uid, 'carrom_classic')
    assert (await first.store_snapshot(uid))['equipped']['carrom_theme'] == 'carrom_classic'
    assert (await second.store_snapshot(uid))['coins'] == balance
    print('carrom_store_regression: OK (HTTP sessions, free equip, return to classic, account isolation, Redis branch persistence, unchanged wallet)')

if __name__ == '__main__': asyncio.run(main())
