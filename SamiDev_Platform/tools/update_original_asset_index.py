"""Rebuild local resource hashes for the two redesigned games."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1] / 'game'
for game, namespace in [(ROOT, 'carrom'), (ROOT / 'games/crazy8', 'crazy8'), (ROOT / 'games/tablesoccer', 'tablesoccer'), (ROOT / 'games/pool', 'pool')]:
    resources = []
    for directory in ['images', 'sounds', 'shaders', 'anim', 'scene-avatars', 'scene-settings', 'scene-reactions', 'scene-ui', 'imported']:
        if (game / directory).exists():
            resources.extend(p for p in (game / directory).rglob('*') if p.is_file())
    if (game / 'dictionary.json').exists():
        resources.append(game / 'dictionary.json')
    index = {namespace + '/' + str(p.relative_to(game)): hashlib.sha1(p.read_bytes()).hexdigest() for p in sorted(resources)}
    (game / '__assets.json').write_text(json.dumps(index, separators=(',', ':')) + '\n')
    print(namespace, len(index), 'local resources indexed')
