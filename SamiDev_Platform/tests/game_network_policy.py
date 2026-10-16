"""Actual browser egress checks with production CSP, without live credentials."""
import asyncio, os, sys
from pathlib import Path
from aiohttp import web
from aiohttp.test_utils import TestServer
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
os.environ.update(SAMIDEV_STORE='memory',SAMIDEV_PLATFORM_STORE='memory',SAMIDEV_FIREBASE_AUTH='0',SAMIDEV_PRODUCTION='0')
import app as application
async def main():
    application.SERVICE.platform.firebase.enabled=True
    application.SERVICE.platform.firebase.project='network-policy-test'
    app=web.Application()
    app.on_response_prepare.append(application.security_headers)
    async def config(request):return web.Response(text='',content_type='application/javascript')
    async def store(request):return web.json_response({'ok':True,'equipped':{},'catalog':[]})
    app.router.add_get('/client-config.js',config)
    app.router.add_get('/api/store',store)
    app.router.add_static('/',ROOT/'game')
    async with TestServer(app) as server:
        proc=await asyncio.create_subprocess_exec('node',str(ROOT/'tests/game_network_policy.mjs'),env=dict(os.environ,SAMIDEV_TEST_BASE_URL=str(server.make_url(''))))
        assert await proc.wait()==0,'Game network policy browser checks failed'
if __name__=='__main__':asyncio.run(main())
