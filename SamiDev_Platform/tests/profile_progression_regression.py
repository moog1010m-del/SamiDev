"""Per-game counters, immutable match claims, progression and ownership privacy."""
import asyncio
import os
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ['SAMIDEV_PLATFORM_PREFIX'] = 'ranktest' + secrets.token_hex(6)
from social_platform import PlatformService
from postgres_platform import PostgresPlatformService
from progression import progression, wins_for_level
from games import GAMES
import redis.asyncio as redis


async def exercise(service, other):
    user = await service.create_user('rank_' + secrets.token_hex(4), 'Test-password-123')
    uid = user['id']
    # Preserve historical aggregate wins, never infer which games earned them.
    await service.increment_wins(uid, 12)
    initial = await service.public_profile(uid)
    assert initial['showcaseItems'] == []
    assert initial['legacyWins'] == 12
    assert all(x['wins'] == 0 and x['level'] == 1 for x in initial['gameStatistics'])
    for game in GAMES:
        outcomes = await asyncio.gather(*[
            (service if i % 2 else other).record_game_result(uid, game, f'{game}:one', won=True)
            for i in range(12)
        ])
        assert sum(outcomes) == 1
        await other.record_game_result(uid, game, f'{game}:two', won=False)
        await other.record_game_result(uid, game, f'{game}:three', won=False, drawn=True)
    profile = await other.public_profile(uid)
    assert profile['wins'] == 16 and profile['legacyWins'] == 12
    for stat in profile['gameStatistics']:
        assert (stat['played'], stat['wins'], stat['losses'], stat['draws']) == (3, 1, 1, 1)
        assert (ROOT / 'game' / stat['icon'].lstrip('/')).exists()
        assert (ROOT / 'game' / stat['rankAsset'].lstrip('/')).exists()
    await service.award_daily_match_coins(uid, 'REWARD01')
    await service.buy_store_item(uid, 'profile_star')
    await service.grant_store_item(uid, 'badge_crown')
    profile = await other.public_profile(uid)
    assert {x['id'] for x in profile['showcaseItems']} == {'badge_crown', 'profile_star'}
    assert profile['ownedItemCount'] == 2
    assert not {'passwordHash','coins','authVersion','ledger'} & profile.keys()
    return uid


async def main():
    for level in range(1, 101):
        minimum = wins_for_level(level)
        p = progression(minimum)
        assert p['level'] == level and 0 <= p['progress'] <= 1
        assert (ROOT / 'game' / p['rankAsset'].lstrip('/')).exists()
        if level > 1: assert progression(minimum - 1)['level'] == level - 1
    assert progression(10**9)['level'] == 100 and progression(10**9)['progress'] == 1
    memory = PlatformService()
    await exercise(memory, memory)
    r = redis.from_url(os.environ['SAMIDEV_TEST_REDIS_URL'], decode_responses=True)
    legacy = PlatformService(r)
    services = [PostgresPlatformService(os.environ['SAMIDEV_TEST_DATABASE_URL'], r) for _ in range(2)]
    prefix = os.environ['SAMIDEV_PLATFORM_PREFIX']
    try:
        await exercise(legacy, legacy)
        await asyncio.gather(*(s.start() for s in services))
        uid = await exercise(*services)
        a, b = services
        # Counter failure after inserting the claim must roll back the claim too.
        increment = a.r.hincrby
        async def fail(*_): raise RuntimeError('injected write failure')
        a.r.hincrby = fail
        try:
            await a.record_game_result(uid, 'pool', 'rollback', won=True)
            raise AssertionError('Expected failure')
        except RuntimeError: pass
        finally: del a.r.hincrby
        assert await b.record_game_result(uid, 'pool', 'rollback', won=True)
        assert not await a.record_game_result(uid, 'pool', 'rollback', won=True)
        assert next(x for x in await a.game_statistics(uid) if x['gameId'] == 'pool')['wins'] == 2
        print('PASS: 100 rank boundaries; memory/Redis/PostgreSQL results; cross-gateway idempotency; rollback; real ownership; public privacy')
    finally:
        for service in services:
            if service.r.pool:
                async with service.r.pool.acquire() as conn:
                    await conn.execute('DELETE FROM samidev_social_documents WHERE key LIKE $1', prefix + ':%')
                await service.close()
        async for key in r.scan_iter(match=prefix + ':*'): await r.delete(key)
        await r.aclose()


if __name__ == '__main__': asyncio.run(main())
