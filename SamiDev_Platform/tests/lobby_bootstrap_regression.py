"""Anonymous bootstrap never replaces a saved account; avatar caches revalidate."""
import asyncio, base64, io, os, sys
from pathlib import Path
os.environ.update(SAMIDEV_FIREBASE_AUTH='0',SAMIDEV_STORE='memory',SAMIDEV_PLATFORM_STORE='memory')
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
from aiohttp import web, ClientSession
from aiohttp.test_utils import TestClient, TestServer
from PIL import Image
from social_platform import PlatformService, PlatformHttp, PlatformError, SESSION_COOKIE
from store import MemoryStore
from app import security_headers

async def main():
    service=PlatformService();api=PlatformHttp(service,MemoryStore())
    @web.middleware
    async def errors(request,handler):
        try:return await handler(request)
        except PlatformError as e:return web.json_response({'ok':False,'error':e.code},status=e.status)
    app=web.Application(middlewares=[errors]);app.on_response_prepare.append(security_headers)
    app.router.add_get('/api/me',api.me);app.router.add_post('/api/auth/guest',api.guest)
    app.router.add_get('/api/avatar/{user_id}',api.avatar_image);app.router.add_patch('/api/profile',api.profile_update)
    async with TestClient(TestServer(app)) as client:
        assert (await client.get('/api/me')).status==401
        first=await client.post('/api/auth/guest',json={});assert first.status==200
        guest=(await first.json())['user'];assert guest['isGuest'] and isinstance(guest['showcaseItems'],list)
        assert 'no-store' in first.headers['Cache-Control']
        repeated=await client.post('/api/auth/guest',json={});assert (await repeated.json())['user']['id']==guest['id']
        assert 'Set-Cookie' not in repeated.headers and len(service.mem_users)==1
        saved=await service.create_user('Saved_Owner','Test-password-123',role='admin');saved['coins']='123'
        token=await service.create_session(saved['id'])
        client.session.cookie_jar.update_cookies({SESSION_COOKIE:token},response_url=client.make_url('/'))
        before=(await (await client.get('/api/me')).json())['user']
        resumed=await client.post('/api/auth/guest',json={});restored=(await resumed.json())['user']
        assert restored==before and restored['role']=='admin' and (await service.get_user(saved['id']))['coins']=='123' and not restored['isGuest']
        assert len(service.mem_users)==2 and 'Set-Cookie' not in resumed.headers
        def avatar(color):
            buf=io.BytesIO();Image.new('RGB',(64,64),color).save(buf,format='PNG')
            return 'data:image/png;base64,'+base64.b64encode(buf.getvalue()).decode()
        assert (await client.patch('/api/profile',json={'avatarData':avatar('red')})).status==200
        path='/api/avatar/'+saved['id']
        response=await client.get(path);assert response.status==200
        old_bytes=await response.read();etag=response.headers['ETag'];assert 'private' in response.headers['Cache-Control'] and 'no-cache' in response.headers['Cache-Control']
        unchanged=await client.get(path,headers={'If-None-Match':etag});assert unchanged.status==304 and not await unchanged.read()
        weak=await client.get(path,headers={'If-None-Match':'W/'+etag});assert weak.status==304
        assert (await client.patch('/api/profile',json={'avatarData':avatar('blue')})).status==200
        changed=await client.get(path,headers={'If-None-Match':etag});assert changed.status==200 and changed.headers['ETag']!=etag and await changed.read()!=old_bytes
        async with ClientSession() as anonymous:
            public=await anonymous.get(client.make_url(path));assert public.status==200 and public.headers['Content-Type'].startswith('image/')
        assert (await client.patch('/api/profile',json={'avatarData':''})).status==200
        removed=await client.get(path,headers={'If-None-Match':changed.headers['ETag']});assert removed.status==204 and 'no-store' in removed.headers['Cache-Control']
    print('LOBBY_BOOTSTRAP_PASS: one guest identity, restored owner/coins/session, unchanged 401 protection; conditional avatars refresh on change/removal')

if __name__=='__main__':asyncio.run(main())
