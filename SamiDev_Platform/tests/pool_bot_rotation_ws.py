"""Reserved bots join humans while independent self-play tables remain active."""
import asyncio,json,os,subprocess,sys,tempfile
from pathlib import Path
import aiohttp
from aiohttp import web
from multigame_ws import ROOT,GH_PORT,GH,app
async def main():
 worker=None;runner=None;sessions=[];log=(Path(tempfile.gettempdir())/'pool-bot-rotation-worker.log').open('w')
 process=subprocess.Popen(['node',str(ROOT/'gamehost/server.js')],cwd=ROOT,env=dict(os.environ,SAMIDEV_GAMEHOST_HOST='127.0.0.1',SAMIDEV_GAMEHOST_PORT=str(GH_PORT)),stdout=subprocess.DEVNULL)
 try:
  async with aiohttp.ClientSession() as probe:
   for _ in range(100):
    try:
     async with probe.get(GH+'/health') as response:
      if response.status==200:break
    except aiohttp.ClientError:pass
    await asyncio.sleep(.05)
  runner=web.AppRunner(app.make_app());await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start();base='http://127.0.0.1:'+str(site._server.sockets[0].getsockname()[1]);app.ALLOWED_ORIGINS.add(base)
  p=app.SERVICE.platform;admin=await p.create_user('SelfplayAdmin','Test-password-123',role='admin');token=await p.create_session(admin['id'])
  async with aiohttp.ClientSession(cookies={'samidev_session':token}) as client:
   async with client.post(base+'/api/admin/bots',json={'room':'majlis','addCount':6,'enabled':True}) as response:assert response.status==200
   async with client.get(base+'/api/admin/bots') as response:bots=(await response.json())['bots']
   for bot in bots:
    async with client.patch(base+'/api/admin/bots/'+bot['id'],json={'skill':'expert'}) as response:assert response.status==200
   worker=await asyncio.create_subprocess_exec(sys.executable,str(ROOT.parent/'experiments/pool-bots/worker.py'),'--base-url',base,'--enable-play','--bot-vs-bot','--selfplay-per-room','4','--reserve-per-room','2','--join-after','0','--max-games','4',env=dict(os.environ,PLAZR_POOL_WORKER_ADMIN_SESSION=token),stdout=log,stderr=log)
   for _ in range(100):
    async with client.get(base+'/api/admin/bots') as response:status=(await response.json())['playWorker']
    if status.get('selfPlayingBots')==4 and status.get('readyBots')==2:break
    assert worker.returncode is None
    await asyncio.sleep(.2)
   assert status.get('selfPlayingBots')==4 and status.get('readyBots')==2,status
   selfplay_ids=set(app.SERVICE.store.rooms)
   human=await p.create_user('RotationHuman','Test-password-123');human_token=await p.create_session(human['id'])
   async with aiohttp.ClientSession(cookies={'samidev_session':human_token},headers={'Origin':base}) as human_client:
    async with human_client.post(base+'/api/game-ticket',json={'communityId':'majlis'}) as response:ticket=(await response.json())['ticket']
    async with human_client.ws_connect(base+'/ws?ticket='+ticket) as socket:
     from multigame_ws import receive
     await socket.send_json({'type':'create_room','settings':{'gameId':'pool','players':1,'break':1},'communityId':'majlis','name':'RotationHuman'})
     rid=(await receive(socket,'created'))['roomId']
     await receive(socket,'start');await socket.send_json({'type':'runtime_ready'});await receive(socket,'begin_match')
     state=await app.SERVICE.store.get_room_state(rid)
     assert state['begun'] and len([p for p in state['roster'] if p])==2,state
     for _ in range(30):
      async with client.get(base+'/api/admin/bots') as response:status=(await response.json())['playWorker']
      if status.get('humanPlayingBots')==1:break
      await asyncio.sleep(.2)
     assert status.get('selfPlayingBots')==4 and status.get('humanPlayingBots')==1 and status.get('readyBots')==1,status
     for selfplay in selfplay_ids:
      assert (await app.SERVICE.store.get_room_state(selfplay))['begun']
     print(json.dumps({'case':'POOL_BOT_ROTATION_PASS','selfPlayingBots':4,'humanPlayingBots':1,'readyBots':1,'humanJoinedReservedBot':True,'ongoingSelfplayPreserved':True}))
   worker.terminate();await asyncio.wait_for(worker.wait(),15);assert (worker.returncode in (0,1) if os.name=='nt' else worker.returncode==0)

 finally:
  if worker and worker.returncode is None:worker.kill();await worker.wait()
  log.close()
  if runner:await runner.cleanup()
  process.terminate()
  try:process.wait(timeout=3)
  except subprocess.TimeoutExpired:process.kill();process.wait()
if __name__=='__main__':asyncio.run(main())
