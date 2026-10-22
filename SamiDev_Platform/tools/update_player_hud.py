"""Refresh the shared player HUD without changing native game rules."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
layout=(ROOT/'design/avatar-layout-v36.js').read_text()
for path in [ROOT/'game/main.js',*sorted((ROOT/'game/games').glob('*/main.js'))]:
 source=path.read_text(encoding='utf-8');start=source.index('/* Shared source,');end=source.index('\n});',start)+4
 source=source[:start]+layout.rstrip()+source[end:]
 if not re.search(r'countdown=0,globalThis.SamiDevAvatarLayout.trackTimer',source):
  source=re.sub(r'(?<![\w.])((?:this|[a-z])\.countdown)=0',lambda m:'('+m[1]+'=0,globalThis.SamiDevAvatarLayout.trackTimer('+m[1].split('.')[0]+'))',source)
 path.write_text(source,encoding='utf-8')
print('Player HUD source refreshed in all four games')
