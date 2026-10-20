"""Isolated web and mobile-web block/report and admin decisions."""
import asyncio,os,sys
from pathlib import Path
os.environ.update(SAMIDEV_STORE='memory',SAMIDEV_PLATFORM_STORE='memory',SAMIDEV_FIREBASE_AUTH='0',SAMIDEV_PUSH_ENABLED='0')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from aiohttp import web
import app
async def main():
 application=app.make_app();application.on_startup.clear();application.on_cleanup.clear()
 p=app.SERVICE.platform
 for i in range(2):await p.create_user('Report_Peer'+str(i),'Test-password-123')
 owner=await p.create_user('Review_Admin','Test-password-123',role='admin');token=await p.create_session(owner['id'])
 runner=web.AppRunner(application);await runner.setup()
 try:
  site=web.TCPSite(runner,'127.0.0.1',0);await site.start();base='http://127.0.0.1:'+str(site._server.sockets[0].getsockname()[1])
  child=await asyncio.create_subprocess_exec('node',str(ROOT/'tests/report_review_browser.mjs'),env=dict(os.environ,SAMIDEV_TEST_BASE_URL=base,SAMIDEV_TEST_ADMIN_COOKIE=token))
  assert await child.wait()==0
 finally:await runner.cleanup()
if __name__=='__main__':asyncio.run(main())
