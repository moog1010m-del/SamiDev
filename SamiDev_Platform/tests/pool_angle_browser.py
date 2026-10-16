"""Real two-browser pool regression with an isolated memory gateway and Node host.

Run with the project Python environment; SAMIDEV_PLAYWRIGHT_MODULE may point to
an installed playwright-core module. No production database or accounts are used.
"""
import asyncio
import os
import subprocess

os.environ.update(SAMIDEV_PLATFORM_STORE='memory', SAMIDEV_FIREBASE_AUTH='0',
                  SAMIDEV_PRODUCTION='0', SAMIDEV_TRUST_PROXY='1')
from multigame_ws import ROOT, GH_PORT, GH, app
from aiohttp import web, ClientSession


async def main():
    host = subprocess.Popen(['node', str(ROOT/'gamehost/server.js')], cwd=ROOT,
        env=dict(os.environ, SAMIDEV_GAMEHOST_HOST='127.0.0.1',
                 SAMIDEV_GAMEHOST_PORT=str(GH_PORT)), stdout=subprocess.DEVNULL)
    runner = None
    try:
        async with ClientSession() as session:
            for _ in range(100):
                try:
                    async with session.get(GH+'/health') as response:
                        if response.status == 200:
                            break
                except OSError:
                    pass
                await asyncio.sleep(.05)
            else:
                raise RuntimeError('Test GameHost did not become healthy')
        runner = web.AppRunner(app.make_app())
        await runner.setup()
        site = web.TCPSite(runner, '127.0.0.1', 0)
        await site.start()
        base = f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'
        app.ALLOWED_ORIGINS.add(base)
        child = await asyncio.create_subprocess_exec('node',
            str(ROOT/'tests/pool_contract_browser.mjs'),
            env=dict(os.environ, SAMIDEV_TEST_BASE_URL=base))
        if await child.wait():
            raise RuntimeError('Pool browser contract failed')
    finally:
        if runner:
            await runner.cleanup()
        host.terminate()
        host.wait(timeout=10)


if __name__ == '__main__':
    asyncio.run(main())
