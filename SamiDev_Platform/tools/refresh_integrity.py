"""Recompute deployment fingerprints after reviewing a source or asset change."""
from pathlib import Path
import hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];GAME=ROOT/'game'
subprocess.run([sys.executable,str(ROOT/'tools/check_runtime_branding.py')],check=True)
def digest(path,algorithm='sha256'):return hashlib.new(algorithm,path.read_bytes()).hexdigest()
def save(path,data):path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
engines={'carrom':'main.js','crazy8':'games/crazy8/main.js','pool':'games/pool/main.js','tablesoccer':'games/tablesoccer/main.js'}
integrity={'publisher':'SamiDev','algorithm':'sha256','games':{key:{'sha256':digest(GAME/value),'main':value} for key,value in engines.items()}}
save(GAME/'samidev-integrity.json',integrity)
for key,main in engines.items():
 base=(GAME/main).parent;index=base/'__assets.json'
 if index.exists():
  items=json.loads(index.read_text());items={name:digest(base/name.removeprefix(key+'/'),'sha1') for name in items};save(index,items)
build=GAME/'platform/build.json';data=json.loads(build.read_text());data['release']='V30';data['files']={key:digest(GAME/key) for key in data['files']};data['buildId']='samidev-v30-'+hashlib.sha256(json.dumps(data['files'],sort_keys=True).encode()).hexdigest()[:16];save(build,data)
for key,main in engines.items():
 base=(GAME/main).parent;file=base/'attestation.json';data=json.loads(file.read_text());data['signed']=False;data['files']={key:digest(base/key) for key in data['files']};save(file,data)
print('Deployment fingerprints refreshed; regenerate the Flutter bundle with tool/sync_assets.py')
