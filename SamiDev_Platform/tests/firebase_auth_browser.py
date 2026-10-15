"""Real Chromium + local HTTP auth; Google responses replaced in the test browser."""
import asyncio
import os
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock
from aiohttp import web
from aiohttp.test_utils import TestServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
os.environ['SAMIDEV_FIREBASE_AUTH'] = '0'
os.environ['SAMIDEV_STORE'] = 'memory'
os.environ['SAMIDEV_PLATFORM_STORE'] = 'memory'
os.environ['SAMIDEV_PRODUCTION'] = '0'
from social_platform import PlatformService, PlatformHttp, PlatformError
from firebase_identity import FirebaseFailure
import app as application

async def main():
    service = PlatformService()
    service.firebase.enabled = True
    service.firebase.project = 'browser-test'
    service.firebase.api_key = 'public-fixture'
    service.firebase.admin_uid = ''
    service.firebase.session_valid = AsyncMock(return_value=True)
    async def verify(token):
        if token not in {'fixture-verified', 'fixture-new'}:
            raise FirebaseFailure('EMAIL_NOT_VERIFIED', 'وثق بريدك', 403)
        return dict(uid='browser-user' if token == 'fixture-verified' else 'new-browser-user', email='browser@example.test', email_verified=True, auth_time=int(time.time()))
    service.firebase.verify = verify
    # Use the actual production CSP and route handlers, not a permissive test CSP.
    application.SERVICE.platform = service
    api = PlatformHttp(service, None)
    old = await service.create_user('old_browser', 'Original-password-123')
    old['coins'] = '777'
    @web.middleware
    async def errors(request, handler):
        try: return await handler(request)
        except PlatformError as e:
            return web.json_response({'ok':False,'error':e.code,'message':e.message}, status=e.status)
    server_app = web.Application(middlewares=[errors])
    server_app.on_response_prepare.append(application.security_headers)
    server_app.router.add_get('/api/auth/config', api.auth_config)
    server_app.router.add_post('/api/auth/guest', api.guest)
    server_app.router.add_patch('/api/profile', api.profile_update)
    server_app.router.add_get('/api/store', api.store_state)
    server_app.router.add_post('/api/store/buy', api.store_buy)
    server_app.router.add_post('/api/auth/firebase', api.firebase_exchange)
    server_app.router.add_post('/api/auth/login', api.login)
    server_app.router.add_post('/api/auth/logout', api.logout)
    server_app.router.add_get('/api/me', api.me)
    async def seed_guest(request):
        user=await api._user(request);user['coins']='500'
        await service.grant_store_item(user['id'],'badge_ember')
        return web.json_response({'ok':True})
    server_app.router.add_post('/fixture/seed',seed_guest)
    async def unused(request): return web.json_response({'ok':True,'friends':[],'requests':[],'communities':[],'rooms':[]})
    server_app.router.add_get('/api/{tail:.*}', unused)
    async def index(request): return web.FileResponse(ROOT / 'game/platform/index.html')
    server_app.router.add_get('/platform/', index)
    server_app.router.add_static('/', ROOT / 'game')
    async with TestServer(server_app) as server:
        env = dict(os.environ, SAMIDEV_TEST_BASE_URL=str(server.make_url('')))
        process = await asyncio.create_subprocess_exec('node',str(ROOT/'tests/firebase_auth_browser.mjs'),env=env)
        assert await process.wait() == 0, 'Browser assertions failed'
        unchanged = await service.get_user(old['id'])
        assert not unchanged.get('firebaseUid') and unchanged['coins'] == '777'
        assert len(service.mem_firebase)==2, 'Expected two linked Firebase identities; old test account untouched'
    print('FIREBASE_BROWSER_HTTP_PASS: new profiles, no old account migration')

if __name__ == '__main__': asyncio.run(main())
