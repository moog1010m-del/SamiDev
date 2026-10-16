"""Two independent policy/store clients; only deletes this test's unique prefix."""
import asyncio,os,secrets,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
os.environ['SAMIDEV_PLATFORM_PREFIX']='roompolicytest'+secrets.token_hex(8)
os.environ['SAMIDEV_FIREBASE_AUTH']='0'
from social_platform import PlatformService,PREFIX
from store import RedisStore,StoreError,sanitize_settings
from room_policy import DEFAULTS
import redis.asyncio as redis

async def main():
 url=os.environ['SAMIDEV_TEST_REDIS_URL']
 from urllib.parse import urlparse
 assert urlparse(url).hostname in {'127.0.0.1','localhost'}
 clients=[redis.from_url(url,decode_responses=True) for _ in range(2)]
 services=[PlatformService(client) for client in clients]
 stores=[RedisStore(url,prefix=PREFIX+'rt') for _ in range(2)]
 try:
  users=[await services[0].create_user('concurrent_'+str(i),'Test-password-123') for i in range(3)]
  await services[0].room_policy.configure('majlis',{**DEFAULTS,'maxTables':1})
  assert (await services[1].room_policy.settings('majlis'))['maxTables']==1
  async def create(index):
   policy=services[index].room_policy
   try:
    async with policy.transaction():
     await policy.admit(stores[index],users[0]['id'],'majlis','create_room',{})
     return await stores[index].create_room('Owner',sanitize_settings({'gameId':'pool'}),'test-node',f'owner-{index}',users[0]['id'],'majlis')
   except StoreError as e:return e.code
  results=await asyncio.gather(create(0),create(1));accepted=[r for r in results if isinstance(r,dict)]
  assert len(accepted)==1 and 'ACCOUNT_IN_MATCH' in results,results
  room=accepted[0];rid=room['roomId'];owner_index=0 if isinstance(results[0],dict) else 1
  try:
   async with services[1].room_policy.transaction():await services[1].room_policy.admit(stores[1],users[2]['id'],'majlis','create_room',{})
   raise AssertionError('table cap bypassed')
  except StoreError as e:assert e.code=='COMMUNITY_TABLE_LIMIT'
  async with services[1].room_policy.transaction():
   await services[1].room_policy.admit(stores[1],users[1]['id'],'majlis','join_room',{'roomId':rid})
   joined=await stores[1].join_room(rid,'Other',None,'other-node','other',users[1]['id'])
  await stores[0].runtime_ready(rid,0,f'owner-{owner_index}',1)
  await stores[1].runtime_ready(rid,joined['seat'],'other',1)
  state=await stores[1].get_room_state(rid);assert state['begunAt']>0
  await services[0].room_policy.finish(stores[0],rid)
  assert await services[1].room_policy.read('cooldown:'+users[0]['id'])>await services[1].room_policy.clock()
  # A legitimate reconnect may inspect the same completed match during cooldown.
  async with services[1].room_policy.transaction():
   assert await services[1].room_policy.admit(stores[1],users[0]['id'],'majlis','join_room',{'roomId':rid,'token':room['token']})
  try:
   async with services[1].room_policy.transaction():await services[1].room_policy.admit(stores[1],users[0]['id'],'majlis','join_room',{'roomId':rid,'token':'forged-token'})
   raise AssertionError('forged reconnect bypassed cooldown')
  except StoreError as e:assert e.code=='MATCH_COOLDOWN'
  # Real Redis Pub/Sub: local sender is delivered once and remote gateway once.
  async with services[0].live.subscribe('majlis',users[0]['id']) as local:
   async with services[1].live.subscribe('majlis',users[1]['id']) as remote:
    await services[0].live.publish('majlis',{'type':'message','message':{'id':'broadcast-test'}})
    assert (await asyncio.wait_for(local.get(),1))['message']['id']=='broadcast-test'
    assert (await asyncio.wait_for(remote.get(),1))['message']['id']=='broadcast-test'
    await asyncio.sleep(.05)
    assert local.empty() and remote.empty()
  print('PASS two Redis gateways: concurrent same-account admission, table cap, shared settings, authoritative begin clock, cross-gateway cooldown, valid/forged reconnect, Pub/Sub once per gateway')
 finally:
  for service in services:await service.live.close()
  keys=[key async for key in clients[0].scan_iter(PREFIX+'*')]
  if keys:await clients[0].delete(*keys)
  for store in stores:await store.r.aclose()
  for client in clients:await client.aclose()
if __name__=='__main__':asyncio.run(main())
