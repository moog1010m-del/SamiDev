"""Fail release builds closed when JS layers or generated hashes are absent/stale."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
ENGINES={'carrom':'main.js','pool':'games/pool/main.js','crazy8':'games/crazy8/main.js','tablesoccer':'games/tablesoccer/main.js'}
def verify(root=ROOT):
 root=Path(root);manifest=json.loads((root/'assets/runtime-manifest.json').read_text(encoding='utf-8'))
 protection=manifest.get('protection') or {}
 required={'terser-local-mangling','seeded-identifier-obfuscation','rc4-string-array-75-percent','selective-control-flow-6-percent','no-source-maps'}
 if protection.get('profile')!='layered-release-v4' or not required.issubset(protection.get('layers',[])):
  raise RuntimeError('Protected release assets required. Build with python tool/build_play.py --server-url <reviewed HTTPS origin>.')
 for game,relative in ENGINES.items():
  file=root/'assets/runtime'/relative;digest=hashlib.sha256(file.read_bytes()).hexdigest()
  if digest!=manifest['engines'][game] or digest!=protection.get('engines',{}).get(game):raise RuntimeError('Protected runtime hash mismatch: '+game)
  source=root.parent/'SamiDev_Platform/game'/relative
  if source.is_file() and hashlib.sha256(source.read_bytes()).hexdigest()==digest:raise RuntimeError('Unprotected original engine found: '+game)
 if list((root/'assets/runtime').rglob('*.map')):raise RuntimeError('Source maps must stay private')
 print('Layered release protection verified for all four games; no source maps.')
if __name__=='__main__':verify()
