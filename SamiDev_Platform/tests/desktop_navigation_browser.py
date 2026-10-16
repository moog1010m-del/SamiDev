"""Responsive desktop navigation against actual local platform handlers."""
import asyncio, os, sys
from pathlib import Path
from aiohttp import web
from aiohttp.test_utils import TestServer
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.environ.update(SAMIDEV_STORE='memory',SAMIDEV_PLATFORM_STORE='memory',SAMIDEV_FIREBASE_AUTH='0',SAMIDEV_PRODUCTION='0')
from social_platform import PlatformService,PlatformHttp,PlatformError
from store import MemoryStore
from account_security import AccountSecurityHttp
import app as application
async def main():
    service=PlatformService();api=PlatformHttp(service,MemoryStore())
    application.SERVICE.platform=service
    @web.middleware
    async def errors(request,handler):
        try:return await handler(request)
        except PlatformError as e:return web.json_response({'ok':False,'error':e.code,'message':e.message},status=e.status)
    app=web.Application(middlewares=[errors])
    app.on_response_prepare.append(application.security_headers)
    AccountSecurityHttp(api).install(app.router)
    app.router.add_get('/api/auth/config',api.auth_config)
    app.router.add_get('/api/me',api.me)
    app.router.add_post('/api/auth/guest',api.guest)
    app.router.add_get('/api/communities',api.communities)
    app.router.add_post('/api/heartbeat',api.heartbeat)
    app.router.add_get('/api/store',api.store_state)
    app.router.add_get('/api/public-profile/{user_id}',api.public_profile)
    async def unused(request):return web.json_response({'ok':True,'friends':[],'requests':[]})
    app.router.add_route('*','/api/{tail:.*}',unused)
    app.router.add_get('/platform/',lambda request:web.FileResponse(ROOT/'game/platform/index.html'))
    app.router.add_static('/',ROOT/'game')
    async with TestServer(app) as server:
        proc=await asyncio.create_subprocess_exec('node',str(ROOT/'tests/desktop_navigation_browser.mjs'),env=dict(os.environ,SAMIDEV_TEST_BASE_URL=str(server.make_url(''))))
        assert await proc.wait()==0,'Desktop navigation failed'
if __name__=='__main__':asyncio.run(main())
