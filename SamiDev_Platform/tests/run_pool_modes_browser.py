"""Spawn isolated local PostgreSQL/Redis services and clean only this fixture."""
import argparse, asyncio, os
from pathlib import Path
from realtime_cluster_fixture import Cluster
async def main(script):
    cluster=Cluster(gateways=1,hosts=1,browser_origins=True)
    try:
        await cluster.start()
        proc=await asyncio.create_subprocess_exec('node',str(Path(__file__).with_name(script)),env=dict(os.environ,SAMIDEV_TEST_BASE_URL=cluster.urls[0]))
        code=await proc.wait()
        if code:raise SystemExit(code)
    finally:await cluster.close()
if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--script',choices=['pool_modes_browser.mjs','pyramid_browser.mjs'],default='pool_modes_browser.mjs')
    asyncio.run(main(parser.parse_args().script))
