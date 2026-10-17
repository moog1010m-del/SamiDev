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
    from room_policy import DEFAULTS
    # This suite starts two short test matches back-to-back; cooldown policy
    # has its own dedicated tests and is disabled only in this isolated fixture.
    await app.SERVICE.platform.room_policy.configure('majlis', {**DEFAULTS, 'cooldownSeconds':0})
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
        application = app.make_app()
        @web.middleware
        async def shared_game_host(request, handler):
            if request.path == '/games/pool/index.html' and request.method in {'GET','HEAD'}:
                return web.FileResponse(ROOT/'game/game-host.html')
            return await handler(request)
        application.middlewares.append(shared_game_host)
        runner = web.AppRunner(application)
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
