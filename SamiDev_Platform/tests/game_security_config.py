"""Unsafe service exposure and production authentication must fail closed."""
import asyncio
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
env={k:v for k,v in os.environ.items() if not k.startswith('SAMIDEV_') and k!='NODE_ENV'}
cases=[
    {'SAMIDEV_GAMEHOST_HOST':'0.0.0.0'},
    {'SAMIDEV_GAMEHOST_HOST':'0.0.0.0','SAMIDEV_GAMEHOST_SERVICE_KEY':'short'},
    {'NODE_ENV':'production'},
    {'SAMIDEV_PRODUCTION':'1','SAMIDEV_GAMEHOST_SERVICE_KEY':'CHANGE_ME_TO_A_LONG_RANDOM_SECRET'},
]
for case in cases:
    result=subprocess.run(['node','gamehost/server.js'],cwd=ROOT,env={**env,**case},capture_output=True,text=True,timeout=5)
    assert result.returncode!=0 and 'A private SAMIDEV_GAMEHOST_SERVICE_KEY' in result.stderr,result

code='''
import asyncio,sys
sys.path.insert(0,'backend')
import app
assert app.REQUIRE_GAME_AUTH is True
app.PRODUCTION_MODE=True
async def reject(expected):
    try: await app.SERVICE.start(None)
    except RuntimeError as e: assert expected in str(e),str(e)
    else: raise AssertionError('Unsafe production startup accepted')
async def main():
    app.REQUIRE_GAME_AUTH=False
    await reject('REQUIRE_GAME_AUTH=1')
    app.REQUIRE_GAME_AUTH=True
    for key in ['short','samidev-local-development-key-change-me','CHANGE_ME_TO_A_LONG_RANDOM_SECRET']:
        app.SERVICE.gamehost.service_key=key
        await reject('private SAMIDEV_GAMEHOST_SERVICE_KEY')
asyncio.run(main())
'''
result=subprocess.run([sys.executable,'-c',code],cwd=ROOT,env=env,capture_output=True,text=True,timeout=5)
assert result.returncode==0,result.stderr
print(json.dumps({'ok':True,'checks':9,'nodeUnsafeExposureRejected':True,'gatewayAuthDefaultOn':True,'productionAuthAndSecretEnforced':True},indent=2))
