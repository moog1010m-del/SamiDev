"""Two external bot clients complete a real match and earn ordinary account progression."""
import asyncio,json,os,subprocess,sys,tempfile
from pathlib import Path
import aiohttp
from aiohttp import web
from multigame_ws import ROOT,GH_PORT,GH,app
async def main():
 worker=None;runner=None;sessions=[];log=(Path(tempfile.gettempdir())/'pool-bot-selfplay-worker.log').open('w')
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
   async with client.post(base+'/api/admin/bots',json={'room':'majlis','addCount':2,'enabled':True}) as response:assert response.status==200
   async with client.get(base+'/api/admin/bots') as response:bots=(await response.json())['bots']
   for bot in bots:
    async with client.patch(base+'/api/admin/bots/'+bot['id'],json={'skill':'expert'}) as response:assert response.status==200
   worker=await asyncio.create_subprocess_exec(sys.executable,str(ROOT.parent/'experiments/pool-bots/worker.py'),'--base-url',base,'--enable-play','--bot-vs-bot','--selfplay-per-room','2','--reserve-per-room','0','--join-after','0','--max-games','1','--test-time-scale','.01',env=dict(os.environ,PLAZR_POOL_WORKER_ADMIN_SESSION=token),stdout=log,stderr=log)
   completed=None
   for _ in range(600):
    for room in app.SERVICE.store.rooms.values():
     state=await app.SERVICE.store.get_room_state(room.room_id)
     if state.get('finished'):completed=state;break
    if completed:break
    assert worker.returncode is None,'worker exited before completing match'
    await asyncio.sleep(.2)
   assert completed,'No completed real match within 120 seconds'
   # Awards run after the authoritative result is committed.
   for _ in range(30):
    users=[await p.get_user(bot['id']) for bot in bots]
    if sum(int(u.get('wins','0')) for u in users)==1:break
    await asyncio.sleep(.1)
   assert sum(int(u.get('wins','0')) for u in users)==1
   statistics=[await p.game_statistics(bot['id']) for bot in bots]
   assert all(next(s for s in stats if s['gameId']=='pool')['played']==1 for stats in statistics)
   assert all(int(u.get('coins','0'))>=50 for u in users)
   async with client.get(base+'/api/admin/bots') as response:roster=await response.json()
   assert all(bot['poolPlayed']==1 for bot in roster['bots'])
   worker.terminate();await asyncio.wait_for(worker.wait(),15);assert worker.returncode==0
   state=await app.SERVICE.gamehost.state(completed['roomId']);assert state['gameOver']
   print(json.dumps({'case':'POOL_BOT_SELFPLAY_PASS','moves':completed['moveCount'],'winner':state['finishOrder'][0],'accountWins':[u['wins'] for u in users],'ordinaryRewards':True,'unchangedPhysics':True}))
 finally:
  if worker and worker.returncode is None:worker.kill();await worker.wait()
  log.close()
  if runner:await runner.cleanup()
  process.terminate()
  try:process.wait(timeout=3)
  except subprocess.TimeoutExpired:process.kill();process.wait()
if __name__=='__main__':asyncio.run(main())
