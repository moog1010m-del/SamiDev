"""Durable social storage, preserving the V37 data shapes during migration.

This is a deliberately small document API, not a Redis emulator. Game rooms,
pub/sub and rate limiting remain in Redis. PostgreSQL owns durable social keys.
All writes use ordered database locks, including keys that do not yet exist.
"""
from __future__ import annotations

import asyncio
import json
import os
from contextlib import asynccontextmanager
from contextvars import ContextVar

import asyncpg


SCHEMA = """
CREATE TABLE IF NOT EXISTS samidev_social_documents (
    key text PRIMARY KEY,
    kind text NOT NULL CHECK (kind IN ('string', 'hash', 'set', 'list')),
    value jsonb NOT NULL,
    expires_at timestamptz,
    CHECK (
        (kind = 'string' AND jsonb_typeof(value) = 'string') OR
        (kind = 'hash' AND jsonb_typeof(value) = 'object') OR
        (kind IN ('set', 'list') AND jsonb_typeof(value) = 'array')
    )
);
CREATE INDEX IF NOT EXISTS samidev_social_expiry
    ON samidev_social_documents(expires_at) WHERE expires_at IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS samidev_social_username
    ON samidev_social_documents ((split_part(key, ':', 1)), (value->>'usernameLower'))
    WHERE kind = 'hash' AND split_part(key, ':', 2) = 'user';
CREATE TABLE IF NOT EXISTS samidev_match_results (
    account_key text NOT NULL REFERENCES samidev_social_documents(key) ON DELETE CASCADE,
    match_id text NOT NULL,
    game_id text NOT NULL CHECK (game_id IN ('pool', 'carrom', 'tablesoccer', 'crazy8')),
    outcome text NOT NULL CHECK (outcome IN ('win', 'loss', 'draw')),
    recorded_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    PRIMARY KEY (account_key, match_id)
);
"""


def durable_key(key):
    """Only explicitly selected namespaces are persisted; new keys fail closed."""
    parts = str(key).split(':')
    return len(parts) >= 2 and parts[0] == os.getenv('SAMIDEV_PLATFORM_PREFIX', 'sdp') and parts[1] in {
        'user', 'user-blocks', 'username', 'firebase', 'account-sessions', 'account-deletion', 'moderation-audit', 'users', 'friends', 'requests', 'repday',
        'reptarget', 'matchrating', 'reports', 'store', 'community', 'community-catalog', 'game-stats', 'game-result',
    } and not (parts[1] == 'community' and (
        len(parts) < 4 or parts[-1] != 'chat'
    ))


class PostgresSocialStore:
    def __init__(self, url, transient, *, max_connections=10):
        if not url:
            raise RuntimeError('SAMIDEV_DATABASE_URL is required for PostgreSQL storage')
        self.url = url
        self.transient = transient
        self.max_connections = max_connections
        self.pool = None
        self._admission_pool = None
        self._transaction = ContextVar('samidev_social_transaction', default=None)
        self._sweeper = None

    async def start(self):
        self.pool = await asyncpg.create_pool(
            self.url, min_size=1, max_size=self.max_connections,
            timeout=15, command_timeout=30,
            server_settings={'application_name': 'samidev-social',
                             'lock_timeout': '10000'},
        )
        try:
            async with self.pool.acquire() as conn:
                async with conn.transaction():
                    await conn.execute("SELECT pg_advisory_xact_lock(hashtextextended('samidev:schema', 0))")
                    await conn.execute(SCHEMA)
            # Admission spans Redis room/presence operations and independently
            # locked social documents. Keep its mutex outside the document
            # transaction context. A separate single-connection pool prevents
            # waiting admissions from exhausting the document pool.
            self._admission_pool = await asyncpg.create_pool(
                self.url, min_size=0, max_size=1, timeout=15, command_timeout=30,
                server_settings={'application_name': 'samidev-admission',
                                 'lock_timeout': '10000'},
            )
            self._sweeper = asyncio.create_task(self._expire())
        except BaseException:
            if self._admission_pool:
                await self._admission_pool.close()
                self._admission_pool = None
            await self.pool.close()
            self.pool = None
            raise

    async def close(self):
        if self._sweeper:
            self._sweeper.cancel()
            await asyncio.gather(self._sweeper, return_exceptions=True)
        if self._admission_pool:
            await self._admission_pool.close()
            self._admission_pool = None
        if self.pool:
            await self.pool.close()
            self.pool = None

    @asynccontextmanager
    async def admission_lock(self, key):
        if self._transaction.get() is not None:
            raise RuntimeError('Acquire admission lock before social document transactions')
        async with self._admission_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute('SELECT pg_advisory_xact_lock(hashtextextended($1, 0))', str(key))
                yield

    async def ping(self):
        async with self.pool.acquire() as conn:
            return await conn.fetchval('SELECT 1') == 1

    async def _expire(self):
        while True:
            await asyncio.sleep(60)
            try:
                async with self.pool.acquire() as conn:
                    await conn.execute('''DELETE FROM samidev_social_documents
                        WHERE expires_at <= clock_timestamp() AND key IN (SELECT key FROM samidev_social_documents
                        WHERE expires_at <= clock_timestamp() LIMIT 1000)''')
            except Exception:
                # Keep trying; readiness reports database failures separately.
                pass

    @asynccontextmanager
    async def transaction(self, keys):
        keys = set(map(str, keys))
        existing = self._transaction.get()
        if existing:
            conn, locked = existing
            if not keys <= locked:
                raise RuntimeError('Transaction accessed an unlocked social key')
            yield conn
            return
        async with self.pool.acquire() as conn:
            async with conn.transaction():
                # Sort database lock IDs (rather than text keys) to avoid deadlocks
                # even in the extremely rare event of a hash collision.
                ids = await conn.fetch('''SELECT DISTINCT hashtextextended(k, 0) AS id
                    FROM unnest($1::text[]) k ORDER BY id''', sorted(keys))
                for row in ids:
                    await conn.execute('SELECT pg_advisory_xact_lock($1)', row['id'])
                token = self._transaction.set((conn, keys))
                try:
                    yield conn
                finally:
                    self._transaction.reset(token)

    async def _read(self, conn, key, kind):
        row = await conn.fetchrow('''SELECT kind, value FROM samidev_social_documents
            WHERE key=$1 AND (expires_at IS NULL OR expires_at > clock_timestamp())''', key)
        if row is None:
            return None
        if row['kind'] != kind:
            raise TypeError('Social document type mismatch')
        return json.loads(row['value'])

    async def _write(self, conn, key, kind, value, *, ex=None, preserve_expiry=True):
        if not durable_key(key):
            raise ValueError('Not a durable social key')
        await conn.execute('''INSERT INTO samidev_social_documents(key,kind,value,expires_at)
            VALUES ($1,$2,$3::jsonb,CASE WHEN $4::double precision IS NULL THEN NULL
                ELSE clock_timestamp() + $4 * interval '1 second' END)
            ON CONFLICT (key) DO UPDATE SET kind=EXCLUDED.kind,value=EXCLUDED.value,
                expires_at=CASE WHEN $5 THEN samidev_social_documents.expires_at
                ELSE EXCLUDED.expires_at END''', key, kind, json.dumps(value), ex, preserve_expiry)

    async def _execute(self, name, args, kwargs, conn):
        key = str(args[0])
        if name == 'delete':
            result = await conn.execute('DELETE FROM samidev_social_documents WHERE key=ANY($1::text[])', list(args))
            return int(result.split()[-1])
        if name == 'exists':
            return int(await conn.fetchval('''SELECT EXISTS(SELECT 1 FROM samidev_social_documents
                WHERE key=$1 AND (expires_at IS NULL OR expires_at > clock_timestamp()))''', key))
        kind = {'get': 'string', 'getdel': 'string', 'set': 'string', 'incr': 'string',
                'hget': 'hash', 'hgetall': 'hash', 'hset': 'hash', 'hincrby': 'hash',
                'sadd': 'set', 'srem': 'set', 'smembers': 'set', 'sismember': 'set',
                'lpush': 'list', 'rpush': 'list', 'lrange': 'list', 'ltrim': 'list'}[name]
        old = await self._read(conn, key, kind)
        if name == 'get': return old
        if name == 'getdel':
            await conn.execute('DELETE FROM samidev_social_documents WHERE key=$1', key)
            return old
        if name == 'set':
            if kwargs.get('nx') and old is not None: return None
            await self._write(conn, key, kind, str(args[1]), ex=kwargs.get('ex'), preserve_expiry=False)
            return True
        if name == 'incr':
            value = int(old or 0) + 1
            await self._write(conn, key, kind, str(value), preserve_expiry=old is not None)
            return value
        if kind == 'hash':
            value = old or {}
            if name == 'hgetall': return value
            if name == 'hget': return value.get(str(args[1]))
            if name == 'hincrby':
                result = int(value.get(str(args[1]), 0)) + int(args[2])
                value[str(args[1])] = str(result)
            else:
                updates = kwargs.get('mapping') or {args[1]: args[2]}
                result = sum(str(k) not in value for k in updates)
                value.update({str(k): str(v) for k, v in updates.items()})
        elif kind == 'set':
            value = set(old or [])
            if name == 'smembers': return value
            if name == 'sismember': return str(args[1]) in value
            before = len(value)
            if name == 'sadd': value.update(map(str, args[1:]))
            else: value.difference_update(map(str, args[1:]))
            result = abs(len(value) - before)
            value = sorted(value)
        else:
            value = old or []
            if name in {'lrange', 'ltrim'}:
                start, stop = int(args[1]), int(args[2])
                start = max(0, start if start >= 0 else len(value) + start)
                stop = stop if stop >= 0 else len(value) + stop
                value = value[start:stop + 1] if stop >= start else []
                if name == 'lrange': return value
                result = True
            else:
                additions = list(map(str, args[1:]))
                value = list(reversed(additions)) + value if name == 'lpush' else value + additions
                result = len(value)
        if kind in {'set', 'list'} and not value:
            await conn.execute('DELETE FROM samidev_social_documents WHERE key=$1', key)
        else:
            await self._write(conn, key, kind, value, preserve_expiry=old is not None)
        return result

    async def command(self, name, *args, **kwargs):
        keys = list(args) if name == 'delete' else [args[0]]
        routes = [durable_key(k) for k in keys]
        if not any(routes):
            return await getattr(self.transient, name)(*args, **kwargs)
        if not all(routes):
            raise ValueError('Mixed durable/transient command')
        # MVCC already provides a committed snapshot for one read-only SELECT.
        # Authentication must not pay BEGIN + lock-ID query + advisory lock +
        # COMMIT for every packet. Reads inside an explicit write transaction
        # still use its connection/locks and see its uncommitted changes.
        if name in {'get','exists','hget','hgetall','smembers','sismember','lrange'} and self._transaction.get() is None:
            async with self.pool.acquire() as conn:
                return await self._execute(name, args, kwargs, conn)
        async with self.transaction(keys) as conn:
            return await self._execute(name, args, kwargs, conn)

    def __getattr__(self, name):
        if name not in {'get', 'getdel', 'set', 'delete', 'exists', 'incr', 'hget',
                        'hgetall', 'hset', 'hincrby', 'sadd', 'srem', 'smembers',
                        'sismember', 'lpush', 'rpush', 'lrange', 'ltrim'}:
            raise AttributeError(name)
        async def call(*args, **kwargs):
            return await self.command(name, *args, **kwargs)
        return call

    def pipeline(self, transaction=True):
        return SocialPipeline(self)

    async def eval(self, script, numkeys, *args):
        keys, values = list(args[:numkeys]), list(args[numkeys:])
        if not any(durable_key(k) for k in keys):
            return await self.transient.eval(script, numkeys, *args)
        if not all(durable_key(k) for k in keys):
            raise ValueError('Mixed durable/transient operation')
        # Tags identify the four existing social operations. No Lua is executed
        # against PostgreSQL, and unknown operations are rejected.
        async with self.transaction(keys):
            if '-- samidev:daily-match-reward' in script:
                user_key, daily_key, claim_key, ledger_key = keys
                if not await self.exists(user_key): return [-2, 0, 0]
                balance = int(await self.hget(user_key, 'coins') or 0)
                used = int(await self.get(daily_key) or 0)
                if await self.exists(claim_key): return [2, used, balance]
                limit, amount = int(values[0]), int(values[1])
                if used >= limit:
                    await self.set(claim_key, 'limit', ex=int(values[7]))
                    return [0, used, balance]
                used += 1
                # Preserve the first increment's expiration, as Redis does.
                if used == 1:
                    await self.set(daily_key, used, ex=int(values[6]))
                else:
                    await self.incr(daily_key)
                balance = await self.hincrby(user_key, 'coins', amount)
                await self.set(claim_key, amount, ex=int(values[7]))
                entry = dict(id=values[2], type='daily_match_reward', amount=amount,
                             roomId=values[3], createdAt=int(values[4]), day=values[5], balance=balance)
                await self.lpush(ledger_key, json.dumps(entry))
                await self.ltrim(ledger_key, 0, int(values[8]) - 1)
                return [1, used, balance]
            if '-- samidev:grant-reputation' in script:
                daily_key, claim_key, user_key = keys
                used = int(await self.get(daily_key) or 0)
                reputation = int(await self.hget(user_key, 'reputation') or 0)
                if used >= int(values[0]): return [-1, used, reputation]
                if await self.exists(claim_key): return [-2, used, reputation]
                if not await self.exists(user_key):
                    raise RuntimeError('Reputation target no longer exists')
                await self.set(claim_key, '1', ex=int(values[1]))
                if used == 0:
                    await self.set(daily_key, '1', ex=int(values[1]))
                else:
                    await self.incr(daily_key)
                reputation = await self.hincrby(user_key, 'reputation', 1)
                return [1, used + 1, reputation]
            if '-- samidev:match-rating' in script:
                claim_key, user_key = keys
                reputation = int(await self.hget(user_key, 'reputation') or 0)
                if await self.exists(claim_key): return [-1, reputation]
                if not await self.exists(user_key):
                    raise RuntimeError('Rating target no longer exists')
                await self.set(claim_key, values[0], ex=int(values[1]))
                reputation = reputation + 1 if values[0] == '1' else max(0, reputation - 1)
                await self.hset(user_key, 'reputation', reputation)
                return [1, reputation]
            raise NotImplementedError('Unknown durable social operation')


class SocialPipeline:
    def __init__(self, store):
        self.store = store
        self.commands = []

    def __getattr__(self, name):
        def queue(*args, **kwargs):
            self.commands.append((name, args, kwargs))
            return self
        return queue

    async def execute(self):
        if not self.commands: return []
        keys = {a[0] for _, a, _ in self.commands}
        if not any(durable_key(k) for k in keys):
            pipeline = self.store.transient.pipeline(transaction=True)
            for name, args, kwargs in self.commands:
                getattr(pipeline, name)(*args, **kwargs)
            return await pipeline.execute()
        if not all(durable_key(k) for k in keys):
            raise ValueError('Mixed durable/transient pipeline')
        async with self.store.transaction(keys) as conn:
            return [await self.store._execute(n, a, kw, conn) for n, a, kw in self.commands]
