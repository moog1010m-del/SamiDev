"""Real platform handlers + live sidecar subprocess, ephemeral memory and accounts only."""
import asyncio,json,os,sys,tempfile
from pathlib import Path
from aiohttp import web,ClientSession
from aiohttp.test_utils import TestServer
BASE=Path(__file__).resolve().parents[1]
PLATFORM=BASE.parents[1]/'SamiDev_Platform'
sys.path.insert(0,str(PLATFORM/'backend'))
os.environ.update(SAMIDEV_STORE='memory',SAMIDEV_PLATFORM_STORE='memory',SAMIDEV_FIREBASE_AUTH='0',SAMIDEV_PRODUCTION='0')
from social_platform import PlatformService,PlatformHttp,PlatformError
from store import MemoryStore
async def main():
    service=PlatformService();api=PlatformHttp(service,MemoryStore())
    @web.middleware
    async def errors(request,handler):
        try:return await handler(request)
        except PlatformError as error:return web.json_response({'ok':False,'error':error.code},status=error.status)
    app=web.Application(middlewares=[errors])
    app.router.add_get('/api/me',api.me);app.router.add_post('/api/heartbeat',api.heartbeat)
    app.router.add_get('/api/communities/{community_id}',api.community_state)
    app.router.add_post('/api/communities/{community_id}/enter',api.community_enter)
    app.router.add_post('/api/communities/{community_id}/leave',api.community_leave)
    app.router.add_post('/api/communities/{community_id}/chat',api.community_chat)
    app.router.add_get('/ws/community/{community_id}',api.community_socket)
    env=dict(os.environ);bot_ids=set();human=None;token=None
    for username,env_name in [('NawafBot','PLAZR_BOT_NAWAF_SESSION'),('FahadBot','PLAZR_BOT_FAHAD_SESSION'),('HumanTester',None)]:
        user=await service.create_user(username,'Test-password-123');session=await service.create_session(user['id'])
        if env_name:env[env_name]=session;bot_ids.add(user['id'])
        else:human=user;token=session
    # Baseline message must not cause an unsolicited reply on connection.
    await service.append_community_chat(human['id'],'majlis','السلام عليكم','baseline_123')
    process=None
    async with TestServer(app) as server,ClientSession(cookies={'samidev_session':token}) as client:
        with tempfile.TemporaryDirectory() as directory:
            config=json.loads((BASE/'config.example.json').read_text());config.update(cooldown_seconds=5,reply_delay_seconds=0)
            path=Path(directory)/'config.json';path.write_text(json.dumps(config))
            process=await asyncio.create_subprocess_exec(sys.executable,str(BASE/'run.py'),'live','--enable-live','--config',str(path),'--state',str(Path(directory)/'db.sqlite'),'--base-url',str(server.make_url('')).rstrip('/'),env=env,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
            try:
                line=await asyncio.wait_for(process.stdout.readline(),15)
                assert b'snapshot_ready' in line,line
                await asyncio.sleep(.5)
                rows=await service.community_chat_history('majlis');assert not any(r['userId'] in bot_ids for r in rows)
                async with client.post(server.make_url('/api/communities/majlis/enter'),json={}) as response:assert response.status==200
                await asyncio.sleep(5.5)
                for _ in range(2):
                    async with client.post(server.make_url('/api/communities/majlis/chat'),json={'text':'السلام عليكم','clientMessageId':'human_message_123'}) as response:assert response.status==200
                for _ in range(30):
                    rows=await service.community_chat_history('majlis')
                    replies=[r for r in rows if r['userId'] in bot_ids]
                    if replies:break
                    await asyncio.sleep(.2)
                assert len(replies)==1,replies
                assert replies[0]['text']=='وعليكم السلام، حيّاك الله!'
                await asyncio.sleep(.5)
                rows=await service.community_chat_history('majlis');assert len([r for r in rows if r['userId'] in bot_ids])==1
                # A fresh message during cooldown must wait, rather than disappear.
                async with client.post(server.make_url('/api/communities/majlis/chat'),json={'text':'كم الساعة','clientMessageId':'human_cooldown_456'}) as response:assert response.status==200
                for _ in range(40):
                    rows=await service.community_chat_history('majlis')
                    replies=[r for r in rows if r['userId'] in bot_ids]
                    if len(replies)==2:break
                    await asyncio.sleep(.2)
                assert len(replies)==2,replies
                assert 'الساعة الحين' in replies[-1]['text'],replies
                process.terminate();await asyncio.wait_for(process.wait(),10);assert (process.returncode in (0,1) if os.name=='nt' else process.returncode==0)
                if os.name=='nt':
                    for b in bot_ids:await service.leave_community(b,'majlis')
                members=await service.community_members('majlis');assert not ({u['id'] for u in members}&bot_ids)
                # The real room still accepts human messages after the sidecar exits.
                async with client.post(server.make_url('/api/communities/majlis/chat'),json={'text':'التجربة انتهت','clientMessageId':'after_shutdown_123'}) as response:assert response.status==200
                print('SIDECAR_INTEGRATION_PASS: real HTTP/WS; no snapshot replay; one speaker; dedup; no bot loop; graceful leave; chat survives shutdown')
            finally:
                if process.returncode is None:process.kill();await process.wait()
if __name__=='__main__':asyncio.run(main())
