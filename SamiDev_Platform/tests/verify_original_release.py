"""Run the three-game release checks and retain their actual output."""
from pathlib import Path
import datetime
import json
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
commands = [
    ['node', 'tests/crazy8_runtime.js'],
    [sys.executable, 'tests/crazy8_ws.py'],
    ['node', 'tests/multigame_routing.js', 'crazy8'],
    ['node', 'tests/multigame_runtime.js'],
    [sys.executable, 'tests/multigame_ws.py'],
    [sys.executable, 'tests/spectator_lifecycle_regression.py'],
    ['node', 'tests/browser_multigame_smoke.js', 'carrom', 'local', 'carrom_classic'],
    ['node', 'tests/browser_multigame_smoke.js', 'carrom', 'local', 'carrom_cat'],
    ['node', 'tests/browser_multigame_smoke.js', 'carrom', 'local', 'carrom_cat', 'fail-cat'],
    ['node', 'tests/browser_multigame_smoke.js', 'crazy8', 'online'],
    ['node', 'tests/browser_multigame_smoke.js', 'tablesoccer', 'online'],
    ['node', 'tests/carrom_theme_selection.js'],
    [sys.executable, 'tests/carrom_store_regression.py'],
    ['node', 'tests/striker_move_regression.js'],
    [sys.executable, 'tests/original_assets.py'],
    [sys.executable, 'start_dev.py', '--check'],
]
report = {
    'date': datetime.date.today().isoformat(),
    'ok': True,
    'environment': {
        'backend': 'memory',
        'gamehost': 'Node.js',
        'browser': 'VM smoke with real PNG/WebP dimensions and mocked WebGL/audio; no actual graphical browser installed',
        'redisDockerTested': False,
    },
    'tests': [],
}
for command in commands:
    name = ' '.join('python' if c == sys.executable else c for c in command)
    try:
        result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, timeout=90)
        item = {'command': name, 'exitCode': result.returncode, 'passed': result.returncode == 0,
                'output': result.stdout + result.stderr}
    except subprocess.TimeoutExpired:
        item = {'command': name, 'exitCode': None, 'passed': False, 'output': 'Timed out after 90 seconds'}
    report['tests'].append(item)
    report['ok'] &= item['passed']
    print(name, 'PASS' if item['passed'] else 'FAIL', flush=True)
    if not item['passed']:
        print(item['output'], flush=True)
(ROOT / 'ORIGINAL_ASSETS_TEST_REPORT.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
sys.exit(0 if report['ok'] else 1)
