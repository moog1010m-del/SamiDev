"""Spawn isolated local PostgreSQL/Redis services and clean only this fixture."""
import asyncio, os
from pathlib import Path
from realtime_cluster_fixture import Cluster
async def main():
    cluster=Cluster(gateways=1,hosts=1,browser_origins=True)
    try:
        await cluster.start()
        proc=await asyncio.create_subprocess_exec('node',str(Path(__file__).with_name('pool_modes_browser.mjs')),env=dict(os.environ,SAMIDEV_TEST_BASE_URL=cluster.urls[0]))
        code=await proc.wait()
        if code:raise SystemExit(code)
    finally:await cluster.close()
if __name__=='__main__':asyncio.run(main())
