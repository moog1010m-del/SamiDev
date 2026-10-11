"""Serve the real platform and drive its DOM against real account/community APIs."""
import asyncio
import os
from pathlib import Path
import subprocess
import sys

from aiohttp import web

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from start_dev import free_port, wait_json, terminate
GH_PORT = free_port()
os.environ.pop("SAMIDEV_GAMEHOST_URLS", None)
os.environ.update(SAMIDEV_STORE="memory", SAMIDEV_PRODUCTION="0", SAMIDEV_ALLOWED_ORIGINS="*",
                  SAMIDEV_GAMEHOST_URL=f"http://127.0.0.1:{GH_PORT}")
sys.path.insert(0, str(ROOT / "backend"))
import app


async def main():
    runner = web.AppRunner(app.make_app())
    gamehost = subprocess.Popen(["node", str(ROOT / "gamehost/server.js")], cwd=ROOT,
        env=dict(os.environ, SAMIDEV_GAMEHOST_HOST="127.0.0.1", SAMIDEV_GAMEHOST_PORT=str(GH_PORT)),
        stdout=subprocess.DEVNULL)
    try:
        wait_json(f"http://127.0.0.1:{GH_PORT}/health")
        await runner.setup()
        site = web.TCPSite(runner, "127.0.0.1", 0)
        await site.start()
        url = f"http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}"
        proc = await asyncio.create_subprocess_exec("node", str(ROOT / "tests/mobile_platform_dom.mjs"), url)
        code = await proc.wait()
        if code:
            raise SystemExit(code)
    finally:
        await runner.cleanup()
        terminate(gamehost)


if __name__ == "__main__":
    asyncio.run(main())
