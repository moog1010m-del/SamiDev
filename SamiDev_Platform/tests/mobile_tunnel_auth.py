"""Real HTTP auth behind a simulated HTTPS-terminating tunnel; no public mutations."""
import argparse
import asyncio
import os
from pathlib import Path
import sys
import subprocess
import aiohttp
from aiohttp import web

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT),str(ROOT/'backend')]
from start_dev import configure_public_proxy,public_origin,free_port,wait_json,terminate
ORIGIN=public_origin('https://mobile.example.test/')
GH_PORT=free_port()
env={'SAMIDEV_PRODUCTION':'0','SAMIDEV_STORE':'memory','SAMIDEV_GAMEHOST_URL':f'http://127.0.0.1:{GH_PORT}'}
configure_public_proxy(env,ORIGIN,56648)
os.environ.update(env)
import app

async def main():
    for value in ['http://example.test','https://user:pass@example.test','https://example.test/path','https://example.test?a=1','https://good.test,https://bad.test']:
        try:public_origin(value)
        except argparse.ArgumentTypeError:pass
        else:raise AssertionError(value)
    untouched={};configure_public_proxy(untouched,None,56648);assert untouched=={}
    assert env['SAMIDEV_TRUST_PROXY']=='0' and env['SAMIDEV_TRUST_FORWARDED_HTTPS']=='1' and '*' not in env['SAMIDEV_ALLOWED_ORIGINS']
    process=subprocess.Popen(['node',str(ROOT/'gamehost/server.js')],cwd=ROOT,env=dict(os.environ,SAMIDEV_GAMEHOST_HOST='127.0.0.1',SAMIDEV_GAMEHOST_PORT=str(GH_PORT)),stdout=subprocess.DEVNULL)
    wait_json(f'http://127.0.0.1:{GH_PORT}/health')
    runner=web.AppRunner(app.make_app());await runner.setup()
    site=web.TCPSite(runner,'127.0.0.1',0);await site.start()
    url=f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'
    try:
        async with aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar(),headers={'Origin':ORIGIN,'X-Forwarded-Proto':'https'}) as client:
            body={'username':'mobile_tunnel_test','password':'Mobile-test-password-123'}
            # Reproduce the default dev server: TLS ended at tunnel, Secure is absent.
            app.SERVICE.platform_http.trust_forwarded_https=False
            async with client.post(url+'/api/auth/register',json=body) as response:
                assert response.status==200,await response.text()
                assert not response.cookies['samidev_session']['secure']
            # With the explicit tunnel config, registration and login carry Secure.
            app.SERVICE.platform_http.trust_forwarded_https=True
            for route,payload in [('/api/auth/register',{**body,'username':'mobile_tunnel_new'}),('/api/auth/login',body)]:
                async with client.post(url+route,json=payload) as response:
                    assert response.status==200,await response.text()
                    cookie=response.cookies['samidev_session']
                    assert cookie['secure'] and cookie['httponly']
                    token=cookie.value
                    assert (await response.json())['ok']
            async with client.get(url+'/api/me',headers={'Cookie':f'samidev_session={token}'}) as response:
                assert response.status==200
            async with client.post(url+'/api/auth/login',json=body,headers={'Origin':'https://attacker.invalid'}) as response:
                assert response.status==403
            async with client.post(url+'/api/auth/login',json={**body,'password':'incorrect-password'}) as response:
                assert response.status==401 and 'Set-Cookie' not in response.headers
            async with client.post(url+'/api/auth/logout',json={},headers={'Cookie':f'samidev_session={token}'}) as response:
                assert response.status==200
            async with client.get(url+'/api/me',headers={'Cookie':f'samidev_session={token}'}) as response:
                assert response.status==401
        print('PASS: reproduced missing Secure; tunnel registration/login issue Secure + HttpOnly; session works, logout revokes it and hostile Origin is denied')
    finally:
        await runner.cleanup()
        terminate(process)

if __name__=='__main__':asyncio.run(main())
