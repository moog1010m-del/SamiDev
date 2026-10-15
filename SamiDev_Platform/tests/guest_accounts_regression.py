"""Guest continuity, identity isolation and concurrent rename economics."""
import asyncio, os, secrets, sys, time, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
os.environ['SAMIDEV_PLATFORM_PREFIX']='guesttest'+secrets.token_hex(6)
os.environ['SAMIDEV_FIREBASE_AUTH']='0'
from social_platform import PlatformService, PlatformError, public_user

class Accounts(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.services=[PlatformService()];self.redis=None
  if os.getenv('SAMIDEV_TEST_DATABASE_URL') and os.getenv('SAMIDEV_TEST_REDIS_URL'):
   import redis.asyncio as redis
   from postgres_platform import PostgresPlatformService
   self.redis=redis.from_url(os.environ['SAMIDEV_TEST_REDIS_URL'],decode_responses=True)
   service=PostgresPlatformService(os.environ['SAMIDEV_TEST_DATABASE_URL'],self.redis)
   await service.start();self.services.append(service)
 async def asyncTearDown(self):
  if self.redis:
   s=self.services[-1]
   async with s.r.pool.acquire() as conn:await conn.execute('DELETE FROM samidev_social_documents WHERE key LIKE $1',os.environ['SAMIDEV_PLATFORM_PREFIX']+':%')
   await s.close()
   async for key in self.redis.scan_iter(match=os.environ['SAMIDEV_PLATFORM_PREFIX']+':*'):await self.redis.delete(key)
   await self.redis.aclose()
 async def test_guest_upgrade_preserves_player_and_revokes_old_session(self):
  from unittest.mock import AsyncMock
  for s in self.services:
   s.firebase.enabled=True;s.firebase.project='test';s.firebase.session_valid=AsyncMock(return_value=True)
   guest=await s.accounts.guest();uid=guest['id'];token=await s.create_session(uid)
   self.assertEqual((await s.resolve_session(token))['id'],uid)
   await s.grant_store_item(uid,'badge_ember')
   if s.r is None:guest['coins']='345'
   else:await s.r.hset(s.k_user(uid),'coins','345')
   claims=dict(uid=secrets.token_hex(8),email='guest@example.test',email_verified=True,auth_time=int(time.time()))
   updated=await s.accounts.link(uid,claims,'Linked_'+secrets.token_hex(3))
   self.assertEqual(updated['id'],uid);self.assertEqual(updated['coins'],'345')
   self.assertFalse(public_user(updated)['isGuest']);self.assertTrue(public_user(updated)['freeRenameAvailable'])
   self.assertIn('badge_ember',(await s.store_snapshot(uid))['inventory']);self.assertIsNone(await s.resolve_session(token))
   fresh=await s.create_session(uid,firebase_auth_time=claims['auth_time'])
   self.assertEqual((await s.resolve_session(fresh))['id'],uid);self.assertEqual((await s.firebase_account(claims))['id'],uid)
   second=await s.accounts.guest()
   with self.assertRaises(PlatformError) as err:await s.accounts.link(second['id'],claims)
   self.assertEqual(err.exception.code,'ACCOUNT_ALREADY_LINKED');self.assertTrue(public_user(await s.get_user(second['id']))['isGuest'])
 async def test_rename_free_once_then_consumable_no_duplicate_charge(self):
  for s in self.services:
   u=await s.accounts.guest();uid=u['id'];old=u['username']
   if s.r is None:u['coins']='500'
   else:await s.r.hset(s.k_user(uid),'coins','500')
   first='First_'+secrets.token_hex(3);renamed=await s.accounts.rename(uid,first)
   self.assertEqual(renamed['username'],first);self.assertEqual(renamed['displayName'],first)
   self.assertFalse(public_user(renamed)['freeRenameAvailable']);self.assertIsNone(await s.find_user_by_username(old))
   with self.assertRaises(PlatformError):await s.accounts.rename(uid,'Second_'+secrets.token_hex(3))
   self.assertEqual((await s.get_user(uid))['coins'],'500')
   await s.buy_store_item(uid,'rename_card');await s.buy_store_item(uid,'rename_card')
   self.assertEqual((await s.get_user(uid))['renameCredits'],'2')
   other=await s.accounts.guest()
   with self.assertRaises(PlatformError):await s.accounts.rename(uid,other['username'])
   self.assertEqual((await s.get_user(uid))['renameCredits'],'2')
   results=await asyncio.gather(*(s.accounts.rename(uid,'Name_'+secrets.token_hex(3)) for _ in range(4)),return_exceptions=True)
   self.assertEqual(sum(isinstance(x,dict) for x in results),2);self.assertEqual((await s.get_user(uid))['renameCredits'],'0')
   self.assertEqual((await s.get_user(uid))['coins'],'300')
   with self.assertRaises(PlatformError):await s.equip_store_item(uid,'rename_card')
   with self.assertRaises(PlatformError):await s.update_profile(uid,display_name='Bypass_'+secrets.token_hex(3))
 async def test_name_claim_race_and_invalid_names(self):
  for s in self.services:
   a,b=await s.accounts.guest(),await s.accounts.guest();name='Unique_'+secrets.token_hex(3)
   result=await asyncio.gather(s.accounts.rename(a['id'],name),s.accounts.rename(b['id'],name),return_exceptions=True)
   self.assertEqual(sum(isinstance(x,dict) for x in result),1);loser=b if isinstance(result[0],dict) else a
   self.assertTrue(public_user(await s.get_user(loser['id']))['freeRenameAvailable'])
   for value in ['@hello','a','name with space']:
    with self.assertRaises(PlatformError):await s.accounts.rename(loser['id'],value)

if __name__=='__main__':unittest.main(verbosity=2)
