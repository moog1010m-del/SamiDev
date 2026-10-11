"""Integration tests against real PostgreSQL and Redis. Uses isolated namespaces.

SAMIDEV_TEST_DATABASE_URL and SAMIDEV_TEST_REDIS_URL are mandatory. No FLUSHDB,
TRUNCATE, or deletion of other accounts is performed.
"""
import asyncio
import json
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'tools')]
# Set before importing the social layer; namespace is unique for this test run.
os.environ['SAMIDEV_PLATFORM_PREFIX'] = 'test' + secrets.token_hex(6)
from social_platform import PlatformService, PlatformError, STORE_CATALOG, MATCH_REWARD_COINS
from postgres_platform import PostgresPlatformService
from postgres_store import durable_key
from migrate_social_to_postgres import read_source
import redis.asyncio as redis


async def main():
    db_url = os.environ['SAMIDEV_TEST_DATABASE_URL']
    r = redis.from_url(os.environ['SAMIDEV_TEST_REDIS_URL'], decode_responses=True)
    services = [PostgresPlatformService(db_url, r), PostgresPlatformService(db_url, r)]
    prefix = os.environ['SAMIDEV_PLATFORM_PREFIX']
    checks = []
    try:
        await asyncio.gather(*(s.start() for s in services))
        a, b = services
        results = await asyncio.gather(*[
            s.create_user('race_name', 'Test-password-123') for s in services
        ], return_exceptions=True)
        assert sum(isinstance(x, dict) for x in results) == 1
        assert [x.code for x in results if isinstance(x, PlatformError)] == ['USERNAME_TAKEN']
        user = next(x for x in results if isinstance(x, dict))
        uid = user['id']
        assert (await b.authenticate('race_name', 'Test-password-123'))['id'] == uid
        checks.append('atomic registration and cross-gateway login')

        rewards = await asyncio.gather(*[
            services[i % 2].award_daily_match_coins(uid, 'SAME01') for i in range(20)
        ])
        assert sum(x['awarded'] for x in rewards) == 1
        assert (await a.get_user(uid))['coins'] == str(MATCH_REWARD_COINS)
        rewards = await asyncio.gather(*[
            services[i % 2].award_daily_match_coins(uid, f'ROOM{i:02}') for i in range(20)
        ])
        assert sum(x['awarded'] for x in rewards) == 4
        assert (await b.store_snapshot(uid))['coins'] == 5 * MATCH_REWARD_COINS
        checks.append('idempotent rewards and daily limit across gateways')

        await a.r.hset(a.k_user(uid), mapping={'coins': '1000'})
        bought = await asyncio.gather(*[
            services[i % 2].buy_store_item(uid, 'badge_crown') for i in range(10)
        ], return_exceptions=True)
        assert sum(isinstance(x, dict) for x in bought) == 1
        assert all(x.code == 'STORE_ALREADY_OWNED' for x in bought if isinstance(x, PlatformError))
        assert (await b.get_user(uid))['coins'] == '900'
        stars = await asyncio.gather(*[
            services[i % 2].buy_store_item(uid, 'profile_star') for i in range(10)
        ], return_exceptions=True)
        assert sum(isinstance(x, dict) for x in stars) == 5
        assert (await b.get_user(uid))['coins'] == '650'
        assert (await b.get_user(uid))['starsCount'] == '5'
        await a.equip_store_item(uid, 'badge_crown')
        assert (await b.public_profile(uid))['nameBadge'] == 'badge_crown'
        checks.append('atomic purchases, star cap, inventory and equipment')

        # An exception after updating the balance must undo every write.
        try:
            async with a.r.transaction([a.k_user(uid)]):
                await a.r.hset(a.k_user(uid), 'coins', '0')
                raise RuntimeError('injected failure')
        except RuntimeError: pass
        assert (await b.get_user(uid))['coins'] == '650'
        checks.append('transaction rollback')

        other = await b.create_user('other_name', 'Test-password-123')
        await a.send_friend_request(user, other['username'])
        await b.respond_friend_request(other, uid, True)
        assert await a.are_friends(uid, other['id'])
        assert await b.are_friends(other['id'], uid)
        reps = await asyncio.gather(*[
            services[i % 2].grant_reputation(uid, other['id']) for i in range(10)
        ], return_exceptions=True)
        assert sum(isinstance(x, dict) for x in reps) == 1
        ratings = await asyncio.gather(*[
            services[i % 2].record_match_rating(uid, other['id'], 'RATE01', True) for i in range(10)
        ], return_exceptions=True)
        assert sum(isinstance(x, dict) for x in ratings) == 1
        assert (await b.get_user(other['id']))['reputation'] == '2'
        await a.submit_report(uid, other['id'], message='test report')
        assert len(await b.list_reports()) == 1
        await a.append_community_chat(uid, 'majlis', 'مرحبا')
        assert (await b.community_chat_history('majlis'))[-1]['text'] == 'مرحبا'
        assert len(await a.search_users('other', uid)) == 1
        checks.append('friends, reputation, ratings, reports, chat and search')

        token = await a.create_session(uid)
        assert (await b.resolve_session(token))['id'] == uid
        ticket = await a.issue_game_ticket(user, session_token=token)
        tickets = await asyncio.gather(*[
            s.consume_game_ticket(ticket['ticket']) for s in services
        ])
        assert sum(x is not None for x in tickets) == 1
        assert await b.is_online(uid)
        await a.set_banned(uid, True)
        assert await b.resolve_session(token) is None
        checks.append('shared transient sessions, one-time tickets and ban revocation')

        # Database values survive closing the first gateway and losing ALL Redis
        # keys in this isolated namespace. Login and wallet still work.
        await a.set_banned(uid, False)
        await a.close()
        async for key in r.scan_iter(match=prefix + ':*'):
            assert not durable_key(key), 'Durable account data leaked to Redis'
            await r.delete(key)
        replacement = PostgresPlatformService(db_url, r)
        services[0] = replacement
        await replacement.start()
        assert (await replacement.authenticate('race_name', 'Test-password-123'))['coins'] == '650'
        assert 'badge_crown' in (await replacement.store_snapshot(uid))['inventory']
        assert (await replacement.get_user(other['id']))['reputation'] == '2'
        checks.append('durability after gateway restart and loss of transient Redis keys')

        # Exercise migration input against real legacy Redis data.
        legacy = PlatformService(r)
        legacy_user = await legacy.create_user('legacy_name', 'Test-password-123')
        await legacy.award_daily_match_coins(legacy_user['id'], 'OLD001')
        source = await read_source(r)
        assert source[legacy.k_user(legacy_user['id'])][1]['coins'] == str(MATCH_REWARD_COINS)
        assert all(durable_key(k) for k in source)
        checks.append('legacy migration source and transient exclusion')
        print(json.dumps({'ok': True, 'checks': checks, 'count': len(checks)}))
    finally:
        for s in services:
            if s.r.pool:
                async with s.r.pool.acquire() as conn:
                    await conn.execute('DELETE FROM samidev_social_documents WHERE key LIKE $1', prefix + ':%')
                await s.close()
        async for key in r.scan_iter(match=prefix + ':*'):
            await r.delete(key)
        await r.aclose()


if __name__ == '__main__':
    asyncio.run(main())
