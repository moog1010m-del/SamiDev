"""Real gateway/host tests for community lifecycle and existing-match isolation."""
import asyncio,json,os,subprocess
import aiohttp
from aiohttp import web
from multigame_ws import ROOT,GH_PORT,GH,app,receive


async def main():
    process=subprocess.Popen(['node',str(ROOT/'gamehost/server.js')],cwd=ROOT,env={**os.environ,'SAMIDEV_GAMEHOST_HOST':'127.0.0.1','SAMIDEV_GAMEHOST_PORT':str(GH_PORT)},stdout=subprocess.DEVNULL)
    sessions=[];sockets=[];runner=None
    def client(token=None):
        value=aiohttp.ClientSession(cookie_jar=aiohttp.CookieJar(unsafe=True),headers={'Origin':'http://localhost'},cookies={'samidev_session':token} if token else None)
        sessions.append(value);return value
    try:
        probe=client()
        for _ in range(100):
            try:
                async with probe.get(GH+'/health') as response:
                    if response.status==200:break
            except aiohttp.ClientError:pass
            await asyncio.sleep(.05)
        runner=web.AppRunner(app.make_app());await runner.setup();site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
        base=f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'
        app.ALLOWED_ORIGINS.add(base)
        p=app.SERVICE.platform;tokens=[]
        for name,role in [('CatalogAdmin','admin'),('CatalogOne','user'),('CatalogTwo','user'),('CatalogOther','user')]:
            user=await p.create_user(name,'Test-password-123',role=role);tokens.append(await p.create_session(user['id']))
        admin,one,two,other=[client(token) for token in tokens]
        async def req(session,method,path,body=None,status=200):
            async with session.request(method,base+path,json=body) as response:
                data=await response.json();assert response.status==status,(path,response.status,data)
                return data
        await req(other,'POST','/api/admin/communities',{'id':'forbidden','name':'No'},403)
        await req(probe,'GET','/api/admin/communities',status=401)
        await req(admin,'POST','/api/admin/communities',{'id':'hangout','name':'Hangout','mark':'☕','description':'A new space'})
        await req(admin,'POST','/api/admin/communities',{'id':'hangout','name':'Duplicate'},409)
        await req(admin,'POST','/api/admin/communities',{'id':'../bad','name':'Bad'},400)
        assert any(c['id']=='hangout' for c in (await req(one,'GET','/api/communities'))['communities'])
        await req(one,'POST','/api/communities/hangout/enter',{})
        await req(one,'POST','/api/communities/hangout/chat',{'text':'تبقى الرسالة محفوظة','clientMessageId':'catalog_message_001'})
        async def socket(session):
            ticket=(await req(session,'POST','/api/game-ticket',{'communityId':'hangout'}))['ticket']
            ws=await session.ws_connect(base+'/ws?ticket='+ticket);sockets.append(ws);return ws
        first=await socket(one);second=await socket(two)
        await first.send_json({'type':'quick_play','preset':'pool-eight'})
        created=await receive(first,'created');assert created['type']=='created',created
        rid=created['roomId']
        await second.send_json({'type':'join_room','roomId':rid});assert (await receive(second,'joined'))['type']=='joined'
        for ws in [first,second]:assert (await receive(ws,'start'))['type']=='start';await ws.send_json({'type':'runtime_ready'})
        for ws in [first,second]:assert (await receive(ws,'begin_match'))['type']=='begin_match'
        await req(admin,'PATCH','/api/admin/communities/hangout',{'enabled':False})
        assert not any(c['id']=='hangout' for c in (await req(other,'GET','/api/communities'))['communities'])
        for method,path,body in [('POST','/api/communities/hangout/enter',{}),('POST','/api/communities/hangout/chat',{'text':'ممنوع','clientMessageId':'catalog_closed_002'}),('GET','/api/communities/hangout',None),('POST','/api/game-ticket',{'communityId':'hangout'})]:
            assert (await req(other,method,path,body,403))['error']=='COMMUNITY_DISABLED'
        # A stale socket cannot use its old ticket to open another game.
        await first.send_json({'type':'create_room','settings':{'gameId':'pool','players':1}})
        assert (await receive(first,'error'))['code']=='COMMUNITY_DISABLED'
        # Its original begun game remains writable and reconnectable.
        await first.send_json({'type':'chat_send','text':'المباراة مستمرة'})
        assert (await receive(first,'chat_message'))['type']=='chat_message'
        await first.close();replacement=await socket(one)
        await replacement.send_json({'type':'join_room','roomId':rid,'token':created['token']})
        assert (await receive(replacement,'joined'))['type']=='joined'
        assert (await receive(replacement,'start'))['type']=='start'
        await req(admin,'PATCH','/api/admin/communities/hangout',{'enabled':True})
        restored=await req(one,'GET','/api/communities/hangout')
        assert any(m['text']=='تبقى الرسالة محفوظة' for m in restored['messages'])
        if os.environ.get('SAMIDEV_COMMUNITY_BROWSER')=='1':
            browser=await asyncio.create_subprocess_exec('node',str(ROOT/'tests/community_admin_browser.mjs'),env={**os.environ,'SAMIDEV_TEST_BASE_URL':base,'SAMIDEV_TEST_ADMIN_SESSION':tokens[0]})
            assert await browser.wait()==0
        print('COMMUNITY_CATALOG_PASS: admin-only create/toggle; public filtering; direct entry/chat/ticket/socket rejection; active match chat and reconnect; preserved history')
    finally:
        for socket in sockets:await socket.close()
        if runner:await runner.cleanup()
        for session in sessions:await session.close()
        process.terminate()
        try:process.wait(timeout=3)
        except subprocess.TimeoutExpired:process.kill();process.wait()


if __name__=='__main__':asyncio.run(main())
