import sys, pathlib, asyncio, json
from types import SimpleNamespace
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parents[1]/'backend'))
from social_platform import PlatformService, PlatformError
from store import MemoryStore
from web_challenges import WebChallenges
async def main():
 p=PlatformService(None);users=[await p.create_user(n,'Test-password-123') for n in ['challenge_one','challenge_two','challenge_other']]
 for u in users:await p.touch_community(u['id'],'majlis')
 current=users[0]
 async def user(r):return current
 async def body(r):return r.body
 api=SimpleNamespace(platform=p,room_store=MemoryStore(),_user=user,_body=body);c=WebChallenges(api)
 async def req(data=None):return json.loads((await c.request(SimpleNamespace(method='POST' if data else 'GET',headers={'X-Plazr-Client':'web'},body=data))).text)
 async def bad(data,code):
  try:await req(data)
  except PlatformError as e:assert e.code==code,(e.code,code)
  else:raise AssertionError(code)
 a,b,o=[u['id'] for u in users];await c.presence(a,'web');await c.presence(b,'app')
 payload={'action':'send','target':b,'gameId':'pool','community':'majlis'}
 await bad(payload,'APP_USER');await c.presence(b,'web');await req(payload)
 response=await req();row=response['challenge'];ident=row['id'];assert row['status']=='pending';assert row['largeTable']==0;assert 29<=row['expires']-response['serverNow']<=30
 await bad(payload,'BUSY')
 await req({'action':'cancel','id':ident});assert (await req())['challenge']['status']=='cancelled'
 await req(payload);ident=(await req())['challenge']['id'];current=users[1]
 await req({'action':'reject','id':ident});assert (await req())['challenge']['status']=='rejected';current=users[0]
 await req(payload);ident=(await req())['challenge']['id'];expired=await c.get('id:'+ident);expired['expires']=0;await c.put('id:'+ident,expired)
 assert (await req())['challenge']['status']=='expired';await bad({'action':'accept','id':ident},'EXPIRED')
 await req({**payload,'largeTable':1});pending=(await req())['challenge'];ident=pending['id'];assert pending['largeTable']==1;current=users[2];await bad({'action':'accept','id':ident},'NOT_FOUND')
 current=users[1];await req({'action':'accept','id':ident,'largeTable':0});row=(await req())['challenge'];assert row['status']=='accepted' and 'token' not in row and 'hostToken' not in row
 rid=row['roomId'];room=await api.room_store.get_room_state(rid);assert room['capacity']==2 and room['settings']['largeTable']==1,'acceptance preserves sender mode, not accepting payload'
 current=users[0];row=(await req())['challenge'];assert row['token'];await c.allowed(rid,a);await c.allowed(rid,b)
 try:await c.allowed(rid,o)
 except PlatformError as e:assert e.code=='INVITE_RESERVED'
 else:raise AssertionError('reservation')
 host=await api.room_store.join_room(rid,'Host',row['token'],'test-node','host-real',a)
 guest=await api.room_store.join_room(rid,'Guest',None,'test-node','guest-real',b)
 assert host['seat']==0 and guest['seat']==1
 assert host['settings']['largeTable']==guest['settings']['largeTable']==1
 await bad({'action':'cancel','id':ident},'EXPIRED')
 await p.safety.update(a,b,True);await bad(payload,'BLOCKED')
 # Hybrid Redis/Postgres must never open a social-document transaction for
 # challenge coordination, since acceptance also reads safety and admission.
 from contextlib import asynccontextmanager
 class Transient:
  @asynccontextmanager
  async def lock(self,*args,**kwargs):yield
 class Social:
  transient=Transient()
 class Accounts:
  def transaction(self,*args):raise AssertionError('nested social transaction')
 hybrid=WebChallenges(SimpleNamespace(platform=SimpleNamespace(r=Social(),accounts=Accounts())))
 async with hybrid.transaction(['challenge-key']):pass
 print('WEB_CHALLENGES_PASS: app refusal; pending; busy; authorization; accept; two seats; token isolation; reservation; replay; blocking')
asyncio.run(main())
