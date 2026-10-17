import asyncio,os,subprocess,sys
os.environ.update(SAMIDEV_PLATFORM_STORE='memory',SAMIDEV_FIREBASE_AUTH='0',SAMIDEV_PRODUCTION='0',SAMIDEV_TRUST_PROXY='1',SAMIDEV_ADMIN_USERNAME='',SAMIDEV_ADMIN_PASSWORD='')
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from multigame_ws import ROOT,GH_PORT,GH,app
from aiohttp import ClientSession,web
async def main():
 for game in ['pool','carrom','crazy8','tablesoccer']:
  for i in range(2):await app.SERVICE.platform.create_user(f'perf_{game}_{i}','Test-password-123')
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
  application=app.make_app()
  if os.getenv('JOIN_SHARED_HOST')=='1':
   @web.middleware
   async def shared_game_host(request,handler):
    if request.path in {'/index.html','/games/pool/index.html','/games/crazy8/index.html','/games/tablesoccer/index.html'} and request.method in {'GET','HEAD'}:return web.FileResponse(ROOT/'game/game-host.html')
    return await handler(request)
   application.middlewares.append(shared_game_host)
  runner=web.AppRunner(application);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start();base=f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}';app.ALLOWED_ORIGINS.add(base)
  child=await asyncio.create_subprocess_exec('node',str(ROOT/'tests/game_join_browser.mjs'),env=dict(os.environ,SAMIDEV_TEST_BASE_URL=base))
  assert await child.wait()==0
 finally:
  if runner:await runner.cleanup()
  proc.terminate();proc.wait(timeout=10)
asyncio.run(main())
