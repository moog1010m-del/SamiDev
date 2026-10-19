"""Disposable database only: blocks survive gateways/restart and account deletion."""
import asyncio,os,secrets,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
os.environ['SAMIDEV_PLATFORM_PREFIX']='safety_test_'+secrets.token_hex(6)
import redis.asyncio as redis
from postgres_platform import PostgresPlatformService
from social_platform import PlatformError
from store import RedisStore
async def main():
 db=os.environ['SAMIDEV_TEST_DATABASE_URL'];url=os.environ['SAMIDEV_TEST_REDIS_URL']
 assert '127.0.0.1' in db and '127.0.0.1' in url
 transient=redis.from_url(url,decode_responses=True);services=[PostgresPlatformService(db,transient,max_connections=4) for _ in range(2)]
 try:
  for service in services:await service.start()
  a,b=[await services[0].accounts.guest() for _ in range(2)]
  await services[0].safety.update(a['id'],b['id'],True)
  assert (await services[1].public_profile(b['id'],a['id']))['blocked']
  games=RedisStore(url,prefix='safety_games_'+secrets.token_hex(6))
  try:
   room=await games.create_room('Sender',{'gameId':'pool','players':1,'gameType':0},'node','connection',account_id=b['id'])
   message=await games.append_chat(room['roomId'],0,'connection',1,'hidden',sticker={'userId':'forged'})
   assert message['userId']==b['id']
   history=await games.chat_history(room['roomId']);assert history[0]['userId']==b['id']
   filtered=await services[1].safety.game_event(a['id'],room['roomId'],{'type':'chat_history','messages':history},games)
   assert filtered['messages']==[]
  finally:await games.r.aclose()
  try:await services[1].send_friend_request(b,a['username'])
  except PlatformError as e:assert e.code=='USER_BLOCKED'
  else:raise AssertionError('cross-gateway block bypass')
  await services[0].close();services[0]=PostgresPlatformService(db,transient,max_connections=4);await services[0].start()
  assert b['id'] in await services[0].safety.blocked(a['id'])
  assert await services[0].deletions.request(b)
  assert not await services[1].safety.blocked(a['id'])
  print('USER_SAFETY_POSTGRES_PASS: cross-gateway block, restart persistence, trusted Redis chat sender, inbound deletion cleanup')
 finally:
  for service in services:await service.close()
  await transient.aclose()
if __name__=='__main__':asyncio.run(main())
