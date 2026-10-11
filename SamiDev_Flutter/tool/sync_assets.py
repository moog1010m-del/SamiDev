"""Bundle the complete web lobby and game assets; no backend code, secrets or sourcemaps."""
from pathlib import Path
import hashlib,json,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
WEB=ROOT.parent/'SamiDev_Platform/game'
TARGET=ROOT/'assets/runtime'
ALLOWED={'.html','.js','.css','.json','.atlas','.glsl','.txt','.svg','.png','.webp','.jpg','.jpeg','.m4a','.mp3','.ogg','.wav','.woff','.woff2','.ttf','.otf'}
# Refuse stale branding before copying any asset into the mobile bundle.
subprocess.run([sys.executable,str(WEB.parent/'tools/check_runtime_branding.py'),'--root',str(WEB)],check=True)
files={}
for source in sorted(WEB.rglob('*')):
 if not source.is_file():continue
 rel=source.relative_to(WEB)
 if source.suffix.lower() not in ALLOWED or any(x.startswith('.') for x in rel.parts):continue
 target=TARGET/rel;target.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,target)
 data=target.read_bytes();files[rel.as_posix()]={'size':len(data),'sha256':hashlib.sha256(data).hexdigest()}
# Delete only obsolete files within the generated output directory.
for file in TARGET.rglob('*'):
 if file.is_file() and file.relative_to(TARGET).as_posix() not in files:file.unlink()
engines={game:files[main]['sha256'] for game,main in {'carrom':'main.js','crazy8':'games/crazy8/main.js','pool':'games/pool/main.js','tablesoccer':'games/tablesoccer/main.js'}.items()}
(ROOT/'assets/runtime-manifest.json').write_text(json.dumps({'version':1,'engines':engines,'files':files},indent=2)+'\n')
pub=ROOT/'pubspec.yaml';text=pub.read_text().split('  assets:\n')[0]+'  assets:\n    - assets/runtime-manifest.json\n'
for directory in sorted({str((Path('assets/runtime')/Path(key).parent).as_posix())+'/' for key in files}):text+='    - '+directory+'\n'
pub.write_text(text)
print(f'Bundled {len(files)} files; complete web lobby preserved')
