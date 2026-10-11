import asyncio
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from social_platform import PlatformService
from store import MemoryStore, sanitize_settings


async def main():
    platform = PlatformService(None)
    u1 = await platform.create_user('hub_user_one', 'Test-password-123', 'الأول')
    u2 = await platform.create_user('hub_user_two', 'Test-password-123', 'الثاني')

    await platform.touch_community(u1['id'], 'majlis')
    await platform.touch_community(u2['id'], 'square')
    majlis = await platform.community_members('majlis')
    square = await platform.community_members('square')
    assert {x['id'] for x in majlis} == {u1['id']}
    assert {x['id'] for x in square} == {u2['id']}

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

    print('COMMUNITY_HUB_REGRESSION_PASS')


if __name__ == '__main__':
    asyncio.run(main())
