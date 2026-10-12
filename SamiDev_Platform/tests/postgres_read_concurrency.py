"""Read authentication data without write locks; retain transactional write safety."""
import asyncio
import os
from pathlib import Path
import secrets
import sys
import redis.asyncio as redis
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
prefix='readfix'+secrets.token_hex(6)
os.environ['SAMIDEV_PLATFORM_PREFIX']=prefix
from postgres_store import PostgresSocialStore


async def main():
    r=redis.from_url(os.environ['SAMIDEV_TEST_REDIS_URL'],decode_responses=True)
    store=PostgresSocialStore(os.environ['SAMIDEV_TEST_DATABASE_URL'],r)
    await store.start()
    key=prefix+':user:test'
    release=asyncio.Event(); locked=asyncio.Event()
    try:
        await store.hset(key,mapping={'id':'test','coins':'0','banned':'0'})
        async def writer():
            async with store.transaction([key]):
                await store.hset(key,'coins','1')
                assert await store.hget(key,'coins')=='1'
                locked.set();await release.wait()
        task=asyncio.create_task(writer())
        await locked.wait()
        try:
            # PostgreSQL returns the committed row immediately while the account's
            # balance writer holds its lock. No dirty read or auth cache is used.
            row=await asyncio.wait_for(store.hgetall(key),2)
            assert row['coins']=='0'
        finally:
            release.set();await task
        assert await store.hget(key,'coins')=='1'
        await asyncio.gather(*(store.hincrby(key,'coins',1) for _ in range(50)))
        assert await store.hget(key,'coins')=='51'
        await store.hset(key,'banned','1')
        assert (await store.hgetall(key))['banned']=='1'
        print('PASS unlocked committed reads; own transactional reads; 50 atomic writes; ban visible immediately')
    finally:
        await store.delete(key)
        await store.close();await r.aclose()

asyncio.run(main())
