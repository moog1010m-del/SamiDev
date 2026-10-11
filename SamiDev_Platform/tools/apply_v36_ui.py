"""Reproducible V36 UI integration; run once on the V35 source bundle."""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / 'game'
layout = (ROOT / 'design/avatar-layout-v36.js').read_text()
for engine in [GAME/'main.js', *sorted((GAME/'games').glob('*/main.js'))]:
    source = engine.read_text()
    if source.startswith('/* Shared source,'):
        continue
    source, count = re.subn(r'([a-z])\.prototype\.positionNodes=function\(\)\{.*?\},\1\.prototype\.checkOwnerBadgeVisibility=',
        lambda m: f'{m[1]}.prototype.positionNodes=function(){{globalThis.SamiDevAvatarLayout.position(this)}},{m[1]}.prototype.checkOwnerBadgeVisibility=', source, count=1)
    assert count == 1, engine
    source, count = re.subn(r'([a-z])\.prototype\.layoutOwnerIndicator=function\(\)\{.*?\},\1\.prototype\.refresh=',
        lambda m: f'{m[1]}.prototype.layoutOwnerIndicator=function(){{globalThis.SamiDevAvatarLayout.owner(this)}},{m[1]}.prototype.refresh=', source, count=1)
    assert count == 1, engine
    # Keep the owner's crown visible during their turn, in its independent slot.
    source = source.replace('n&&this.showName&&!this.localTurnPill.visible', 'n&&this.showName')
    engine.write_text(layout + '\n' + source)
print('V36 identity layout embedded in all four engines')
