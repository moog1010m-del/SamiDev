import asyncio
import os
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from social_platform import PlatformService
from store import MemoryStore, sanitize_settings


async def main():
    redis_url = os.environ.get("SAMIDEV_TEST_REDIS_URL")
    if redis_url:
        from redis.asyncio import Redis
        client = Redis.from_url(redis_url, decode_responses=True)
    else:
        client = None
    platform = PlatformService(client)
    u1 = await platform.create_user('hub_user_one', 'Test-password-123', 'الأول')
    u2 = await platform.create_user('hub_user_two', 'Test-password-123', 'الثاني')

    await platform.touch_community(u1['id'], 'majlis')
    await platform.touch_community(u2['id'], 'square')
    majlis = await platform.community_members('majlis')
    square = await platform.community_members('square')
    assert {x['id'] for x in majlis} == {u1['id']}
    assert {x['id'] for x in square} == {u2['id']}

    await platform.touch_community(u2['id'], 'majlis')
    assert [x['id'] for x in await platform.community_members('majlis')] == [u2['id'], u1['id']]
    await platform.renew_community_presence(u1['id'], 'majlis')
    assert [x['id'] for x in await platform.community_members('majlis')] == [u2['id'], u1['id']], 'heartbeat must not reorder members'
    assert [x['id'] for x in await platform.community_members('majlis', 1)] == [u2['id']], 'limit applies after sorting'
    await platform.leave_community(u1['id'], 'majlis')
    await platform.touch_community(u1['id'], 'majlis')
    assert [x['id'] for x in await platform.community_members('majlis')] == [u1['id'], u2['id']], 'actual re-entry goes first'
    await platform.touch_community(u2['id'], 'square')

    await platform.append_community_chat(u1['id'], 'majlis', 'رسالة المجلس')
    await platform.append_community_chat(u2['id'], 'square', 'رسالة الساحة')
    assert [x['text'] for x in await platform.community_chat_history('majlis')] == ['رسالة المجلس']
    assert [x['text'] for x in await platform.community_chat_history('square')] == ['رسالة الساحة']

    ticket = await platform.issue_game_ticket(u1, 'diwan')
    consumed = await platform.consume_game_ticket(ticket['ticket'])
    assert consumed and consumed['communityId'] == 'diwan'

    store = MemoryStore()
    settings = sanitize_settings({'players': 0, 'gamemode': 0, 'live': 1, 'break': 0})
    a = await store.create_room('Host A', settings, 'node-a', 'conn-a', u1['id'], 'majlis')
    b = await store.create_room('Host B', settings, 'node-b', 'conn-b', u2['id'], 'square')
    assert a['communityId'] == 'majlis'
    assert b['communityId'] == 'square'
    rooms = await store.list_public_rooms(20)
    mapping = {r['roomId']: r['communityId'] for r in rooms}
    assert mapping[a['roomId']] == 'majlis'
    assert mapping[b['roomId']] == 'square'

    if client is not None:
        await client.aclose()
    print('COMMUNITY_HUB_REGRESSION_PASS', 'redis' if redis_url else 'memory')


if __name__ == '__main__':
    asyncio.run(main())
