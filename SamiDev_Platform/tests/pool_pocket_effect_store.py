"""Pocket-effect ownership, price, persisted equip and server-authorized room cosmetics."""
import asyncio,sys,pathlib,types
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'backend'))
from social_platform import PlatformService,PlatformError,STORE_CATALOG
from app import SamiDevRealtime
async def main():
 p=PlatformService(None);u=await p.create_user('water_effect_check','Test-password-123');uid=u['id'];item='pool_pocket_water'
 assert STORE_CATALOG[item]['price']==5000 and not STORE_CATALOG[item]['availableToAll']
 async def rejects(call,code):
  try:await call()
  except PlatformError as e:assert e.code==code,e.code
  else:raise AssertionError('Expected '+code)
 await rejects(lambda:p.equip_store_item(uid,item),'STORE_ITEM_NOT_OWNED')
 p.mem_users[uid]['coins']='4999';await rejects(lambda:p.buy_store_item(uid,item),'STORE_INSUFFICIENT_COINS')
 p.mem_users[uid]['coins']='5000';await p.buy_store_item(uid,item);await p.equip_store_item(uid,item)
 snapshot=await p.store_snapshot(uid);assert snapshot['coins']==0 and snapshot['equipped']['pool_pocket_effect']==item
 await rejects(lambda:p.buy_store_item(uid,item),'STORE_ALREADY_OWNED');assert (await p.store_snapshot(uid))['coins']==0
 class Accounts:
  async def account_ids_for_room(self,rid):return {0:uid,1:None}
 service=types.SimpleNamespace(store=Accounts(),platform=p)
 cosmetics=await SamiDevRealtime.room_cosmetics(service,'TEST',{'gameId':'pool'})
 assert cosmetics['0']['pool_pocket_effect']==item and cosmetics['1']['pool_pocket_effect']=='pool_pocket_default'
 await p.equip_store_item(uid,'pool_pocket_default');assert (await p.store_snapshot(uid))['equipped']['pool_pocket_effect']=='pool_pocket_default'
 print('WATER_EFFECT_STORE_PASS: price=5000; unowned/insufficient/duplicate rejected; exact debit; equipped owner cosmetics; default reset')
asyncio.run(main())
