"""Real authenticated HTTP/SSE + browser regression for the private workspace."""
import asyncio,os,sys
from pathlib import Path
os.environ.update(SAMIDEV_STORE='memory',SAMIDEV_PLATFORM_STORE='memory',SAMIDEV_FIREBASE_AUTH='0',SAMIDEV_PUSH_ENABLED='0')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from aiohttp import web
import app
from social_platform import PlatformHttp
from direct_messages import DirectHttp
async def main():
 api=PlatformHttp(app.SERVICE.platform,app.SERVICE.store)
 application=web.Application(middlewares=[app.platform_error_middleware]);application.on_response_prepare.append(app.security_headers)
 DirectHttp(api).install(application)
 for method,path,handler in [('GET','/api/me',api.me),('POST','/api/auth/guest',api.guest),('GET','/api/friends',api.friends),('POST','/api/friends/request',api.friend_request),('POST','/api/friends/respond',api.friend_respond),('POST','/api/heartbeat',api.heartbeat),('GET','/api/store',api.store_state),('GET','/api/communities',api.communities),('GET','/api/auth/config',api.auth_config),('GET','/api/public-profile/{user_id}',api.public_profile),('GET','/api/avatar/{user_id}',api.avatar_image)]:
  application.router.add_route(method,path,handler)
 application.router.add_get('/platform/',app.SERVICE.index)
 application.router.add_get('/api/build',app.SERVICE.ui_build)
 application.router.add_get('/api/games',app.SERVICE.game_catalog)
 application.router.add_get('/{path:.*}',app.SERVICE.static_game)
 runner=web.AppRunner(application);await runner.setup()
 try:
  site=web.TCPSite(runner,'127.0.0.1',0);await site.start();base=f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'
  child=await asyncio.create_subprocess_exec('node',str(ROOT/'tests/friends_browser.mjs'),env=dict(os.environ,SAMIDEV_TEST_BASE_URL=base))
  assert await child.wait()==0
 finally:
  await app.SERVICE.platform.direct.close();await runner.cleanup()
asyncio.run(main())
