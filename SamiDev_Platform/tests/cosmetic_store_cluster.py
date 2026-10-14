"""Isolated PostgreSQL + Redis: entitlement, cross-gateway chat and browser purchase preview."""
import asyncio,json,os,sys,asyncpg,aiohttp
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from realtime_cluster_fixture import Cluster,receive
async def main():
 cluster=Cluster(gateways=2,hosts=1,browser_origins=True)
 try:
  await cluster.start();cookies=await cluster.seed(2);conn=await asyncpg.connect(cluster.db)
  try:await conn.execute("UPDATE samidev_social_documents SET value=jsonb_set(value,'{coins}','\"1000\"') WHERE key=$1",cluster.prefix+':user:'+cluster.prefix+'_0')
  finally:await conn.close()
  async with aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar()) as session:
   base=cluster.urls[0];h=cookies[0]
   async def post(path,data):
    async with session.post(base+path,json=data,headers=h) as response:
     body=await response.json();assert response.status==200,(path,response.status,body);return body
   async with session.post(base+'/api/store/equip',json={'itemId':'chat_turquoise'},headers=h) as response:assert response.status==403
   for item in ['chat_turquoise','banner_dunes','badge_shard']:
    await post('/api/store/buy',{'itemId':item});await post('/api/store/equip',{'itemId':item})
   async with session.get(cluster.urls[1]+'/api/me',headers=h) as response:
    body=await response.json();assert body['user']['chatBubble']=='chat_turquoise';assert body['user']['profileBanner']=='banner_dunes'
   msg=await post('/api/communities/majlis/chat',{'text':'هذه رسالة مزينة'});assert msg['message']['chatBubble']=='chat_turquoise',msg
   peers=[]
   for i in range(2):
    async with session.post(cluster.urls[i]+'/api/game-ticket',json={},headers=cookies[i]) as response:ticket=(await response.json())['ticket']
    ws=await session.ws_connect(cluster.urls[i]+'/ws?ticket='+ticket,headers=cookies[i]);peers.append(ws)
   await peers[0].send_json({'type':'create_room','settings':{'gameId':'pool','players':0,'live':1}});assigned=await receive(peers[0],{'created','joined'});rid=assigned['roomId']
   await peers[1].send_json({'type':'join_room','roomId':rid});await receive(peers[1],{'created','joined'})
   await peers[0].send_json({'type':'chat_send','text':'اختبار الزخرفة','chatBubble':'chat_ember'})
   for ws in peers:
    entry=await receive(ws,{'chat_message'});assert entry['chatBubble']=='chat_turquoise',entry
   await peers[1].send_json({'type':'chat_history'});history=await receive(peers[1],{'chat_history'});assert history['messages'][-1]['chatBubble']=='chat_turquoise'
   for ws in peers:await ws.close()
   env=dict(os.environ,SAMIDEV_TEST_BASE_URL=base,SAMIDEV_COSMETIC_COOKIE=h['Cookie'].split('=',1)[1])
   process=await asyncio.create_subprocess_exec('node',str(ROOT/'cosmetic_store_browser.mjs'),env=env);assert await process.wait()==0
  print('POSTGRES_REDIS_TWO_GATEWAY_COSMETICS_PASS')
 finally:await cluster.close()
asyncio.run(main())
