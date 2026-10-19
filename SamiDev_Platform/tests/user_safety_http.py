"""Authenticated block API + live WebSocket/HTTP delivery, using disposable memory accounts."""
import asyncio,json,os,sys
from pathlib import Path
from aiohttp import web,ClientSession
from aiohttp.test_utils import TestServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
os.environ.update(SAMIDEV_FIREBASE_AUTH='0',SAMIDEV_PRODUCTION='0')
from social_platform import PlatformService,PlatformHttp,PlatformError
from user_safety import block_user
from store import MemoryStore
import community_socket

async def main():
 p=PlatformService();api=PlatformHttp(p,MemoryStore())
 users=[await p.create_user(n,'Test-password-123') for n in ('BlockReader','BlockSender')]
 tokens=[await p.create_session(u['id']) for u in users]
 @web.middleware
 async def errors(request,handler):
  try:return await handler(request)
  except PlatformError as error:return web.json_response({'ok':False,'error':error.code},status=error.status)
 app=web.Application(middlewares=[errors])
 app.router.add_post('/api/users/{user_id}/block',lambda r:block_user(api,r))
 app.router.add_get('/api/communities/{community_id}',api.community_state)
 app.router.add_get('/ws/community/{community_id}',lambda r:community_socket.serve(api,r))
 async with TestServer(app) as server,ClientSession(cookies={'samidev_session':tokens[0]}) as reader,ClientSession(cookies={'samidev_session':tokens[1]}) as sender,ClientSession() as anon:
  path='/api/users/'+users[1]['id']+'/block'
  async with anon.post(server.make_url(path),json={'blocked':True}) as response:assert response.status==401
  async with reader.post(server.make_url(path),json={'blocked':'true'}) as response:assert response.status==400
  await p.touch_community(users[0]['id'],'majlis');await p.touch_community(users[1]['id'],'majlis')
  async with reader.ws_connect(server.make_url('/ws/community/majlis')) as socket:
   snapshot=await socket.receive_json();assert snapshot['type']=='snapshot'
   async with reader.post(server.make_url(path),json={'blocked':True}) as response:assert response.status==200
   snapshot=await socket.receive_json();assert snapshot['type']=='snapshot'
   await p.append_community_chat(users[1]['id'],'majlis','hidden for reader')
   await p.append_community_chat(users[0]['id'],'majlis','visible for reader')
   event=await asyncio.wait_for(socket.receive_json(),3)
   assert event['type']=='message' and event['message']['userId']==users[0]['id'],event
   for client,count in ((reader,1),(sender,2)):
    async with client.get(server.make_url('/api/communities/majlis')) as response:
     data=await response.json();assert response.status==200 and len(data['messages'])==count,data
   async with reader.post(server.make_url(path),json={'blocked':False}) as response:assert response.status==200
   snapshot=await socket.receive_json();assert len(snapshot['messages'])==2,snapshot
 print('USER_SAFETY_HTTP_PASS: authenticated bool-only API; live messages/history; other viewers unaffected; unblock resync')
if __name__=='__main__':asyncio.run(main())
