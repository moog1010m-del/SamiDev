"""Real PostgreSQL/Redis cross-gateway replay, persistence and account cleanup."""
import asyncio,os,secrets,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
os.environ['SAMIDEV_PLATFORM_PREFIX']='direct_test_'+secrets.token_hex(6)
import redis.asyncio as redis
from postgres_platform import PostgresPlatformService
from social_platform import PlatformError
async def main():
 db=os.environ['SAMIDEV_TEST_DATABASE_URL'];url=os.environ['SAMIDEV_TEST_REDIS_URL']
 assert '127.0.0.1' in db and '127.0.0.1' in url
 transient=redis.from_url(url,decode_responses=True);services=[PostgresPlatformService(db,transient,max_connections=4) for _ in range(2)]
 try:
  for s in services:await s.start()
  a,b,c=[await services[0].accounts.guest() for _ in range(3)]
  await services[0].send_friend_request(a,b['username']);await services[1].respond_friend_request(b,a['id'],True)
  payload={'text':'سر خاص 8','clientMessageId':'concurrent_nonce_123'}
  async with services[1].direct.live.subscribe(b['id'],b['id']) as queue:
   first,second=await asyncio.gather(*(s.direct.send(a['id'],b['id'],payload) for s in services))
   assert first==second
   event=await asyncio.wait_for(queue.get(),3)
   assert event['type']=='direct' and 'text' not in event and event['notify']
  await services[1].direct.mute(b['id'],a['id'],True)
  await services[0].close();services[0]=PostgresPlatformService(db,transient,max_connections=4);await services[0].start()
  history=await services[0].direct.history(b['id'],a['id'])
  assert history['muted'] and len(history['messages'])==1
  await services[0].direct.device(a['id'],'0'*64,{'deviceId':'device_1234567890','fid':'abcdefghijklmnopqrstuv'})
  link=(await services[0].direct.invite(a['id']))['url'].split('friend=')[1]
  await services[1].direct.redeem(c,link)
  assert await services[1].deletions.request(a)
  assert not await services[0].direct.get(services[0].direct.thread(a['id'],b['id']))
  assert not await services[0].direct.devices(a['id'])
  assert not await services[0].direct.get(services[0].direct.key('direct-mute',b['id'],a['id']))
  try:await services[0].direct.redeem(c,link)
  except PlatformError:pass
  else:raise AssertionError('deleted invitation accepted')
  print('DIRECT_POSTGRES_PASS: cross-node private bus, concurrent idempotency, restart, mute, invitation, complete deletion')
 finally:
  for s in services:await s.close()
  await transient.aclose()
if __name__=='__main__':asyncio.run(main())
