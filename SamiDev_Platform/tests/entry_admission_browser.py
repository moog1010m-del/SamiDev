"""Real admission failures must stay in the lobby for every game."""
import asyncio,os,subprocess,sys
from pathlib import Path
os.environ.update(SAMIDEV_PLATFORM_STORE='memory',SAMIDEV_FIREBASE_AUTH='0',SAMIDEV_PRODUCTION='0',SAMIDEV_ADMIN_USERNAME='',SAMIDEV_ADMIN_PASSWORD='')
sys.path.insert(0,str(Path(__file__).resolve().parent))
from multigame_ws import ROOT,GH_PORT,GH,app
from aiohttp import ClientSession,web
async def main():
 for game in ['pool','carrom','crazy8','tablesoccer']:
  await app.SERVICE.platform.create_user('entry_'+game,'Test-password-123')
  await app.SERVICE.platform.create_user('join_'+game,'Test-password-123')
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
  testapp=app.make_app()
  async def cooldown(request):
   body=await request.json();uid=body['uid']
   assert await app.SERVICE.platform.get_user(uid)
   until=await app.SERVICE.room_policy.clock()+60000 if body['enabled'] else 0
   await app.SERVICE.room_policy.write('cooldown:'+uid,until)
   return web.json_response({'ok':True})
  # Test-only control; never registered by production app.make_app().
  testapp.router.add_post('/__test/entry-cooldown',cooldown)
  runner=web.AppRunner(testapp);await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
  base=f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}';app.ALLOWED_ORIGINS.add(base)
  child=await asyncio.create_subprocess_exec('node',str(ROOT/'tests/entry_admission_browser.mjs'),env=dict(os.environ,SAMIDEV_TEST_BASE_URL=base))
  assert await child.wait()==0
 finally:
  if runner:await runner.cleanup()
  proc.terminate();proc.wait(timeout=10)
asyncio.run(main())
