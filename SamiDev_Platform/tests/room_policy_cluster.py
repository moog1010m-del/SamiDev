"""Authenticated HTTP + WS behavior on two gateways, real PostgreSQL and Redis."""
import asyncio,json,os
import aiohttp,asyncpg
from realtime_cluster_fixture import Cluster,receive
async def main():
 cluster=Cluster(gateways=2,hosts=1,browser_origins=True);sockets=[]
 try:
  await cluster.start();cookies=await cluster.seed(3)
  conn=await asyncpg.connect(cluster.db)
  try:await conn.execute("UPDATE samidev_social_documents SET value=jsonb_set(value,'{role}','\"admin\"') WHERE key=$1",cluster.prefix+':user:'+cluster.prefix+'_0')
  finally:await conn.close()
  async with aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar()) as session:
   async def post(index,path,body,status=200):
    async with session.post(cluster.urls[index%2]+path,json=body,headers=cookies[index]) as response:
     result=await response.json();assert response.status==status,(path,response.status,result);return result
   async def error(ws):
    async with asyncio.timeout(10):
     while True:
      packet=await ws.receive_json()
      if packet.get('type')=='error':return packet
   async with session.post(cluster.urls[0]+'/api/auth/guest',json={},headers=cluster.base_headers) as response:
    anonymous=await response.json();assert response.status==200 and anonymous['user']['isGuest'],(response.status,anonymous)
    guest_headers={**cluster.base_headers,'Cookie':'samidev_session='+response.cookies['samidev_session'].value}
   async with session.get(cluster.urls[1]+'/api/me',headers=guest_headers) as response:
    assert (await response.json())['user']['id']==anonymous['user']['id']
   async with session.post(cluster.urls[1]+'/api/auth/guest',json={},headers=guest_headers) as response:
    assert (await response.json())['user']['id']==anonymous['user']['id']
   async with session.post(cluster.urls[1]+'/api/game-ticket',json={'communityId':'majlis'},headers=guest_headers) as response:
    ticket=(await response.json())['ticket']
   async with session.ws_connect(cluster.urls[0]+'/ws?ticket='+ticket,headers=guest_headers) as guest_socket:
    await guest_socket.send_json({'type':'create_room','settings':{'gameId':'pool','gameType':7}})
    assert (await receive(guest_socket,{'created'}))['roomId']
   uid=lambda i:cluster.prefix+'_'+str(i)
   await post(0,'/api/admin/users/'+uid(1)+'/role',{'role':'moderator'},400)
   await post(0,'/api/communities/majlis/moderation',{'targetUserId':uid(1),'action':'grant_moderator'})
   async with session.get(cluster.urls[1]+'/api/communities',headers=cookies[1]) as response:
    home=await response.json();assert response.status==200
    assert home['notifications'][0]['sender']=='سيتم'
    assert home['notifications'][0]['itemId']=='badge_steward'
   async with session.get(cluster.urls[0]+'/api/communities',headers=cookies[2]) as response:
    assert (await response.json())['notifications']==[]
   await post(1,'/api/communities/diwan/moderation',{'targetUserId':uid(2),'action':'ban'},403)
   await post(1,'/api/communities/majlis/moderation',{'targetUserId':uid(2),'action':'mute'})
   await post(2,'/api/communities/majlis/chat',{'text':'not allowed'},403)
   await post(2,'/api/communities/diwan/chat',{'text':'allowed'})
   await post(1,'/api/communities/majlis/moderation',{'targetUserId':uid(2),'action':'unmute'})
   async def socket(index):
    ticket=(await post(index,'/api/game-ticket',{'communityId':'majlis'}))['ticket']
    ws=await session.ws_connect(cluster.urls[1 if index==2 else index%2]+'/ws?ticket='+ticket,headers=cookies[index]);sockets.append(ws);return ws
   a=await socket(0);b=await socket(2)
   await a.send_json({'type':'create_room','settings':{'gameId':'pool','gameType':6}})
   created=await receive(a,{'created'});rid=created['roomId']
   assert created['waitingExpiresAt']-created['createdAt']==300000
   await b.send_json({'type':'join_room','roomId':rid});await receive(b,{'joined'})
   await b.send_json({'type':'manage_table','action':'close'})
   assert (await error(b))['code']=='TABLE_OWNER_REQUIRED'
   await a.send_json({'type':'manage_table','action':'kick','targetSeat':1})
   kicked=await receive(b,{'left_room'});assert kicked['reason']=='TABLE_KICKED'
   await b.send_json({'type':'join_room','roomId':rid});await receive(b,{'joined'})
   # Expiration notification must work on both gateways even without Pub/Sub replay.
   key=cluster.prefix+'r:room:'+rid;clock=await cluster.r.time();deadline=clock[0]*1000+clock[1]//1000-1
   await cluster.r.hset(key,mapping={'waitingExpiresAt':str(deadline)})
   await cluster.r.zadd(cluster.prefix+'r:rooms:waiting',{rid:deadline})
   for ws in [a,b]:assert (await receive(ws,{'left_room'},timeout=12))['reason']=='ROOM_WAIT_EXPIRED'
   await b.send_json({'type':'join_room','roomId':rid})
   assert (await error(b))['code']=='ROOM_WAIT_EXPIRED'
   await post(1,'/api/communities/majlis/moderation',{'targetUserId':uid(2),'action':'ban'})
   await post(2,'/api/game-ticket',{'communityId':'majlis'},403)
   await post(2,'/api/communities/diwan/enter',{})
   await post(1,'/api/communities/majlis/moderation',{'targetUserId':uid(2),'action':'unban'})
   await b.send_json({'type':'create_room','settings':{'gameId':'pool','gameType':6}})
   pending=await receive(b,{'created'})
   await post(1,'/api/communities/majlis/moderation',{'targetUserId':uid(2),'action':'ban'})
   assert (await receive(b,{'left_room'},timeout=12))['reason']=='COMMUNITY_BANNED'
   await post(1,'/api/communities/majlis/moderation',{'targetUserId':uid(2),'action':'unban'})
   env=dict(os.environ,SAMIDEV_TEST_BASE_URL=cluster.urls[0],SAMIDEV_POLICY_ADMIN_COOKIE=cookies[0]['Cookie'].split('=',1)[1],SAMIDEV_POLICY_MEMBER=uid(2),SAMIDEV_POLICY_MEMBER_COOKIE=cookies[2]['Cookie'].split('=',1)[1],SAMIDEV_POLICY_COLLEAGUE=uid(1))
   process=await asyncio.create_subprocess_exec('node',str(__import__('pathlib').Path(__file__).with_name('room_policy_browser.mjs')),env=env)
   assert await process.wait()==0
  print('ROOM_POLICY_TWO_GATEWAY_HTTP_WS_PASS')
 finally:
  for ws in sockets:await ws.close()
  await cluster.close()
asyncio.run(main())
