"""Authenticated admission, real pool authority, chat ownership and live delivery."""
import asyncio,json,os,subprocess,time
import aiohttp
from aiohttp import web
os.environ.update(SAMIDEV_PLATFORM_STORE='memory',SAMIDEV_FIREBASE_AUTH='0',SAMIDEV_PRODUCTION='0',SAMIDEV_ADMIN_USERNAME='',SAMIDEV_ADMIN_PASSWORD='')
from multigame_ws import ROOT,GH_PORT,GH,app,receive
from room_policy import DEFAULTS

async def main():
    proc=subprocess.Popen(['node',str(ROOT/'gamehost/server.js')],cwd=ROOT,env=dict(os.environ,SAMIDEV_GAMEHOST_HOST='127.0.0.1',SAMIDEV_GAMEHOST_PORT=str(GH_PORT)),stdout=subprocess.DEVNULL)
    runner=None;sessions=[];sockets=[]
    service=app.SERVICE.platform
    try:
        probe=aiohttp.ClientSession();sessions.append(probe)
        for _ in range(100):
            try:
                async with probe.get(GH+'/health') as response:
                    if response.status==200:break
            except aiohttp.ClientError:pass
            await asyncio.sleep(.05)
        else:raise AssertionError('GameHost unavailable')
        users=[]
        for i in range(4):users.append(await service.create_user('room_policy_'+str(i),'Test-password-123',role='admin' if i==0 else 'user'))
        runner=web.AppRunner(app.make_app());await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start();base=f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'
        async def request(client,path,body=None,method=None):
            async with client.request(method or ('POST' if body is not None else 'GET'),base+path,json=body) as response:return response.status,await response.json()
        for user in users:
            client=aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True),headers={'Origin':'http://localhost'});sessions.append(client)
            assert (await request(client,'/api/auth/login',{'username':user['username'],'password':'Test-password-123'}))[0]==200
        clients=sessions[1:]
        config={**DEFAULTS,'maxMembers':1,'maxTables':1}
        path='/api/admin/communities/majlis/policy'
        assert (await request(clients[1],path,config,'PUT'))[0]==403
        assert (await request(clients[0],path,{**config,'maxTables':True},'PUT'))[0]==400
        assert (await request(clients[0],path,config,'PUT'))[0]==200
        assert (await request(clients[1],'/api/communities/majlis/enter',{}))[0]==200
        status,data=await request(clients[2],'/api/communities/majlis/enter',{});assert status==409 and data['error']=='COMMUNITY_FULL',data
        assert (await request(clients[0],path,{**config,'maxMembers':200},'PUT'))[0]==200
        async def ws(client):
            sock=await client.ws_connect(base+'/ws');sockets.append(sock);return sock
        a,b,duplicate,other=[await ws(c) for c in (clients[1],clients[2],clients[1],clients[3])]
        await a.send_json({'type':'create_room','settings':{'gameId':'pool'}});created=await receive(a,'created');assert created['type']=='created',created;rid=created['roomId']
        await duplicate.send_json({'type':'create_room','settings':{'gameId':'pool'}});assert (await receive(duplicate,'created'))['code']=='ACCOUNT_IN_MATCH'
        await other.send_json({'type':'create_room','settings':{'gameId':'pool'}});assert (await receive(other,'created'))['code']=='COMMUNITY_TABLE_LIMIT'
        await b.send_json({'type':'join_room','roomId':rid});assert (await receive(b,'joined'))['type']=='joined'
        for sock in [a,b]:await receive(sock,'start');await sock.send_json({'type':'runtime_ready'})
        for sock in [a,b]:await receive(sock,'begin_match')
        assert (await app.SERVICE.store.get_room_state(rid))['begunAt']>0
        await a.send_json({'type':'chat_send','stickerId':'chat_ember'});assert (await receive(a,'chat_message'))['code']=='STICKER_NOT_OWNED'
        service.mem_inventory[users[1]['id']].add('badge_crown')
        await a.send_json({'type':'chat_send','stickerId':'badge_crown'});entry=await receive(b,'chat_message');assert entry['stickerId']=='badge_crown' and entry['stickerAsset'].startswith('/platform/assets/'),entry
        await a.send_json({'type':'move','packet':{'i':'ready','n':0,'m':{'__ready':1}}});await receive(a,'move');await receive(b,'move')
        await a.send_json({'type':'move','packet':{'i':'resign','n':1,'m':{'a':0}}});await receive(a,'move');await receive(b,'move')
        await duplicate.send_json({'type':'create_room','settings':{'gameId':'pool'}});assert (await receive(duplicate,'created'))['code']=='MATCH_COOLDOWN'
        await other.send_json({'type':'create_room','settings':{'gameId':'pool'}});assert (await receive(other,'created'))['type']=='created'
        await other.send_json({'type':'leave_room'});assert (await receive(other,'left_room'))['type']=='left_room'
        await other.send_json({'type':'create_room','settings':{'gameId':'pool'}});assert (await receive(other,'created'))['code']=='MATCH_COOLDOWN'
        # Reject arbitrary asset URLs and unowned stickers in the public chat too.
        status,data=await request(clients[2],'/api/communities/majlis/chat',{'stickerId':'badge_crown','clientMessageId':'not_owned_123'});assert status==403,data
        status,data=await request(clients[1],'/api/communities/majlis/chat',{'stickerId':'badge_crown','clientMessageId':'owned_sticker_123'});assert status==200 and data['message']['stickerId']=='badge_crown',data
        status,retry=await request(clients[1],'/api/communities/majlis/chat',{'stickerId':'badge_crown','clientMessageId':'owned_sticker_123'});assert retry['message']['id']==data['message']['id']
        # Local stream consumers must not wait on a slow Redis publisher.
        class SlowRedis:
            async def publish(self,*args):await asyncio.sleep(1)
        live=service.live;original=service.r;service.r=SlowRedis()
        queue=asyncio.Queue();live.listeners['majlis']={queue}
        start=time.monotonic();task=asyncio.create_task(live.publish('majlis',{'type':'message','message':{'id':'latency'}}))
        event=await asyncio.wait_for(queue.get(),.2);assert event['message']['id']=='latency';elapsed=time.monotonic()-start
        await task;service.r=original;live.listeners.pop('majlis',None)
        from social_platform import STORE_CATALOG,public_user
        assert 'badge_palm_swords' not in STORE_CATALOG
        assert public_user({'nameBadge':'badge_palm_swords'})['nameBadgeAsset']==''
        print(json.dumps({'ok':True,'localLiveMilliseconds':round(elapsed*1000,2),'checks':['admin-only validated policy','member/table caps','same-account concurrency blocked','short-match cooldown','owned stickers only','sticker retry idempotency','slow Redis does not delay local chat','removed default badge']},ensure_ascii=False))
    finally:
        for sock in sockets:await sock.close()
        for client in sessions:await client.close()
        if runner:await runner.cleanup()
        proc.terminate();proc.wait(timeout=10)
if __name__=='__main__':asyncio.run(main())
