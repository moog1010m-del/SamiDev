"""Requires dedicated localhost test URLs. Never uses the deployed platform database."""
import asyncio,os,secrets,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'backend'))
os.environ['SAMIDEV_PLATFORM_PREFIX']='botroster_test_'+secrets.token_hex(6)
import redis.asyncio as redis
from postgres_platform import PostgresPlatformService
from postgres_store import durable_key
from bot_accounts import BotAccounts
from social_platform import PREFIX,PlatformError
async def main():
 database=os.environ['SAMIDEV_TEST_DATABASE_URL'];redis_url=os.environ['SAMIDEV_TEST_REDIS_URL']
 assert '127.0.0.1' in database and '127.0.0.1' in redis_url
 transient=redis.from_url(redis_url,decode_responses=True)
 services=[PostgresPlatformService(database,transient,max_connections=4) for _ in range(2)]
 for service in services:await service.start()
 managers=[BotAccounts(s) for s in services]
 try:
  assert durable_key(managers[0].index)
  results=await asyncio.gather(*(m.provision({'targetPerRoom':50,'enabled':True}) for m in managers))
  assert sum(r['created'] for r in results)==200
  assert not await services[1].list_users(include_bots=False)
  state=await managers[1].snapshot();assert len(state['bots'])==200 and all(u['online'] for u in state['bots'])
  uid=state['bots'][0]['id']
  await managers[0].update(uid,{'username':'Saved_Bot','bio':'تجربة الحفظ','room':'diwan','enabled':False,'skill':'expert','badgeId':'badge_shard'})
  other=await services[1].get_user(uid);assert other['username']=='Saved_Bot' and other['botEnabled']=='0' and other['botSkill']=='expert'
  assert not await services[1].is_online(uid)
  await asyncio.gather(*(s.close() for s in services));services=[]
  # Deleting only this test namespace from transient Redis must not delete accounts.
  keys=[key async for key in transient.scan_iter(match=PREFIX+':*')]
  if keys:await transient.delete(*keys)
  restored=PostgresPlatformService(database,transient,max_connections=4);services=[restored];await restored.start()
  manager=BotAccounts(restored);state=await manager.snapshot();assert len(state['bots'])==200
  row=next(u for u in state['bots'] if u['id']==uid);assert row['username']=='Saved_Bot' and not row['enabled'] and row['room']=='diwan' and row['nameBadge']=='badge_shard'
  await manager.sweep();assert sum(u['online'] for u in (await manager.snapshot())['bots'])==199
  print('BOT_POSTGRES_PASS: 200 durable accounts; concurrent idempotent provisioning; cross-gateway edits; Redis namespace loss; restart persistence; online state renewal')
 finally:
  for service in services:await service.close()
  await transient.aclose()
if __name__=='__main__':asyncio.run(main())
