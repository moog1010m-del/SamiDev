"""Record targeted security and compatibility checks for this patch."""
from pathlib import Path
import datetime
import json
import os
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
commands=[
    ['node','tests/game_security_runtime.js'],
    [sys.executable,'tests/game_security_store.py'],
    [sys.executable,'tests/game_security_ws.py'],
    [sys.executable,'tests/game_security_config.py'],
    ['node','tests/game_security_client_sync.js'],
    ['node','tests/turn_authority_regression.js'],
    ['node','tests/state_checkpoint_regression.js'],
    ['node','tests/gamehost_conformance.js'],
    ['node','tests/timeout_afk_regression.js'],
    ['node','tests/turn_resize_race_regression.js'],
    [sys.executable,'tests/store_authority_epoch_regression.py'],
    [sys.executable,'tests/store_sequence_regression.py'],
    [sys.executable,'tests/store_rewards_v23_regression.py'],
]
report={'date':datetime.datetime.now(datetime.timezone.utc).isoformat(),'ok':True,
        'limitations':['No production load test or actual phone browser test','Redis only tested if SAMIDEV_TEST_REDIS_URL is supplied'],
        'tests':[]}
for command in commands:
    try:
        result=subprocess.run(command,cwd=ROOT,env={**os.environ,'PYTHONPATH':str(ROOT)+os.pathsep+str(ROOT/'backend')},capture_output=True,text=True,timeout=90)
        item={'command':' '.join('python' if c==sys.executable else c for c in command),'passed':result.returncode==0,
              'exitCode':result.returncode,'output':result.stdout+result.stderr}
    except subprocess.TimeoutExpired:
        item={'command':' '.join(command),'passed':False,'output':'Timed out'}
    report['tests'].append(item);report['ok'] &= item['passed']
    print(item['command'],'PASS' if item['passed'] else 'FAIL',flush=True)
    if not item['passed']:print(item['output'],flush=True)
(ROOT/'GAME_SECURITY_TEST_REPORT.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
sys.exit(0 if report['ok'] else 1)
