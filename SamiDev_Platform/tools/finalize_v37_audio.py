"""Refresh source media inventory and cache versions after the V37 audio build."""
from pathlib import Path
import hashlib, json, re, subprocess, sys
ROOT=Path(__file__).resolve().parents[1]
GAME=ROOT/'game'
audio=json.loads((ROOT/'FREESOUND_AUDIO.json').read_text())
manifest=json.loads((ROOT/'ORIGINAL_ASSETS_MANIFEST.json').read_text())
indexed={item['path']:item for item in manifest['assets']}
for item in audio:
    record=indexed.setdefault(item['file'],{'path':item['file']})
    record.update(sha256=item['sha256'],source='CC0 Freesound recording; see FREESOUND_AUDIO.json for authors, sources and processing')
manifest.update(assets=sorted(indexed.values(),key=lambda x:x['path']),mediaCount=len(indexed),
                audioSource='V37: 105 effects from 15 CC0 Freesound recordings; existing music and four vocal reactions retained',
                v37FreesoundEffects=len(audio),v37NewAudioFiles=1)
(ROOT/'ORIGINAL_ASSETS_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
for page in [GAME/'index.html',*sorted((GAME/'games').glob('*/index.html'))]:
    text=page.read_text()
    for name in ['browser-runtime.js','crazy8-audio.js']:
        digest=hashlib.sha256((GAME/name).read_bytes()).hexdigest()[:16]
        text=re.sub(r'((?:\.\./|/)?'+re.escape(name)+r')(?:\?[^"\']*)?(?=["\'])',lambda m:m[1]+'?v='+digest,text)
    page.write_text(text)
for script in ['update_original_asset_index.py','update_ui_build.py','update_game_integrity.py']:
    subprocess.run([sys.executable,str(ROOT/'tools'/script)],check=True,stdout=subprocess.DEVNULL)
subprocess.run([sys.executable,str(ROOT.parent/'SamiDev_Flutter/tool/sync_assets.py')],check=True)
print('V37 source inventory, all four game resource indexes, build fingerprints and Flutter assets updated')
