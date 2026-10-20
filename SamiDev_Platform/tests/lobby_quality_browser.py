"""Real lobby UI audit against isolated memory accounts; no production services."""
import asyncio, os, sys
from pathlib import Path
os.environ.update(SAMIDEV_STORE='memory',SAMIDEV_PLATFORM_STORE='memory',SAMIDEV_FIREBASE_AUTH='0',SAMIDEV_PUSH_ENABLED='0')
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
from aiohttp import web
import app
async def main():
    application=app.make_app();application.on_startup.clear();application.on_cleanup.clear()
    peer=await app.SERVICE.platform.firebase_account({'uid':'quality-peer','email':'peer@example.test'},username='Audit_Peer')
    await app.SERVICE.platform.touch_community(peer['id'],'majlis')
    runner=web.AppRunner(application);await runner.setup()
    try:
        site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
        base='http://127.0.0.1:'+str(site._server.sockets[0].getsockname()[1])
        child=await asyncio.create_subprocess_exec('node',str(ROOT/'tests/lobby_quality_browser.mjs'),env=dict(os.environ,SAMIDEV_TEST_BASE_URL=base))
        assert await child.wait()==0
    finally:await runner.cleanup()
if __name__=='__main__':asyncio.run(main())
