"""Profile biography persists independently of paid/free username changes."""
import asyncio,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from social_platform import PlatformService,PlatformError,public_user
async def main():
 service=PlatformService(None);user=await service.create_user('bio_owner','Test-password-123')
 before=public_user(user)
 updated=await service.update_profile(user['id'],bio='أحب البلياردو ⚡\nأهلًا بالجميع',update_bio=True)
 assert public_user(await service.get_user(user['id']))['bio']=='أحب البلياردو ⚡\nأهلًا بالجميع'
 assert public_user(updated)['username']==before['username']
 assert public_user(updated)['freeRenameAvailable']==before['freeRenameAvailable']
 for invalid in ['x'*161,None,{'role':'admin'}]:
  try:await service.update_profile(user['id'],bio=invalid,update_bio=True)
  except PlatformError as e:assert e.code=='INVALID_BIO'
  else:raise AssertionError('Invalid biography accepted')
 await service.update_profile(user['id'],bio='',update_bio=True)
 assert public_user(await service.get_user(user['id']))['bio']==''
 print('PROFILE_BIO_PASS: persisted, bounded, removable, no rename credit consumed')
asyncio.run(main())
