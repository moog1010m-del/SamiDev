"""Dedicated local databases only: catalog edits across gateways and restart."""
import asyncio,os,secrets,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
os.environ['SAMIDEV_PLATFORM_PREFIX']='catalog_test_'+secrets.token_hex(6)
import redis.asyncio as redis
from postgres_platform import PostgresPlatformService
from social_platform import PlatformError,PREFIX
from postgres_store import durable_key


async def main():
    database=os.environ['SAMIDEV_TEST_DATABASE_URL'];url=os.environ['SAMIDEV_TEST_REDIS_URL']
    assert '127.0.0.1' in database and '127.0.0.1' in url
    transient=redis.from_url(url,decode_responses=True)
    services=[PostgresPlatformService(database,transient,max_connections=4) for _ in range(2)]
    try:
        for service in services:await service.start()
        first,second=services
        assert durable_key(first.community_definitions.key())
        await first.community_definitions.save({'id':'coffee','name':'Coffee Room','description':'محفوظة بعد التحديث'})
        assert any(row['id']=='coffee' for row in await second.community_catalog())
        await second.community_definitions.save({'enabled':False},'square')
        assert not any(row['id']=='square' for row in await first.community_catalog())
        async def duplicate(service):
            try:await service.community_definitions.save({'id':'unique','name':'Unique'});return True
            except PlatformError as error:assert error.code=='COMMUNITY_EXISTS';return False
        assert sum(await asyncio.gather(*(duplicate(service) for service in services)))==1
        # Parallel edits must preserve both updates, not overwrite the whole document.
        await asyncio.gather(first.community_definitions.save({'enabled':False},'diwan'),second.community_definitions.save({'description':'Updated'},'coffee'))
        for service in services:await service.close()
        services=[]
        keys=[key async for key in transient.scan_iter(PREFIX+':*')]
        if keys:await transient.delete(*keys)
        restored=PostgresPlatformService(database,transient,max_connections=4);services=[restored];await restored.start()
        rows={row['id']:row for row in await restored.community_catalog(include_disabled=True)}
        assert not rows['square']['enabled'] and not rows['diwan']['enabled']
        assert rows['coffee']['description']=='Updated' and 'unique' in rows
        print('COMMUNITY_POSTGRES_PASS: durable definitions; cross-gateway refresh; unique IDs; concurrent edits; restart and Redis loss preserve disabled state')
    finally:
        for service in services:await service.close()
        await transient.aclose()


if __name__=='__main__':asyncio.run(main())
