"""Apply/verify/rollback tests using a temporary PostgreSQL schema and Redis prefix."""
import asyncio
import json
import os
import secrets
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / 'backend'), str(ROOT / 'tools')]
prefix = 'migrationtest' + secrets.token_hex(6)
os.environ['SAMIDEV_PLATFORM_PREFIX'] = prefix
from social_platform import PlatformService
from postgres_store import SCHEMA
from migrate_social_to_postgres import migrate
import asyncpg
import redis.asyncio as redis


async def main():
    r = redis.from_url(os.environ['SAMIDEV_TEST_REDIS_URL'], decode_responses=True)
    base = await asyncpg.connect(os.environ['SAMIDEV_TEST_DATABASE_URL'])
    schema = prefix
    pool = None
    checks = []
    try:
        await base.execute(f'CREATE SCHEMA "{schema}"')
        pool = await asyncpg.create_pool(os.environ['SAMIDEV_TEST_DATABASE_URL'],
            server_settings={'search_path': schema})
        async with pool.acquire() as conn: await conn.execute(SCHEMA)
        destination = SimpleNamespace(pool=pool)
        legacy = PlatformService(r)
        user = await legacy.create_user('migration_user', 'Test-password-123')
        uid = user['id']
        await legacy.award_daily_match_coins(uid, 'MIG001')
        await legacy.buy_store_item(uid, 'profile_star')
        await legacy.create_session(uid)
        await legacy.append_community_chat(uid, 'majlis', 'رسالة محفوظة')
        preview = await migrate(r, destination)
        async with pool.acquire() as conn:
            assert await conn.fetchval('SELECT count(*) FROM samidev_social_documents') == 0
        assert preview['dryRun']
        result = await migrate(r, destination, apply=True)
        assert result['verified'] and result['documents'] == preview['documents']
        async with pool.acquire() as conn:
            imported = json.loads(await conn.fetchval('SELECT value FROM samidev_social_documents WHERE key=$1', legacy.k_user(uid)))
            assert imported['passwordHash'] == user['passwordHash']
            assert imported['coins'] == '0' and imported['starsCount'] == '1'
            assert await conn.fetchval('SELECT count(*) FROM samidev_social_documents WHERE key LIKE $1', prefix + ':session:%') == 0
            assert await conn.fetchval('SELECT count(*) FROM samidev_social_documents WHERE expires_at IS NOT NULL') >= 2
        assert await r.exists(legacy.k_user(uid)), 'Migration must not delete source'
        checks.append('dry-run, exact import verification, expiry retention and untouched source')
        try:
            await migrate(r, destination, apply=True)
            raise AssertionError('Nonempty destination accepted')
        except RuntimeError as e:
            assert 'not empty' in str(e)
        checks.append('repeat apply refuses overwriting existing data')
        await r.set(legacy.k_username('migration_user'), 'invalid')
        try:
            await migrate(r, destination, apply=True)
            raise AssertionError('Corrupt source accepted')
        except RuntimeError as e:
            assert 'username index' in str(e)
        checks.append('corrupt source rejected')
        await r.set(legacy.k_username('migration_user'), uid)
        async with pool.acquire() as conn:
            await conn.execute('DELETE FROM samidev_social_documents')
            await conn.execute("ALTER TABLE samidev_social_documents ADD CHECK (kind <> 'hash')")
        try:
            await migrate(r, destination, apply=True)
            raise AssertionError('Injected database failure did not abort')
        except asyncpg.CheckViolationError: pass
        async with pool.acquire() as conn:
            assert await conn.fetchval('SELECT count(*) FROM samidev_social_documents') == 0
        checks.append('whole import rolls back on database failure')
        print(json.dumps({'ok': True, 'checks': checks, 'count': len(checks)}))
    finally:
        if pool: await pool.close()
        await base.execute(f'DROP SCHEMA "{schema}" CASCADE')
        await base.close()
        async for key in r.scan_iter(match=prefix + ':*'): await r.delete(key)
        await r.aclose()


if __name__ == '__main__': asyncio.run(main())
