"""Pool integration through the platform's authenticated HTTP and WebSockets."""
import asyncio,json,os,subprocess
import aiohttp
from aiohttp import web
from multigame_ws import ROOT,GH_PORT,GH,app,receive

async def main():
 sessions=[];sockets=[];runner=None;results=[]
 proc=subprocess.Popen(['node',str(ROOT/'gamehost/server.js')],cwd=ROOT,env=dict(os.environ,SAMIDEV_GAMEHOST_HOST='127.0.0.1',SAMIDEV_GAMEHOST_PORT=str(GH_PORT)),stdout=subprocess.DEVNULL)
 def client():
  s=aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True),headers={'Origin':'http://localhost'});sessions.append(s);return s
 try:
  probe=client()
  for _ in range(100):
   try:
    async with probe.get(GH+'/health') as r:
     if r.status==200:break
   except aiohttp.ClientError:pass
   await asyncio.sleep(.05)
  runner=web.AppRunner(app.make_app());await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start();url=f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'
  async def ws(s):
   w=await s.ws_connect(url+'/ws');sockets.append(w);return w
  users=[]
  for i in range(3):
   s=client();users.append(s)
   async with s.post(url+'/api/auth/register',json={'username':f'pool_user_{i}','password':'Test-password-123','displayName':f'Pool {i}'}) as r:assert r.status==200,await r.text()
  async with probe.get(url+'/api/games') as r:assert 'pool' in {g['id'] for g in (await r.json())['games']}
  for path in ['/games/pool/index.html','/browser-runtime.js','/games/pool/sounds/cue_hard1.m4a']:
   async with probe.get(url+path) as r:assert r.status==200,path
  peers=[await ws(s) for s in users[:2]]
  await peers[0].send_json({'type':'create_room','settings':{'gameId':'pool','players':1,'gameType':999}})
  created=await receive(peers[0],'created');rid=created['roomId'];assert created['capacity']==2 and created['settings']['gameType']==0
  await peers[0].send_json({'type':'create_invite'});invite=await receive(peers[0],'invite_created')
  await peers[1].send_json({'type':'join_invite','inviteToken':invite['inviteToken']});assert (await receive(peers[1],'joined'))['seat']==1
  for w in peers:
   start=await receive(w,'start');assert len(start['snapshot']['pool']['balls'])==16
  for w in peers:await w.send_json({'type':'runtime_ready'})
  for w in peers:assert (await receive(w,'begin_match'))['type']=='begin_match'
  sequence=[0,0]
  async def move(seat,m):
   await peers[seat].send_json({'type':'move','packet':{'i':f'p-{seat}-{sequence[seat]}','n':sequence[seat],'m':m}})
   responses=[await receive(w,'move') for w in peers];assert all(x['type']=='move' for x in responses),responses;sequence[seat]+=1;return responses
  await move(0,{'__ready':1});shot=await move(0,{'a':1,'st':.8,'an':-1.5707963267948966,'sp':[0,0]})
  assert shot[0]['reveal']['soundEvents'][0]['kind']=='cue'
  assert shot[0]['reveal']['soundEvents']==shot[1]['reveal']['soundEvents']
  assert shot[0]['reveal']['frames'] and shot[0]['reveal']['pool']['turn']==[1]
  results.append('Catalog, assets, authenticated invitation, two-player match and actual server break')
  await peers[0].send_json({'type':'move','packet':{'i':'wrong-turn','n':sequence[0],'m':{'a':1,'st':.8,'an':0,'sp':[0,0]}}});assert (await receive(peers[0],'move'))['type']=='error'
  await peers[0].send_json({'type':'move','packet':{'__info':{'a':-1,'idx':1,'logic':{'winner':0}}}});assert (await receive(peers[0],'move'))['type']=='error'
  await peers[1].send_json({'type':'chat_send','text':'مرحبا من البلياردو <script>'})
  for w in peers:assert (await receive(w,'chat_message'))['text']=='مرحبا من البلياردو <script>'
  watcher=await ws(users[2]);await watcher.send_json({'type':'watch_room','roomId':rid});assert (await receive(watcher,'watching'))['type']=='watching';assert (await receive(watcher,'start'))['snapshot']['pool']['turn']==[1]
  await watcher.send_json({'type':'move','packet':{'i':'watch','n':0,'m':{'a':0}}});assert (await receive(watcher,'move'))['type']=='error'
  rogue=await ws(users[2]);await rogue.send_json({'type':'join_room','roomId':rid,'token':created['token']});assert (await receive(rogue,'joined')).get('code')=='RECONNECT_ACCOUNT_MISMATCH'
  results.append('Chat, spectator view, spectator move rejection, forged result rejection and seat ownership')
  await peers[0].close();peers[0]=await ws(users[0]);await peers[0].send_json({'type':'join_room','roomId':rid,'token':created['token']});assert (await receive(peers[0],'joined'))['seat']==0
  snap=(await receive(peers[0],'start'))['snapshot'];assert snap['pool']['sequence']==sequence
  async with probe.delete(GH+'/v1/room/'+rid,headers={'X-SamiDev-Service-Key':'integration-test-key'}) as r:assert r.status==200
  restored=await app.SERVICE._ensure_authority(rid,renew=True);assert restored['pool']['sequence']==sequence and restored['pool']['balls']==snap['pool']['balls']
  await move(1,{'a':0});state=await app.SERVICE.gamehost.state(rid);assert state['gameOver'] and state['finishOrder']==[[0],[1]]
  assert (await app.SERVICE.store.get_room_state(rid))['finished']
  results.append('Reconnect, GameHost restoration, resignation winner and platform finished-room lifecycle')
  print(json.dumps({'ok':True,'results':results},ensure_ascii=False,indent=2))
 finally:
  for w in sockets:await w.close()
  if runner:await runner.cleanup()
  for s in sessions:await s.close()
  proc.terminate()
  try:proc.wait(timeout=3)
  except subprocess.TimeoutExpired:proc.kill();proc.wait()
if __name__=='__main__':asyncio.run(main())
