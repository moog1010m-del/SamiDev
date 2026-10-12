"""Completion notices follow persisted rewards and never reach spectators."""
import asyncio
import json
import sys
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from app import SamiDevRealtime

async def main():
 service=SamiDevRealtime()
 a=await service.platform.create_user('reward_a','Test-password-123')
 b=await service.platform.create_user('reward_b','Test-password-123')
 room=await service.store.create_room('A',{'players':0,'gameId':'pool'},'node','a',a['id'])
 rid=room['roomId']
 await service.store.join_room(rid,'B',None,'node','b',b['id'])
 messages=[]
 async def send(c,payload):messages.append((c.conn_id,payload))
 service.send=send
 service.connections={k:SimpleNamespace(conn_id=k,seat=seat,spectator=seat<0) for k,seat in [('a',0),('b',1),('viewer',-1)]}
 service.room_local[rid]=set(service.connections)
 await service._award_daily_match_rewards(rid,{'gameOver':False})
 assert not messages
 await service._award_daily_match_rewards(rid,{'gameOver':True})
 assert len(messages)==2
 assert {c for c,p in messages}=={'a','b'}
 for c,p in messages:
  assert p['type']=='match_reward' and p['amount']==50 and p['rewardedMatches']==1 and p['remainingMatches']==4
  uid=a['id'] if c=='a' else b['id']
  assert (await service.platform.get_user(uid))['coins']=='50'
 await service._award_daily_match_rewards(rid,{'gameOver':True})
 assert len(messages)==2,'Repeated authority events must not repeat notifications'
 print(json.dumps({'ok':True,'checks':['No notice before completion','Persisted 50 coins precede each player notice','Spectators excluded','Repeated completion does not duplicate notices']}))
asyncio.run(main())
