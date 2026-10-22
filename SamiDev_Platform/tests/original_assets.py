"""Verify complete replacement coverage and resource-index integrity."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / 'game'
manifest = json.loads((ROOT / 'ORIGINAL_ASSETS_MANIFEST.json').read_text())
listed = {item['path']: item for item in manifest['assets']}
assert len(listed) == manifest['mediaCount']
media_suffixes = {'.png', '.webp', '.jpg', '.jpeg', '.svg', '.m4a', '.ogg', '.wav', '.mp3', '.woff', '.woff2', '.ttf'}
actual = {
    p.relative_to(ROOT).as_posix() for p in GAME.rglob('*')
    if p.is_file() and p.suffix in media_suffixes
    and ('platform/' not in p.relative_to(GAME).as_posix() or 'platform/assets/profile/' in p.relative_to(GAME).as_posix())
}
assert actual == set(listed), {'untracked': sorted(actual - set(listed)), 'missing': sorted(set(listed) - actual)}
old_hashes = {item['sha256'] for item in manifest['previousMediaHashes']}
for rel, item in listed.items():
    sha = hashlib.sha256((ROOT / rel).read_bytes()).hexdigest()
    assert sha == item['sha256'], ('Changed asset; review and update manifest', rel)
    assert rel.startswith('game/games/pool/') or sha not in old_hashes, ('Old media reintroduced', rel)
pool = json.loads((ROOT / 'POOL_ORIGINAL_ASSETS.json').read_text())
assert len(pool['files']) == pool['preservedImages'] == 15
for item in pool['v36Replacements']:
    assert hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest() == item['sha256']
for item in pool['brandReplacements']:
    assert hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest() == item['sha256']
    assert (ROOT / item['path']).read_bytes() == (ROOT / item['source']).read_bytes()
assert hashlib.sha256((ROOT / pool['replacedTable']['path']).read_bytes()).hexdigest() == pool['replacedTable']['sha256']
for item in pool['files']:
    assert hashlib.sha256((ROOT / item['path']).read_bytes()).hexdigest() == item['sha256']
audio = json.loads((ROOT / 'AUDIO_RESTORE_MANIFEST.json').read_text())
assert len(audio['files']) == 105
current_audio = {item['file']: item for item in json.loads((ROOT / 'FREESOUND_AUDIO.json').read_text())}
for item in audio['files']:
    replacement = current_audio.get(item['path'])
    if replacement:
        assert listed[item['path']]['sha256'] == replacement['sha256']
        assert replacement['license'] == 'CC0-1.0'
    else:
        assert listed[item['path']]['sha256'] == item['sha256']
        assert item['decodedPeak'] <= .95
        assert abs(item['duration'] - item['sourceDuration']) < .13
for base, namespace in [(GAME, 'carrom'), (GAME / 'games/crazy8', 'crazy8'), (GAME / 'games/tablesoccer', 'tablesoccer')]:
    index = json.loads((base / '__assets.json').read_text())
    for key, expected in index.items():
        assert key.startswith(namespace + '/')
        p = base / key.removeprefix(namespace + '/')
        assert p.is_file(), ('Missing local resource', key)
        assert hashlib.sha1(p.read_bytes()).hexdigest() == expected, ('Stale resource hash', key)
    source = (base / 'main.js').read_text()
    for hook in ['shop.getCatalog', '.net.sendMessage', '.net.onMessage', 'showItemPurchase', 'SamiDev.streamMusic']:
        assert hook not in source, ('Legacy host hook present', namespace, hook)
    assert ('images/bg-img-standard.png' if namespace == 'tablesoccer' else 'images/table-background.webp') in source
print(json.dumps({'ok': True, 'mediaFilesVerified': len(listed), 'freesoundEffects': len(current_audio), 'preservedOriginalPoolImages': pool['preservedImages'], 'localAssetIndexesVerified': 3, 'legacyHostHooks': 0}))
