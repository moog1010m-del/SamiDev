"""A timer/checkpoint may advance Redis sequence before an accepted HTTP move is committed."""
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
os.environ.setdefault('SAMIDEV_REQUIRE_GAME_AUTH', '0')
from app import SamiDevRealtime, Conn
from store import MemoryStore, RedisStore, StoreError, sanitize_settings


class Socket:
    closed = False
    async def send_str(self, value): pass


async def check(store):
    service = SamiDevRealtime()
    service.store = store
    data = await store.create_room('A', sanitize_settings({'players': 0}), 'race-a', 'a')
    rid = data['roomId']
    await store.join_room(rid, 'B', None, 'race-b', 'b')
    await store.runtime_ready(rid, 0, 'a', 1)
    await store.runtime_ready(rid, 1, 'b', 1)
    lease = await store.claim_authority(rid, 'http://fake', False)
    messages = []
    async def fanout(room, payload, **kwargs): messages.append(payload)
    async def noop(*args): pass
    service.fanout = fanout
    service._award_profile_wins = noop
    service._award_daily_match_rewards = noop
    class Host:
        def has_shard(self, shard): return True
        async def move(self, room, seat, packet, **kwargs):
            # Real interleaving: an authority event synchronizes sequence first.
            await store.sync_sequence(rid, [1, 0])
            return {'accepted': True, 'packet': packet, 'sequence': [1, 0],
                    'turn': [1], 'authorityEpoch': lease['epoch'], 'authorityRevision': 1}
    service.gamehost = Host()
    conn = Conn(Socket(), 'a', 'local', room_id=rid, seat=0, connection_epoch=1)
    await service.handle(conn, {'type': 'move', 'packet': {'n': 0, 'i': 'accepted', 'm': {'m': 0}}})
    assert any(m['type'] == 'move' for m in messages), 'accepted engine move was dropped by store sequence race'
    assert (await store.get_room_state(rid))['moveCount'] == 1
    duplicate = await store.append_move(rid, 0, {'n':0,'i':'accepted','m':{'m':0}},
        authority_epoch=lease['epoch'], authority_shard=lease['shard'])
    assert duplicate['moveIndex'] == 0 and (await store.get_room_state(rid))['moveCount'] == 1
    try:
        await store.append_move(rid, 0, {'n':1,'i':'old-host','m':{'m':0}},
            authority_epoch=lease['epoch']-1, authority_shard=lease['shard'])
        raise AssertionError('stale authority committed a move')
    except StoreError as exc: assert exc.code == 'STALE_AUTHORITY'
    try:
        await store.append_move(rid, 0, {'n': 0, 'i': 'untrusted', 'm': {'m': 0}})
        raise AssertionError('untrusted stale packet accepted')
    except StoreError as exc: assert exc.code == 'DESYNC'
    if isinstance(store, RedisStore):
        keys = [key async for key in store.r.scan_iter(match=store.prefix + ':*')]
        if keys: await store.r.delete(*keys)
        await store.r.aclose()


async def main():
    await check(MemoryStore())
    if os.environ.get('SAMIDEV_TEST_REDIS_URL'):
        import secrets
        await check(RedisStore(os.environ['SAMIDEV_TEST_REDIS_URL'], prefix='race-' + secrets.token_hex(6)))
    print('PASS accepted move survives authority/store race; untrusted stale moves still rejected')

asyncio.run(main())
