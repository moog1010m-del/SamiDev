"""Two real web clients against isolated authenticated memory + native GameHost."""
import asyncio,os,subprocess
os.environ.update(SAMIDEV_PLATFORM_STORE='memory',SAMIDEV_FIREBASE_AUTH='0',SAMIDEV_TRUST_PROXY='1',SAMIDEV_PRODUCTION='0',SAMIDEV_ADMIN_USERNAME='',SAMIDEV_ADMIN_PASSWORD='')
from multigame_ws import ROOT,GH_PORT,GH,app
from aiohttp import ClientSession,web
async def main():
    service=app.SERVICE.platform
    for name,role in [('room_visual_admin','admin'),('room_visual_member','user')]:
        user=await service.create_user(name,'Test-password-123',role=role)
        if role=='user':
            user['coins']='10000'
            for item in ['badge_shard','chat_ember']:await service.buy_store_item(user['id'],item)
            await service.equip_store_item(user['id'],'chat_ember')
    proc=subprocess.Popen(['node',str(ROOT/'gamehost/server.js')],cwd=ROOT,env=dict(os.environ,SAMIDEV_GAMEHOST_HOST='127.0.0.1',SAMIDEV_GAMEHOST_PORT=str(GH_PORT)),stdout=subprocess.DEVNULL)
    runner=None
    try:
        async with ClientSession() as session:
            for _ in range(100):
                try:
                    async with session.get(GH+'/health') as r:
                        if r.status==200:break
                except OSError:pass
                await asyncio.sleep(.05)
            else:raise AssertionError('GameHost unavailable')
        runner=web.AppRunner(app.make_app());await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start();base=f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}';app.ALLOWED_ORIGINS.add(base)
        browser=await asyncio.create_subprocess_exec('node',str(ROOT/'tests/room_polish_browser.mjs'),env=dict(os.environ,SAMIDEV_TEST_BASE_URL=base))
        assert await browser.wait()==0
    finally:
        if runner:await runner.cleanup()
        proc.terminate();proc.wait(timeout=10)
if __name__=='__main__':asyncio.run(main())
