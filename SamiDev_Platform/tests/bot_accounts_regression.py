"""Managed roster, real persistence fields, admin authorization, capacity and UI fixture."""
import asyncio,base64,io,json,os,sys
from pathlib import Path
from collections import Counter
from PIL import Image
from aiohttp import web,ClientSession
from aiohttp.test_utils import TestServer
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.environ.update(SAMIDEV_STORE='memory',SAMIDEV_PLATFORM_STORE='memory',SAMIDEV_FIREBASE_AUTH='0',SAMIDEV_PRODUCTION='0')
from social_platform import PlatformService,PlatformHttp,PlatformError,public_user,verify_password
from bot_accounts import install
from store import MemoryStore
import app as application
async def main():
 p=PlatformService();api=PlatformHttp(p,MemoryStore());application.SERVICE.platform=p
 @web.middleware
 async def errors(request,handler):
  try:return await handler(request)
  except PlatformError as error:return web.json_response({'ok':False,'error':error.code,'message':error.message},status=error.status)
 app=web.Application(middlewares=[errors],client_max_size=2**20)
 manager=install(app,api)
 admin=await p.create_user('BotAdmin','Test-password-123',role='admin')
 member=await p.create_user('OrdinaryMember','Test-password-123')
 admin_token=await p.create_session(admin['id']);member_token=await p.create_session(member['id'])
 app.router.add_get('/api/me',api.me);app.router.add_post('/api/heartbeat',api.heartbeat)
 app.router.add_get('/api/auth/config',api.auth_config);app.router.add_get('/api/communities',api.communities)
 app.router.add_get('/api/communities/{community_id}',api.community_state)
 app.router.add_get('/api/public-profile/{user_id}',api.public_profile)
 app.router.add_get('/api/avatar/{user_id}',api.avatar_image)
 app.router.add_get('/api/admin/users',api.admin_users);app.router.add_get('/api/admin/stats',api.admin_stats)
 app.router.add_get('/api/admin/reports',api.admin_reports)
 app.router.add_get('/api/admin/communities/{community_id}/policy',api.community_policy)
 app.router.add_put('/api/admin/communities/{community_id}/policy',api.community_policy)
 async def empty(request):return web.json_response({'ok':True,'friends':[],'requests':[],'games':[]})
 app.router.add_route('*','/api/{tail:.*}',empty)
 app.router.add_get('/platform/',lambda request:web.FileResponse(ROOT/'game/platform/index.html'))
 app.router.add_get('/{path:.*}',application.SERVICE.static_game)
 async with TestServer(app) as server,ClientSession(cookies={'samidev_session':admin_token}) as client,ClientSession(cookies={'samidev_session':member_token}) as ordinary,ClientSession() as anon:
  async with anon.get(server.make_url('/api/admin/bots')) as response:assert response.status==401
  for method,path,body in [('GET','/api/admin/bots',None),('POST','/api/admin/bots',{'targetPerRoom':50}),('PATCH','/api/admin/bots/'+member['id'],{'enabled':True})]:
   async with ordinary.request(method,server.make_url(path),json=body) as response:assert response.status==403
  async with client.post(server.make_url('/api/admin/bots'),json={'targetPerRoom':50,'enabled':True}) as response:
   assert response.status==200;result=await response.json();assert result['created']==200
  async with client.post(server.make_url('/api/admin/bots'),json={'targetPerRoom':50,'enabled':True}) as response:assert (await response.json())['created']==0
  # The operator helper uses the same protected API and verifies actual room counts.
  helper=ROOT.parent/'experiments/chat-bots/provision_roster.py'
  process=await asyncio.create_subprocess_exec(sys.executable,str(helper),'--base-url',str(server.make_url('')).rstrip('/'),'--apply',env={**os.environ,'PLAZR_BOT_ADMIN_SESSION':admin_token},stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
  output,errors=await asyncio.wait_for(process.communicate(),20)
  assert process.returncode==0,(output,errors)
  lines=[json.loads(line) for line in output.decode().splitlines()]
  assert lines[0]['created']==0 and sorted(lines[1]['accountsPerRoom'].values())==[50]*4,lines
  async with client.get(server.make_url('/api/admin/users')) as response:
   assert {u['id'] for u in (await response.json())['users']}=={admin['id'],member['id']}
  state=await manager.snapshot();assert len(state['bots'])==200
  assert Counter(u['room'] for u in state['bots'])==dict(majlis=50,square=50,diwan=50,elite=50)
  assert all(u['online'] and u['isBot'] and not u['gameplayReady'] for u in state['bots'])
  for cid in ('majlis','square','diwan','elite'):assert len(await p.community_members(cid))==50
  selected=state['bots'][0];uid=selected['id'];oldroom=selected['room'];other='square' if oldroom!='square' else 'majlis'
  original_username=selected['username']
  raw=await p.get_user(uid);assert not verify_password('anything',raw['passwordHash']) and raw['role']=='user'
  assert 'passwordHash' not in selected
  out=io.BytesIO();Image.new('RGB',(32,32),'blue').save(out,format='PNG');avatar='data:image/png;base64,'+base64.b64encode(out.getvalue()).decode()
  async with client.patch(server.make_url('/api/admin/bots/'+uid),json={'username':'Nawaf_Test','bio':'أحب البلياردو','avatarData':avatar,'badgeId':'badge_ember','room':other,'enabled':False,'skill':'expert'}) as response:assert response.status==200
  raw=await p.get_user(uid);assert raw['username']=='Nawaf_Test' and raw['bio']=='أحب البلياردو' and raw['avatarData']==avatar and raw['nameBadge']=='badge_ember'
  assert not await p.is_online(uid)
  assert uid not in {u['id'] for u in await p.community_members(oldroom)}
  assert public_user(raw)['displayName']=='Nawaf_Test' and public_user(raw)['isBot']
  assert await p.find_user_by_username(original_username) is None
  assert (await p.find_user_by_username('nawaf_test'))['id']==uid
  async with client.patch(server.make_url('/api/admin/bots/'+uid),json={'username':member['username'],'bio':'must not save'}) as response:assert response.status==409
  assert (await p.get_user(uid))['bio']=='أحب البلياردو'
  async with client.patch(server.make_url('/api/admin/bots/'+uid),json={'name':'اسم منفصل'}) as response:assert response.status==400
  for new_name in ('Nawaf_Second','Nawaf_Test'):
   async with client.patch(server.make_url('/api/admin/bots/'+uid),json={'username':new_name}) as response:assert response.status==200
  assert (await p.get_user(uid)).get('freeRenameUsed') is None
  assert 'name' not in next(u for u in (await manager.snapshot())['bots'] if u['id']==uid)
  assert 'badge_ember' in p.mem_inventory[uid]
  async with client.patch(server.make_url('/api/admin/bots/'+member['id']),json={'enabled':True}) as response:assert response.status==404
  async with client.patch(server.make_url('/api/admin/bots/'+uid),json={'role':'admin'}) as response:assert response.status==400
  async with client.patch(server.make_url('/api/admin/bots/'+uid),json={'avatarData':'data:image/svg+xml;base64,xxx'}) as response:assert response.status==400
  p.room_policy.memory['settings:'+other]=json.dumps(dict(maxMembers=1))
  async with client.patch(server.make_url('/api/admin/bots/'+uid),json={'enabled':True}) as response:assert response.status==200
  raw=await p.get_user(uid);assert raw['botPresenceError']=='COMMUNITY_FULL' and not await p.is_online(uid)
  another=state['bots'][1]['id'];await p.set_banned(another,True);await manager.sweep();assert not await p.is_online(another)
  async with client.patch(server.make_url('/api/admin/bots'),json={'room':'elite','enabled':False}) as response:assert response.status==200
  assert not await p.community_members('elite')
  async with ordinary.patch(server.make_url('/api/admin/bots'),json={'enabled':False}) as response:assert response.status==403
  eligible=next(u for u in (await manager.snapshot())['bots'] if u['enabled'] and not u['banned'] and u['online'])
  async with ordinary.post(server.make_url('/api/admin/bots/'+eligible['id']+'/play-session'),json={}) as response:assert response.status==403
  async with client.post(server.make_url('/api/admin/bots/'+member['id']+'/play-session'),json={}) as response:assert response.status==409
  async with client.post(server.make_url('/api/admin/bots/'+eligible['id']+'/play-session'),json={}) as response:
   assert response.status==200 and response.headers['Cache-Control']=='no-store';play_token=(await response.json())['session']
  async with client.post(server.make_url('/api/admin/bots/'+eligible['id']+'/play-session'),json={}) as response:assert response.status==409
  async with ClientSession(cookies={'samidev_session':play_token}) as bot_client:
   async with bot_client.post(server.make_url('/api/bot-play/heartbeat'),json={}) as response:assert response.status==200
   await manager.update(eligible['id'],{'enabled':False})
   async with bot_client.post(server.make_url('/api/bot-play/heartbeat'),json={}) as response:assert response.status==403
  await p.delete_session(play_token)
  async with ordinary.post(server.make_url('/api/admin/bots/play-worker'),json={'online':True,'activeGames':1}) as response:assert response.status==403
  async with client.post(server.make_url('/api/admin/bots/play-worker'),json={'online':True,'activeGames':1}) as response:assert response.status==200
  assert (await manager.snapshot())['gameplayReady'] is True
  counts={'online':True,'activeGames':120,'selfPlayingBots':160,'humanPlayingBots':4,'readyBots':36}
  async with client.post(server.make_url('/api/admin/bots/play-worker'),json=counts) as response:assert response.status==200
  state=(await manager.snapshot())['playWorker'];assert all(state[k]==v for k,v in counts.items())
  for bad in (-1,True,1001):
   async with client.post(server.make_url('/api/admin/bots/play-worker'),json={**counts,'readyBots':bad}) as response:assert response.status==400
  p.mem_game_stats.setdefault(eligible['id'],{})['pool']={'played':7,'wins':3,'draws':0}
  assert next(b for b in (await manager.snapshot())['bots'] if b['id']==eligible['id'])['poolPlayed']==7

  async with client.post(server.make_url('/api/admin/bots/play-worker'),json={'online':False,'activeGames':0}) as response:assert response.status==200
  if os.getenv('SAMIDEV_BOT_ADMIN_BROWSER')=='1':
   proc=await asyncio.create_subprocess_exec('node',str(ROOT/'tests/bot_admin_browser.mjs'),env=dict(os.environ,SAMIDEV_TEST_BASE_URL=str(server.make_url('')),SAMIDEV_TEST_ADMIN_SESSION=admin_token))
   assert await proc.wait()==0
 print('BOT_ACCOUNTS_PASS: 200 real memory accounts; 50/room; idempotent provisioning; admin-only; profile/avatar/badge/move/offline; capacity; ban; no login secrets exposed')
if __name__=='__main__':asyncio.run(main())
