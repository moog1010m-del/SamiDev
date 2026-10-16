"""Chromium over real local HTTP. Firebase SDK network is replaced only in tests."""
import asyncio
import os
import secrets
import sys
import time
from pathlib import Path
from unittest.mock import AsyncMock
from aiohttp import web
from aiohttp.test_utils import TestServer

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.environ.update(SAMIDEV_FIREBASE_AUTH='0',SAMIDEV_STORE='memory',SAMIDEV_PLATFORM_STORE='memory',SAMIDEV_PRODUCTION='0',SAMIDEV_PLATFORM_PREFIX='accountbrowser'+secrets.token_hex(6))
from social_platform import PlatformService,PlatformHttp,PlatformError
from account_security import AccountSecurityHttp
import app as application


async def main():
    service=PlatformService()
    service.firebase.enabled=True;service.firebase.project='settings-browser';service.firebase.api_key='public-fixture'
    service.firebase.session_valid=AsyncMock(return_value=True)
    async def verify(token):
        assert token in {'token-a','token-b'}
        return dict(uid=token,email=token+'@example.test',email_verified=True,auth_time=int(time.time()))
    service.firebase.verify=verify
    async def info(uid):
        return {'email':uid+'@example.test','providers':['password'] if uid=='token-a' else ['google.com']}
    service.firebase.account_info=info
    service.firebase.delete_user=AsyncMock()
    a=await service.firebase_account(await verify('token-a'),username='Saved_Player')
    b=await service.firebase_account(await verify('token-b'),username='Google_Player')
    cookies=[]
    for user,device in [(a,'iPhone'),(a,'Windows'),(b,'Android')]:
        cookies.append(await service.create_session(user['id'],firebase_auth_time=int(time.time()),metadata={'device':device,'client':'تطبيق SamiDev' if device!='Windows' else 'Chrome','country':'SA' if device=='iPhone' else ''}))
    application.SERVICE.platform=service
    api=PlatformHttp(service,None)
    @web.middleware
    async def errors(request,handler):
        try:return await handler(request)
        except PlatformError as e:return web.json_response({'ok':False,'error':e.code,'message':e.message},status=e.status)
    app=web.Application(middlewares=[errors])
    app.on_response_prepare.append(application.security_headers)
    AccountSecurityHttp(api).install(app.router)
    app.router.add_get('/api/auth/config',api.auth_config)
    app.router.add_get('/api/me',api.me)
    app.router.add_patch('/api/profile',api.profile_update)
    app.router.add_post('/api/auth/guest',api.guest)
    app.router.add_post('/api/auth/logout',api.logout)
    async def unused(request):return web.json_response({'ok':True,'friends':[],'requests':[],'communities':[],'rooms':[]})
    app.router.add_route('*','/api/{tail:.*}',unused)
    app.router.add_get('/platform/',lambda request:web.FileResponse(ROOT/'game/platform/index.html'))
    app.router.add_static('/',ROOT/'game')
    async with TestServer(app) as server:
        process=await asyncio.create_subprocess_exec('node',str(ROOT/'tests/account_settings_browser.mjs'),env=dict(os.environ,SAMIDEV_TEST_BASE_URL=str(server.make_url('')),SAMIDEV_TEST_COOKIES='|'.join(cookies)))
        assert await process.wait()==0,'Browser account controls failed'
    assert [call.args[0] for call in service.firebase.delete_user.await_args_list]==['token-a','token-b']
    assert await service.get_user(a['id']) is None
    assert await service.get_user(b['id']) is None
    print('ACCOUNT_SETTINGS_REAL_HTTP_BROWSER_PASS')


if __name__=='__main__':asyncio.run(main())
