"""Offline, non-destructive V37 social migration. Dry-run is the default."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import redis.asyncio as redis
from postgres_store import PostgresSocialStore, durable_key


async def read_source(client):
    prefix = os.getenv('SAMIDEV_PLATFORM_PREFIX', 'sdp')
    documents = {}
    async for key in client.scan_iter(match=prefix + ':*', count=500):
        if not durable_key(key): continue
        # Gateways and writers must be stopped: SCAN is not a live snapshot.
        kind = await client.type(key)
        if kind == 'none': continue
        if kind == 'string': value = await client.get(key)
        elif kind == 'hash': value = await client.hgetall(key)
        elif kind == 'set': value = sorted(await client.smembers(key))
        elif kind == 'list': value = await client.lrange(key, 0, -1)
        else: raise RuntimeError('Unsupported durable Redis type; migration aborted')
        seconds, micros = await client.time()
        ttl = await client.pttl(key)
        if ttl == -2: continue
        expiry = None if ttl == -1 else datetime.fromtimestamp(seconds + micros / 1e6 + ttl / 1000, timezone.utc)
        documents[key] = (kind, value, expiry)
    # Do not migrate a corrupt/incomplete account index into a working database.
    users_key = prefix + ':users'
    users = documents.get(users_key, ('set', [], None))[1]
    for uid in users:
        user = documents.get(prefix + ':user:' + uid)
        if not user or user[0] != 'hash' or user[1].get('id') != uid:
            raise RuntimeError('Incomplete account index; migration aborted')
        lower = user[1].get('usernameLower')
        claimed = documents.get(prefix + ':username:' + str(lower))
        if not lower or not claimed or claimed[1] != uid:
            raise RuntimeError('Inconsistent username index; migration aborted')
    for key, (kind, value, _) in documents.items():
        if key.startswith(prefix + ':user:') and (kind != 'hash' or value.get('id') not in users):
            raise RuntimeError('Unindexed account; migration aborted')
        if key.startswith(prefix + ':username:') and (kind != 'string' or value not in users):
            raise RuntimeError('Orphan username claim; migration aborted')
    return documents


async def migrate(client, destination, *, apply=False):
    documents = await read_source(client)
    if not apply:
        return {'dryRun': True, 'documents': len(documents)}
    async with destination.pool.acquire() as conn:
        async with conn.transaction():
            # Entire import is all-or-nothing. Offline operation is mandatory.
            await conn.execute('LOCK TABLE samidev_social_documents IN EXCLUSIVE MODE')
            if await conn.fetchval('SELECT count(*) FROM samidev_social_documents'):
                raise RuntimeError('Destination is not empty; no data was overwritten')
            await conn.executemany('''INSERT INTO samidev_social_documents(key,kind,value,expires_at)
                VALUES ($1,$2,$3::jsonb,$4)''',
                [(key, kind, json.dumps(value), expiry) for key, (kind, value, expiry) in documents.items()])
            rows = await conn.fetch('SELECT key,kind,value,expires_at FROM samidev_social_documents')
            actual = {r['key']: (r['kind'], json.loads(r['value']), r['expires_at']) for r in rows}
            if actual != documents:
                raise RuntimeError('Import verification failed; transaction rolled back')
    return {'dryRun': False, 'documents': len(documents), 'verified': True}


async def main(args):
    if args.apply and not args.offline_confirmed:
        raise RuntimeError('--apply requires --offline-confirmed after stopping ALL writers')
    client = redis.from_url(os.environ['SAMIDEV_REDIS_URL'], decode_responses=True)
    destination = None
    try:
        if args.apply:
            destination = PostgresSocialStore(os.environ['SAMIDEV_DATABASE_URL'], client)
            await destination.start()
        print(json.dumps(await migrate(client, destination, apply=args.apply)))
    finally:
        if destination: await destination.close()
        await client.aclose()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--offline-confirmed', action='store_true')
    args = parser.parse_args()
    try:
        asyncio.run(main(args))
    except Exception as error:
        # Driver exceptions can contain row contents or credentials. Print only
        # our controlled errors, never arbitrary connection strings or payloads.
        message = str(error) if type(error) is RuntimeError else type(error).__name__
        print('Migration failed: ' + message, file=sys.stderr)
        sys.exit(1)
