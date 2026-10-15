"""Isolated lifecycle races and scoped moderation; no production keys touched."""
import asyncio,json,os,secrets,sys,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
os.environ['SAMIDEV_PLATFORM_PREFIX']='policytest'+secrets.token_hex(6)
os.environ['SAMIDEV_FIREBASE_AUTH']='0'
from store import MemoryStore,RedisStore,StoreError,sanitize_settings,now_ms
from social_platform import PlatformService,PlatformError

class Lifecycle(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.stores=[MemoryStore()]
  if os.getenv('SAMIDEV_TEST_REDIS_URL'):
   self.stores.append(RedisStore(os.environ['SAMIDEV_TEST_REDIS_URL'],prefix='waittest'+secrets.token_hex(6)))
 async def asyncTearDown(self):
  for store in self.stores:
   if store.distributed:
    async for key in store.r.scan_iter(match=store.prefix+':*'):await store.r.delete(key)
    await store.r.aclose()
 async def age(self,s,rid):
  if s.distributed:
   clock=await s.r.time();deadline=clock[0]*1000+clock[1]//1000-1
   await s.r.hset(s.kroom(rid),mapping={'waitingExpiresAt':str(deadline)})
   await s.r.zadd(s.kwaiting(),{rid:deadline})
  else:s.rooms[rid].waiting_expires_at=now_ms()-1
 async def create(self,s,players=2):
  return await s.create_room('owner',sanitize_settings({'gameId':'pool','gameType':6 if players==3 else 7}),'node','owner','owner-account')
 async def test_deadline_enforced_for_direct_invite_and_reconnect_without_sweeper(self):
  for s in self.stores:
   room=await self.create(s);rid=room['roomId']
   invite=await s.create_invite(rid,0,'owner',1,600)
   await self.age(s,rid)
   operations=[s.join_room(rid,'other',None,'node','other','other-account'),s.join_room(rid,'owner',room['token'],'node','again','owner-account'),s.join_invite(invite['inviteToken'],'other','node','other','other-account')]
   for result in await asyncio.gather(*operations,return_exceptions=True):
    self.assertIsInstance(result,StoreError);self.assertEqual(result.code,'ROOM_WAIT_EXPIRED')
   self.assertFalse(await s.list_public_rooms())
   reports=await asyncio.gather(*(s.expire_waiting_rooms() for _ in range(12)))
   self.assertEqual(sum(len(x) for x in reports),1)
   closures=await s.waiting_closures([rid]);self.assertEqual(closures[0]['createdAt'],room['createdAt'])
 async def test_started_table_does_not_expire_but_reopened_waiting_keeps_original_deadline(self):
  for s in self.stores:
   room=await self.create(s);rid=room['roomId'];deadline=room['waitingExpiresAt']
   joined=await s.join_room(rid,'other',None,'node','other','other-account')
   self.assertEqual(joined['waitingExpiresAt'],deadline)
   await self.age(s,rid)
   self.assertFalse(await s.expire_waiting_rooms())
   self.assertFalse(await s.waiting_closures([rid]))
   await s.leave_room(rid,1,'other',1)
   self.assertTrue(await s.expire_waiting_rooms())
 async def test_owner_control_and_transfer_no_control_after_begin(self):
  for s in self.stores:
   room=await self.create(s,3);rid=room['roomId']
   await s.join_room(rid,'other',None,'node','other','other-account')
   with self.assertRaises(StoreError) as caught:await s.manage_waiting_table(rid,1,'other',1,'close')
   self.assertEqual(caught.exception.code,'TABLE_OWNER_REQUIRED')
   result=await s.manage_waiting_table(rid,0,'owner',1,'kick',1)
   self.assertEqual(result['targetConnId'],'other')
   self.assertFalse((await s.get_room_state(rid))['started'])
   await s.join_room(rid,'other',None,'node','other2','other-account')
   await s.leave_room(rid,0,'owner',1)
   self.assertEqual((await s.get_room_state(rid))['ownerSeat'],1)
   await s.join_room(rid,'third',None,'node','third','third-account')
   self.assertEqual((await s.get_room_state(rid))['ownerSeat'],1)
   self.assertEqual((await s.list_public_rooms())[0]['hostName'],'other')
   result=await s.manage_waiting_table(rid,1,'other2',1,'close')
   self.assertEqual(result['reason'],'TABLE_CLOSED')
   self.assertFalse(await s.list_public_rooms())
   self.assertEqual((await s.waiting_closures([rid]))[0]['reason'],'TABLE_CLOSED')
   # A fresh complete table: beginning and management compete on the same state.
   room=await self.create(s);rid=room['roomId']
   await s.join_room(rid,'other',None,'node','other','other-account')
   await s.runtime_ready(rid,0,'owner',1)
   race=await asyncio.gather(s.runtime_ready(rid,1,'other',1),s.manage_waiting_table(rid,0,'owner',1,'kick',1),return_exceptions=True)
   state=await s.get_room_state(rid)
   if state['begun']:
    self.assertIsInstance(race[1],StoreError);self.assertEqual(race[1].code,'TABLE_MANAGEMENT_CLOSED')
   else:self.assertIsInstance(race[1],dict)

 async def test_scoped_departure_does_not_disconnect_a_running_match(self):
  for store in self.stores:
   room=await self.create(store);rid=room['roomId']
   await store.join_room(rid,'other',None,'node','other','other-account')
   await store.runtime_ready(rid,0,'owner',1);await store.runtime_ready(rid,1,'other',1)
   result=await store.leave_room(rid,1,'other',1,before_begin_only=True)
   self.assertFalse(result['seatFreed'])
   self.assertTrue((await store.get_room_state(rid))['roster'][1]['connected'])
   with self.assertRaises(StoreError):await store.manage_waiting_table(rid,0,'owner',1,'close')

 async def test_last_seat_and_expiry_race_has_one_result(self):
  for store in self.stores:
   for _ in range(8):
    room=await self.create(store);rid=room['roomId']
    if store.distributed:
     clock=await store.r.time();deadline=clock[0]*1000+clock[1]//1000+1
     await store.r.hset(store.kroom(rid),mapping={'waitingExpiresAt':str(deadline)})
     await store.r.zadd(store.kwaiting(),{rid:deadline})
    else:store.rooms[rid].waiting_expires_at=now_ms()+1
    joined,expired=await asyncio.gather(store.join_room(rid,'other',None,'node','other','other-account'),store.expire_waiting_rooms(),return_exceptions=True)
    self.assertIsInstance(expired,list)
    if isinstance(joined,dict):
     self.assertTrue(joined['started']);self.assertFalse((await store.get_room_state(rid))['waitingExpired'])
    else:
     self.assertIsInstance(joined,StoreError);self.assertEqual(joined.code,'ROOM_WAIT_EXPIRED')
     self.assertFalse((await store.get_room_state(rid))['started'])

class CommunityPolicy(unittest.IsolatedAsyncioTestCase):
 async def test_scoped_permissions_and_restrictions(self):
  services=[PlatformService()];r=None
  if os.getenv('SAMIDEV_TEST_DATABASE_URL') and os.getenv('SAMIDEV_TEST_REDIS_URL'):
   import redis.asyncio as redis
   from postgres_platform import PostgresPlatformService
   r=redis.from_url(os.environ['SAMIDEV_TEST_REDIS_URL'],decode_responses=True)
   p=PostgresPlatformService(os.environ['SAMIDEV_TEST_DATABASE_URL'],r);await p.start();services.append(p)
  try:
   for s in services:
    admin=await s.create_user('admin','Policy-password-123',role='admin')
    mod=await s.create_user('moderator','Policy-password-123')
    user=await s.create_user('member','Policy-password-123')
    rules=s.community_rules
    with self.assertRaises(PlatformError):await rules.moderate(user['id'],'majlis',mod['id'],'grant_moderator')
    await rules.moderate(admin['id'],'majlis',mod['id'],'grant_moderator')
    gifted=await s.get_user(mod['id'])
    self.assertEqual(len(json.loads(gifted['systemNotifications'])),1)
    snapshot=await s.store_snapshot(mod['id'])
    self.assertIn('badge_steward',snapshot['inventory'])
    self.assertFalse(any(x['id']=='badge_steward' for x in (await s.store_snapshot(user['id']))['catalog']))
    with self.assertRaises(PlatformError):await s.buy_store_item(user['id'],'badge_steward')
    await s.equip_store_item(mod['id'],'badge_steward')
    await rules.moderate(admin['id'],'diwan',mod['id'],'grant_moderator')
    await rules.moderate(admin['id'],'majlis',mod['id'],'revoke_moderator')
    self.assertIn('badge_steward',(await s.store_snapshot(mod['id']))['inventory'])
    self.assertEqual((await s.get_user(mod['id']))['nameBadge'],'badge_steward')
    await rules.moderate(admin['id'],'diwan',mod['id'],'revoke_moderator')
    removed=await s.store_snapshot(mod['id'])
    self.assertNotIn('badge_steward',removed['inventory'])
    self.assertEqual(removed['equipped']['name_badge'],'badge_palm_swords')
    self.assertEqual((await s.get_user(mod['id']))['nameBadge'],'badge_palm_swords')
    with self.assertRaises(PlatformError):await s.equip_store_item(mod['id'],'badge_steward')
    await asyncio.gather(*(rules.moderate(admin['id'],'majlis',mod['id'],'grant_moderator') for _ in range(4)))
    self.assertEqual(json.loads((await s.get_user(mod['id']))['systemNotifications']),json.loads(gifted['systemNotifications']))
    self.assertIn('badge_steward',(await s.store_snapshot(mod['id']))['inventory'])
    self.assertTrue(rules.can_moderate(await s.get_user(mod['id']),'majlis'))
    self.assertFalse(rules.can_moderate(await s.get_user(mod['id']),'diwan'))
    with self.assertRaises(PlatformError):await rules.moderate(mod['id'],'diwan',user['id'],'ban')
    with self.assertRaises(PlatformError):await rules.moderate(mod['id'],'majlis',user['id'],'grant_moderator')
    with self.assertRaises(PlatformError):await rules.moderate(mod['id'],'majlis',admin['id'],'kick')
    await rules.moderate(mod['id'],'majlis',user['id'],'mute')
    with self.assertRaises(PlatformError) as caught:await s.append_community_chat(user['id'],'majlis','blocked')
    self.assertEqual(caught.exception.code,'COMMUNITY_MUTED')
    rules.check({**(await s.get_user(user['id'])),'role':'admin'},'majlis',chat=True)
    await s.append_community_chat(user['id'],'diwan','allowed')
    await rules.moderate(mod['id'],'majlis',user['id'],'unmute')
    await s.append_community_chat(user['id'],'majlis','allowed')
    await rules.moderate(mod['id'],'majlis',user['id'],'kick')
    with self.assertRaises(PlatformError):await s.touch_community(user['id'],'majlis')
    await s.touch_community(user['id'],'diwan')
    await rules.moderate(mod['id'],'majlis',user['id'],'ban')
    with self.assertRaises(PlatformError):await rules.access(user['id'],'majlis')
    await rules.moderate(mod['id'],'majlis',user['id'],'unban')
    await rules.access(user['id'],'majlis')
    await rules.moderate(admin['id'],'majlis',mod['id'],'revoke_moderator')
    with self.assertRaises(PlatformError):await rules.moderate(mod['id'],'majlis',user['id'],'ban')
  finally:
   if r is not None:
    p=services[-1]
    async with p.r.pool.acquire() as conn:await conn.execute('DELETE FROM samidev_social_documents WHERE key LIKE $1',os.environ['SAMIDEV_PLATFORM_PREFIX']+':%')
    await p.close()
    async for key in r.scan_iter(match=os.environ['SAMIDEV_PLATFORM_PREFIX']+':*'):await r.delete(key)
    await r.aclose()

if __name__=='__main__':unittest.main(verbosity=2)
