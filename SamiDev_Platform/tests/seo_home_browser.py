"""Public landing renders without auth, game engines, or external requests."""
import asyncio,os,sys
from pathlib import Path
os.environ.update(SAMIDEV_STORE='memory',SAMIDEV_PLATFORM_STORE='memory',SAMIDEV_FIREBASE_AUTH='0')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from aiohttp import web
import app
async def main():
 application=web.Application();application.on_response_prepare.append(app.security_headers)
 application.router.add_get('/',app.SERVICE.landing);application.router.add_get('/{path:.*}',app.SERVICE.static_game)
 runner=web.AppRunner(application);await runner.setup()
 try:
  site=web.TCPSite(runner,'127.0.0.1',0);await site.start();base=f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'
  child=await asyncio.create_subprocess_exec('node',str(ROOT/'tests/seo_home_browser.mjs'),env=dict(os.environ,SAMIDEV_TEST_BASE_URL=base))
  assert await child.wait()==0
 finally:await runner.cleanup()
asyncio.run(main())
