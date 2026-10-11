"""Seat ownership tests; optionally run identical cases against a real Redis."""
import asyncio
import json
import os
import secrets
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from store import MemoryStore, RedisStore, StoreError, sanitize_settings

async def exercise(store):
    checks = 0
    async def rejects(code, operation):
        nonlocal checks
        try:
            await operation
        except StoreError as e:
            assert e.code == code, (e.code, code)
            checks += 1
        else:
            raise AssertionError(f'Expected {code}')
    for game in ['carrom', 'tablesoccer', 'crazy8']:
        settings = sanitize_settings({'gameId':game,'players':1,'seats':2})
        owner = await store.create_room('Owner',settings,'node','original','owner')
        rid = owner['roomId']
        invitation = await store.create_invite(rid,0,'original',1,300)
        before = await store.get_room_state(rid)
        for account in ['attacker',None]:
            await rejects('RECONNECT_ACCOUNT_MISMATCH',store.join_room(rid,'Hijack',owner['token'],'evil','bad',account))
        assert await store.get_room_state(rid) == before
        await store.assert_connection(rid,0,'original',1)
        checks += 2
        await rejects('ACCOUNT_ALREADY_SEATED',store.join_room(rid,'Duplicate',None,'node','dup','owner'))
        await rejects('ACCOUNT_ALREADY_SEATED',store.join_invite(invitation['inviteToken'],'Duplicate','node','dup','owner'))
        # Rejection must not consume a valid invitation.
        guest = await store.join_invite(invitation['inviteToken'],'Guest','node','guest','guest')
        assert guest['seat']==1
        checks += 1
        # Concurrent attempts by one account must allocate just one seat.
        results = await asyncio.gather(*(store.join_room(rid,'Race',None,'node',f'race-{i}','racer') for i in range(2)),return_exceptions=True)
        assert sum(isinstance(r,dict) for r in results)==1
        assert sum(isinstance(r,StoreError) and r.code=='ACCOUNT_ALREADY_SEATED' for r in results)==1
        checks += 2
        rejoined = await store.join_room(rid,'Owner',owner['token'],'node','replacement','owner')
        assert rejoined['seat']==0 and rejoined['connectionEpoch']==2
        assert (await store.get_room_state(rid))['roster'][0]['accountId']=='owner'
        await store.assert_connection(rid,0,'replacement',2)
        checks += 3
        await rejects('STALE_CONNECTION',store.assert_connection(rid,0,'original',1))
    return checks

async def main():
    results={'memory':await exercise(MemoryStore())}
    url=os.getenv('SAMIDEV_TEST_REDIS_URL')
    if url:
        store=RedisStore(url,prefix='security-test-'+secrets.token_hex(8))
        try:
            await store.ping()
            results['redis']=await exercise(store)
        finally:
            keys=[k async for k in store.r.scan_iter(match=store.prefix+':*')]
            if keys: await store.r.delete(*keys)
            await store.r.aclose()
    print(json.dumps({'ok':True,'checks':results,'redisTested':bool(url)},indent=2))

if __name__=='__main__':asyncio.run(main())
