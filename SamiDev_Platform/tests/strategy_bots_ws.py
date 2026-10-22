"""Multigame worker end-to-end against isolated memory backend; never production accounts."""
import asyncio,json,os,subprocess,sys,tempfile
from pathlib import Path
import aiohttp
from aiohttp import web
from multigame_ws import ROOT,GH_PORT,GH,app,receive
from pool_bot_bridge_ws import wait_event,WORKER
async def main():
 process=subprocess.Popen(['node',str(ROOT/'gamehost/server.js')],cwd=ROOT,env=dict(os.environ,SAMIDEV_GAMEHOST_HOST='127.0.0.1',SAMIDEV_GAMEHOST_PORT=str(GH_PORT)),stdout=subprocess.DEVNULL)
 runner=None;worker=None;sessions=[];logpath=Path(tempfile.gettempdir())/'multigame-worker-test.log';log=logpath.open('w')
 try:
  async with aiohttp.ClientSession() as probe:
   for _ in range(100):
    try:
     async with probe.get(GH+'/health') as response:
      if response.status==200:break
    except aiohttp.ClientError:pass
    await asyncio.sleep(.1)
  runner=web.AppRunner(app.make_app());await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start();base='http://127.0.0.1:'+str(site._server.sockets[0].getsockname()[1]);app.ALLOWED_ORIGINS.add(base)
  platform=app.SERVICE.platform;admin=await platform.create_user('StrategyAdmin','Test-password-123',role='admin');token=await platform.create_session(admin['id'])
  async with aiohttp.ClientSession(cookies={'samidev_session':token}) as a:
   async with a.post(base+'/api/admin/bots',json={'room':'square','addCount':4,'enabled':True}) as resp:assert resp.status==200
  worker=await asyncio.create_subprocess_exec(sys.executable,str(WORKER),'--base-url',base,'--enable-play','--join-after','0','--max-games','3','--test-time-scale','.1',env=dict(os.environ,PLAZR_POOL_WORKER_ADMIN_SESSION=token),stdout=log,stderr=log)
  for gid in ['crazy8','carrom']:
   user=await platform.create_user('Human_'+gid,'Test-password-123');t=await platform.create_session(user['id'])
   session=aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True),cookies={'samidev_session':t},headers={'Origin':base});sessions.append(session)
   async with session.post(base+'/api/game-ticket',json={'communityId':'square'}) as resp:ticket=(await resp.json())['ticket']
   async with session.ws_connect(base+'/ws?ticket='+ticket) as ws:
    await ws.send_json({'type':'create_room','settings':{'gameId':gid,'players':0,'seats':0,'special':0,'live':1,'gamemode':0,'break':0}})
    created=await receive(ws,'created');rid=created['roomId'];start=await wait_event(ws,lambda d:d.get('type')=='start',30)
    await ws.send_json({'type':'runtime_ready'});await receive(ws,'begin_match')
    observed=False
    for step in range(12):
     state=await app.SERVICE.gamehost.state(rid);turn=state['turn']
     if turn==[1]:
      event=await wait_event(ws,lambda d:d.get('type')=='move' and d.get('seat')==1,30);observed=True;break
     move={'d':1} if gid=='crazy8' else ({'m':0} if not turn else {'m':5,'ps':.5,'i':[0,-500]})
     await ws.send_json({'type':'move','packet':{'i':gid+str(step),'n':state['sequence'][0],'m':move}})
     event=await wait_event(ws,lambda d:d.get('type') in ('move','error'),30);assert event['type']=='move',event
     if event.get('seat')==1:observed=True;break
    assert observed,gid+' bot did not play'
    print(gid,'AUTHENTICATED_BOT_MOVE_PASS',flush=True)
 finally:
  if worker and worker.returncode is None:worker.kill();await worker.wait()
  if runner:await runner.cleanup()
  for s in sessions:await s.close()
  process.terminate();process.wait(timeout=5);log.close()
if __name__=='__main__':asyncio.run(main())
