import asyncio,os,subprocess,sys
os.environ.update(SAMIDEV_PLATFORM_STORE='memory',SAMIDEV_FIREBASE_AUTH='0',SAMIDEV_PRODUCTION='0',SAMIDEV_TRUST_PROXY='1',SAMIDEV_ADMIN_USERNAME='',SAMIDEV_ADMIN_PASSWORD='')
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from multigame_ws import ROOT,GH_PORT,GH,app
from aiohttp import ClientSession,web
async def main():
 from room_policy import DEFAULTS
 await app.SERVICE.platform.room_policy.configure('majlis',{**DEFAULTS,'cooldownSeconds':0})
 for game in ['pool','carrom','crazy8','tablesoccer']:
  for i in range(3 if game=='pool' else 2):await app.SERVICE.platform.create_user(f'perf_{game}_{i}','Test-password-123')
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
  runner=web.AppRunner(app.make_app());await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start();base=f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}';app.ALLOWED_ORIGINS.add(base)
  child=await asyncio.create_subprocess_exec('node',str(ROOT/'tests/spa_game_host_browser.mjs'),env=dict(os.environ,SAMIDEV_TEST_BASE_URL=base))
  assert await child.wait()==0
 finally:
  if runner:await runner.cleanup()
  proc.terminate();proc.wait(timeout=10)
asyncio.run(main())
