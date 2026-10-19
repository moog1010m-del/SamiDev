"""Personal blocks affect UGC and friendships, never game state or other viewers."""
import asyncio,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
os.environ.update(SAMIDEV_FIREBASE_AUTH='0',SAMIDEV_PRODUCTION='0')
from social_platform import PlatformService,PlatformError
from postgres_store import durable_key

async def main():
 p=PlatformService()
 users=[await p.create_user(name,'Test-password-123') for name in ('SafetyOne','SafetyTwo','SafetyOther')]
 a,b,c=[u['id'] for u in users]
 await p.send_friend_request(users[1],users[0]['username'])
 assert durable_key(p.safety.key(a))
 await p.safety.update(a,b,True)
 assert (await p.public_profile(b,a))['blocked'] is True
 assert (await p.public_profile(b,c))['blocked'] is False
 assert not (await p.social_state(users[0]))['requests']
 for sender,target in ((users[0],users[1]),(users[1],users[0])):
  try:await p.send_friend_request(sender,target['username'])
  except PlatformError as e:assert e.code=='USER_BLOCKED'
  else:raise AssertionError('blocked friendship accepted')
 messages=[{'userId':a,'text':'one'},{'userId':b,'text':'two'}]
 assert len((await p.safety.community_event(a,{'type':'snapshot','messages':messages}))['messages'])==1
 assert await p.safety.community_event(a,{'type':'message','message':messages[1]}) is None
 assert (await p.safety.community_event(c,{'type':'snapshot','messages':messages}))['messages']==messages
 class Store:
  async def get_room_state(self,rid):return {'roster':[{'seat':0,'accountId':a},{'seat':1,'accountId':b}]}
 store=Store()
 assert await p.safety.game_event(a,'room',{'type':'chat_message','seat':1},store) is None
 assert (await p.safety.game_event(a,'room',{'type':'chat_history','messages':[{'seat':0},{'seat':1}]},store))['messages']==[{'seat':0}]
 assert (await p.safety.game_event(c,'room',{'type':'chat_message','seat':1},store))['seat']==1
 await p.safety.update(a,b,False)
 assert not (await p.public_profile(b,a))['blocked']
 await p.send_friend_request(users[1],users[0]['username'])
 try:await p.safety.update(a,a,True)
 except PlatformError as e:assert e.code=='SELF_BLOCK'
 else:raise AssertionError('self block allowed')
 print('USER_SAFETY_PASS: viewer isolation, durable namespace, both friendship directions, community and game filtering, unblock')
if __name__=='__main__':asyncio.run(main())
