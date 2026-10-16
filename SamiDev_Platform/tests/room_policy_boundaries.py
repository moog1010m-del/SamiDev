"""Boundary behavior through real memory store and quick matchmaking methods."""
import asyncio,os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
os.environ['SAMIDEV_FIREBASE_AUTH']='0'
from social_platform import PlatformService,PlatformError
from room_policy import DEFAULTS
from store import MemoryStore,StoreError
from quick_play import QuickPlay
async def main():
 service=PlatformService();policy=service.room_policy;store=MemoryStore();quick=QuickPlay(store)
 users=[await service.create_user('boundary_'+str(i),'Test-password-123') for i in range(4)]
 await policy.configure('diwan',{**DEFAULTS,'maxTables':1})
 async def match(user,preset,conn):
  async with policy.transaction():
   create=await policy.admit(store,user['id'],'diwan','quick_play',{'preset':preset})
   return await quick.match(preset,user['username'],'node',conn,user['id'],'diwan',allow_create=create)
 room,created=await match(users[0],'pool-eight','a');assert created
 joined,created=await match(users[1],'pool-eight','b');assert not created and joined['roomId']==room['roomId']
 try:await match(users[2],'pool-nine','c');raise AssertionError('quick play exceeded table cap')
 except StoreError as error:assert error.code=='COMMUNITY_TABLE_LIMIT'
 assert len(store.rooms)==1
 await store.runtime_ready(room['roomId'],0,'a',1);await store.runtime_ready(room['roomId'],1,'b',1)
 # A match at the three-minute boundary is not a short match.
 clock=await policy.clock()
 async def now():return clock
 policy.clock=now
 store.rooms[room['roomId']].begun_at=clock-180000
 await policy.finish(store,room['roomId'])
 assert await policy.read('cooldown:'+users[0]['id'])==0
 assert await policy.read('cooldown:'+users[1]['id'])==0
 # Admission via WebSocket also reserves a member slot; HTTP enter is optional.
 await policy.configure('elite',{**DEFAULTS,'maxMembers':1})
 async with policy.transaction():await policy.admit(store,users[2]['id'],'elite','create_room',{})
 try:
  async with policy.transaction():await policy.admit(store,users[3]['id'],'elite','create_room',{})
  raise AssertionError('direct socket bypassed member capacity')
 except StoreError as error:assert error.code=='COMMUNITY_FULL'
 await policy.configure('elite',{**DEFAULTS,'maxMembers':1,'cooldownSeconds':0})
 await policy.departed({'communityId':'elite'},users[2]['id'])
 async with policy.transaction():assert await policy.admit(store,users[2]['id'],'elite','create_room',{})
 print('PASS quick join at table cap; blocked quick creation; exact 180-second boundary; direct-WS member reservation; zero cooldown')
if __name__=='__main__':asyncio.run(main())
