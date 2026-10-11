from __future__ import annotations

import asyncio
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))

from aiohttp import web
from aiohttp.test_utils import make_mocked_request
import app as backend_app

from social_platform import (
    PlatformService,
    PlatformError,
    COMMUNITY_CHAT_USER_RATE,
    COMMUNITY_CHAT_ROOM_RATE,
    COMMUNITY_CHAT_RATE_WINDOW,
)


async def expect_error(coro, code: str):
    try:
        await coro
    except PlatformError as exc:
        assert exc.code == code, (exc.code, code)
        return
    raise AssertionError(f'expected {code}')


async def main():
    platform = PlatformService(None)
    user = await platform.create_user('secure_chat_user', 'Test-password-123', 'لاعب آمن')
    uid = user['id']

    # HTML/XSS-shaped payloads remain plain text in storage; the client must render them with textContent.
    xss1 = '<script>globalThis.PWNED=1</script>'
    xss2 = '<img src=x onerror=alert(1)>'
    e1 = await platform.append_community_chat(uid, 'majlis', xss1)
    e2 = await platform.append_community_chat(uid, 'majlis', xss2)
    assert e1['text'] == xss1
    assert e2['text'] == xss2

    # Bidi override and zero-width format characters (Unicode Cf) are removed server-side.
    bidi = await platform.append_community_chat(uid, 'majlis', 'abc\u202EDEF')
    zwsp = await platform.append_community_chat(uid, 'majlis', 'one\u200Btwo')
    assert '\u202E' not in bidi['text'] and bidi['text'] == 'abcDEF'
    assert '\u200B' not in zwsp['text'] and zwsp['text'] == 'onetwo'

    # 10k payload must be rejected instead of silently truncating it.
    await expect_error(platform.append_community_chat(uid, 'majlis', 'A' * 10_000), 'CHAT_TOO_LONG')

    # Unknown/forged community ids are rejected by the allowlist.
    await expect_error(platform.append_community_chat(uid, '../../admin', 'hello'), 'BAD_COMMUNITY')

    # User-scoped and room-scoped flood buckets both trip after their configured limits.
    for _ in range(COMMUNITY_CHAT_USER_RATE):
        assert await platform.allow_rate('test-user-bucket', COMMUNITY_CHAT_USER_RATE, COMMUNITY_CHAT_RATE_WINDOW)
    assert not await platform.allow_rate('test-user-bucket', COMMUNITY_CHAT_USER_RATE, COMMUNITY_CHAT_RATE_WINDOW)

    for _ in range(COMMUNITY_CHAT_ROOM_RATE):
        assert await platform.allow_rate('test-room-bucket', COMMUNITY_CHAT_ROOM_RATE, COMMUNITY_CHAT_RATE_WINDOW)
    assert not await platform.allow_rate('test-room-bucket', COMMUNITY_CHAT_ROOM_RATE, COMMUNITY_CHAT_RATE_WINDOW)

    client = (ROOT / 'game' / 'platform' / 'platform.js').read_text('utf-8')
    app = (ROOT / 'backend' / 'app.py').read_text('utf-8')
    assert "text.textContent=String(m.text||'')" in client
    assert "name.textContent=String(m.displayName||m.username||'Player')" in client
    assert 'communityMessages.map' not in client or 'communityMessages.map(m=>`<article' not in client
    assert 'platform_origin_middleware' in app
    assert 'Sec-Fetch-Site' in app and 'ORIGIN_FORBIDDEN' in app

    # Origin middleware: cross-site/foreign origin is rejected, configured same-origin passes.
    original_origins, original_prod = backend_app.ALLOWED_ORIGINS, backend_app.PRODUCTION_MODE
    backend_app.ALLOWED_ORIGINS = {'https://game.example.com'}
    backend_app.PRODUCTION_MODE = True
    try:
        async def ok_handler(request):
            return web.json_response({'ok': True})
        bad_req = make_mocked_request('POST', '/api/profile', headers={'Origin':'https://evil.example','Sec-Fetch-Site':'cross-site'}).clone(scheme='https')
        bad_resp = await backend_app.platform_origin_middleware(bad_req, ok_handler)
        assert bad_resp.status == 403
        good_req = make_mocked_request('POST', '/api/profile', headers={'Origin':'https://game.example.com','Sec-Fetch-Site':'same-origin'}).clone(scheme='https')
        good_resp = await backend_app.platform_origin_middleware(good_req, ok_handler)
        assert good_resp.status == 200
        missing_req = make_mocked_request('POST', '/api/profile').clone(scheme='https')
        missing_resp = await backend_app.platform_origin_middleware(missing_req, ok_handler)
        assert missing_resp.status == 403
    finally:
        backend_app.ALLOWED_ORIGINS, backend_app.PRODUCTION_MODE = original_origins, original_prod

    print('COMMUNITY_CHAT_SECURITY_V18_PASS')


if __name__ == '__main__':
    asyncio.run(main())
