"""External worker against real authenticated WS + authoritative pool; no production."""
import asyncio,json,os,subprocess,sys,time,tempfile
from pathlib import Path
import aiohttp
from aiohttp import web
from multigame_ws import ROOT,GH_PORT,GH,app,receive
WORKER=ROOT.parent/'experiments/pool-bots/worker.py'
async def wait_event(socket,predicate,timeout=20):
 async def read():
  while True:
   raw=await socket.receive();assert raw.type==aiohttp.WSMsgType.TEXT,raw
   value=json.loads(raw.data)
   if predicate(value):return value
 return await asyncio.wait_for(read(),timeout)
async def main():
 sessions=[];sockets=[];runner=None;worker=None
 process=subprocess.Popen(['node',str(ROOT/'gamehost/server.js')],cwd=ROOT,env=dict(os.environ,SAMIDEV_GAMEHOST_HOST='127.0.0.1',SAMIDEV_GAMEHOST_PORT=str(GH_PORT)),stdout=subprocess.DEVNULL)
 worker_log=(Path(tempfile.gettempdir())/'pool-agent-integration.log').open('w')
 def client():
  s=aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True),headers={'Origin':'http://localhost'});sessions.append(s);return s
 try:
  probe=client()
  for _ in range(100):
   try:
    async with probe.get(GH+'/health') as response:
     if response.status==200:break
   except aiohttp.ClientError:pass
   await asyncio.sleep(.05)
  runner=web.AppRunner(app.make_app());await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start();base='http://127.0.0.1:'+str(site._server.sockets[0].getsockname()[1]);app.ALLOWED_ORIGINS.add(base)
  platform=app.SERVICE.platform
  admin=await platform.create_user('PoolAgentAdmin','Test-password-123',role='admin');token=await platform.create_session(admin['id'])
  async with aiohttp.ClientSession(cookies={'samidev_session':token}) as admin_client:
   async with admin_client.post(base+'/api/admin/bots',json={'room':'square','addCount':2,'enabled':True}) as response:assert response.status==200
   async with admin_client.get(base+'/api/admin/bots') as response:bots=(await response.json())['bots']
   for bot in bots:
    async with admin_client.patch(base+'/api/admin/bots/'+bot['id'],json={'skill':'expert'}) as response:assert response.status==200
  humans=[]
  for i in range(3):
   s=client()
   async with s.post(base+'/api/auth/register',json={'username':'HumanPoolAgent'+str(i),'password':'Test-password-123'}) as response:assert response.status==200
   if i==0:
    async with s.post(base+'/api/game-ticket',json={'communityId':'square'}) as response:ticket=(await response.json())['ticket']
    socket=await s.ws_connect(base+'/ws?ticket='+ticket)
   else:socket=await s.ws_connect(base+'/ws')
   sockets.append(socket);humans.append(socket)
  # A simultaneous human-only match must remain untouched by the agent process.
  await humans[1].send_json({'type':'create_room','settings':{'gameId':'pool','players':1,'break':0}})
  control=(await receive(humans[1],'created'))['roomId']
  await humans[2].send_json({'type':'join_room','roomId':control});await receive(humans[2],'joined')
  for socket in humans[1:]:await receive(socket,'start');await socket.send_json({'type':'runtime_ready'})
  for socket in humans[1:]:await receive(socket,'begin_match')
  before=(await app.SERVICE.gamehost.state(control))['pool']
  await humans[0].send_json({'type':'create_room','settings':{'gameId':'pool','players':1,'break':1}})
  target=(await receive(humans[0],'created'))['roomId']
  assert (await app.SERVICE.store.get_room_state(target))['communityId']=='square'
  worker=await asyncio.create_subprocess_exec(sys.executable,str(WORKER),'--base-url',base,'--enable-play','--join-after','0','--max-games','1','--test-time-scale','.04',env=dict(os.environ,PLAZR_POOL_WORKER_ADMIN_SESSION=token),stdout=worker_log,stderr=worker_log)
  start=await wait_event(humans[0],lambda d:d.get('type')=='start',20);assert start['snapshot']['pool']['turn']==[1],start['snapshot']['pool']
  await humans[0].send_json({'type':'runtime_ready'});await receive(humans[0],'begin_match')
  observed=[];shot=None
  for _ in range(14):
   event=await wait_event(humans[0],lambda d:d.get('type') in ('move','error'),20)
   assert event['type']=='move',event
   observed.append(event['packet']['m'])
   if event['packet']['m'].get('a')==1:shot=event;break
  assert shot and sum(m.get('a')==3 for m in observed)>=3 and any(m.get('a')==4 for m in observed),observed
  after=(await app.SERVICE.gamehost.state(control))['pool'];assert after==before
  state=(await app.SERVICE.gamehost.state(target))['pool'];assert state['balls']!=start['snapshot']['pool']['balls']
  # Stop only the external process. Main server/physics are left running.
  worker.terminate();await asyncio.wait_for(worker.wait(),15);assert worker.returncode in ((0,1) if os.name=='nt' else (0,))
  await humans[1].send_json({'type':'move','packet':{'i':'human-ready','n':0,'m':{'__ready':1}}});assert (await receive(humans[1],'move'))['type']=='move';await receive(humans[2],'move')
  await humans[1].send_json({'type':'move','packet':{'i':'human-shot','n':1,'m':{'a':1,'st':.8,'an':-1.5707963267948966,'sp':[0,0]}}})
  event=await receive(humans[1],'move');assert event['type']=='move',event;assert (await receive(humans[2],'move'))['type']=='move'
  async with probe.get(base+'/health') as response:assert response.status==200
  print('POOL_BOT_BRIDGE_PASS: separate process; normal authenticated WS; auto-join; ready; three aim previews; power preview; real physical shot; simultaneous human match unchanged; human shot succeeds after worker shutdown')
 finally:
  if worker and worker.returncode is None:worker.kill();await worker.wait()
  worker_log.close()
  for socket in sockets:await socket.close()
  if runner:await runner.cleanup()
  for session in sessions:await session.close()
  process.terminate()
  try:process.wait(timeout=3)
  except subprocess.TimeoutExpired:process.kill();process.wait()
if __name__=='__main__':asyncio.run(main())
