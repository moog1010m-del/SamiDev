"""Embed the Game Pool collection renderer without changing native physics/rules."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
engine = ROOT / 'game/games/pool/main.js'
source = engine.read_text()
helper = (ROOT / 'design/pool-pocketed-layout.js').read_text().rstrip()
start = '/* Shared Game Pool presentation, embedded by tools/apply_pool_pocketed_layout.py. */'
end = '/* End SamiDev pool pocketed layout. */'
if start in source:
    begin = source.index(start)
    finish = source.index(end, begin) + len(end)
    source = source[:begin] + source[finish:]
source = source.lstrip('\n')
for method, delegate in [('update8BallGapBallsVisibility', 'updateVisibility'),
                         ('update8BallGapBallsPos', 'updatePositions')]:
    signature = method + '(){'
    guard = 'if(globalThis.SamiDevPoolPocketedLayout.' + delegate + '(this))return;'
    if source.count(signature) != 1:
        raise RuntimeError(f'Expected one native {method} method')
    source = source.replace(signature + guard, signature)
    source = source.replace(signature, signature + guard, 1)
engine.write_text(helper + '\n\n' + source)
print('Embedded Game Pool collection layout; two presentation delegates updated')
