"""Paid chat/cover entitlement, persisted selection and safe message history."""
import asyncio
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / 'backend'))
from social_platform import PlatformService, PlatformError, STORE_CATALOG, public_user, cosmetic_id
from store import MemoryStore, StoreError, sanitize_settings

async def main():
    service = PlatformService(None)
    user = await service.create_user('cosmetic_check', 'Test-password-123', 'سامي')
    uid = user['id']
    service.mem_users[uid]['coins'] = '1000'
    for item in ['chat_turquoise', 'banner_dunes', 'badge_shard']:
        try:
            await service.equip_store_item(uid, item)
        except PlatformError as error:
            assert error.code == 'STORE_ITEM_NOT_OWNED'
        else:
            raise AssertionError('unowned paid item equipped')
        await service.buy_store_item(uid, item)
        await service.equip_store_item(uid, item)
    snapshot = await service.store_snapshot(uid)
    assert snapshot['coins'] == 400
    assert len(snapshot['ledger']) == 3
    assert snapshot['equipped']['chat_bubble'] == 'chat_turquoise'
    profile = await service.public_profile(uid, uid)
    assert profile['chatBubble'] == 'chat_turquoise'
    assert profile['profileBanner'] == 'banner_dunes'
    assert profile['nameBadge'] == 'badge_shard'
    text = '<img src=x onerror=alert(1)>'
    message = await service.append_community_chat(uid, 'majlis', text)
    assert message['chatBubble'] == 'chat_turquoise' and message['text'] == text
    await service.equip_store_item(uid, 'chat_default')
    plain = await service.append_community_chat(uid, 'majlis', 'عاد الشات البسيط')
    assert plain['chatBubble'] == 'chat_default'
    assert (await service.community_chat_history('majlis'))[0]['chatBubble'] == 'chat_turquoise'
    assert cosmetic_id('https://attacker.example/frame', 'chat_bubble') == ''
    assert cosmetic_id('banner_dunes', 'chat_bubble') == ''
    assert not any(item.get('retired') for item in snapshot['catalog'])
    await service.grant_store_item(uid, 'badge_crown')
    assert any(item['id'] == 'badge_crown' for item in (await service.store_snapshot(uid))['catalog'])
    await service.equip_store_item(uid, 'badge_crown')  # previous purchases remain usable
    room_store = MemoryStore()
    room = await room_store.create_room('سامي', sanitize_settings({'players': 0}), 'node', 'c1', uid)
    entry = await room_store.append_chat(room['roomId'], 0, 'c1', 1, 'مرحبا', chat_bubble='chat_mist')
    assert (await room_store.chat_history(room['roomId']))[0]['chatBubble'] == 'chat_mist'
    try:
        await room_store.append_chat(room['roomId'], 0, 'stale', 1, 'غير مسموح', chat_bubble='chat_ember')
    except StoreError as error:
        assert error.code == 'STALE_CONNECTION'
    else:
        raise AssertionError('stale connection accepted')
    print('COSMETIC_STORE_REGRESSION_PASS')

asyncio.run(main())
