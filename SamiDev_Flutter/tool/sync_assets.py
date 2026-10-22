"""Bundle the complete web lobby and game assets; no backend code, secrets or sourcemaps."""
from pathlib import Path
import argparse,hashlib,json,re,shutil,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--web-root',type=Path,default=ROOT.parent/'SamiDev_Platform/game')
WEB=parser.parse_args().web_root.resolve()
TARGET=ROOT/'assets/runtime'
ALLOWED={'.html','.js','.css','.json','.atlas','.glsl','.txt','.svg','.png','.webp','.jpg','.jpeg','.m4a','.mp3','.ogg','.wav','.woff','.woff2','.ttf','.otf'}
# Refuse stale branding before copying any asset into the mobile bundle.
subprocess.run([sys.executable,str(ROOT.parent/'SamiDev_Platform/tools/check_runtime_branding.py'),'--root',str(WEB)],check=True)
files={}
for source in sorted(WEB.rglob('*')):
 if not source.is_file():continue
 rel=source.relative_to(WEB)
 if source.suffix.lower() not in ALLOWED or any(x.startswith('.') for x in rel.parts):continue
 target=TARGET/rel;target.parent.mkdir(parents=True,exist_ok=True)
 if rel.as_posix()=='platform/index.html':
  # Initial mobile release has no cash purchases or external payment prompts.
  # The web catalog remains independent; native API/navigation policy also
  # denies checkout routes and external payment pages.
  html=source.read_text(encoding='utf-8')
  html,count=re.subn(r'<section\b[^>]*class="coin-topup"[^>]*>.*?</section>', '',html,flags=re.S)
  if count!=1:raise RuntimeError('Expected exactly one web coin top-up section')
  target.write_bytes(html.encode('utf-8'))
 elif not target.exists() or target.read_bytes()!=source.read_bytes():
  shutil.copyfile(source,target)
 data=target.read_bytes();files[rel.as_posix()]={'size':len(data),'sha256':hashlib.sha256(data).hexdigest()}
# Delete only obsolete files within the generated output directory.
for file in TARGET.rglob('*'):
 if file.is_file() and file.relative_to(TARGET).as_posix() not in files:file.unlink()
engines={game:files[main]['sha256'] for game,main in {'carrom':'main.js','crazy8':'games/crazy8/main.js','pool':'games/pool/main.js','tablesoccer':'games/tablesoccer/main.js'}.items()}
manifest={'version':1,'engines':engines,'files':files}
report_path=WEB.parent/(WEB.name+'-protection-report.json')
if report_path.is_file() and (WEB/'.plazr-generated-distribution').is_file():
 report=json.loads(report_path.read_text(encoding='utf-8'))
 if any(report['engines'][game]['sha256']!=sha for game,sha in engines.items()):raise RuntimeError('Protected engine does not match its build report')
 # Never embed the private seed, source hashes, or symbol mappings in the app.
 manifest['protection']={'profile':report['profile'],'layers':report.get('layers',[]),'engines':engines}
(ROOT/'assets/runtime-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
pub=ROOT/'pubspec.yaml';text=pub.read_text().split('  assets:\n')[0]+'  assets:\n    - assets/runtime-manifest.json\n'
for directory in sorted({str((Path('assets/runtime')/Path(key).parent).as_posix())+'/' for key in files}):text+='    - '+directory+'\n'
pub.write_text(text)
print(f'Bundled {len(files)} files; complete web lobby preserved')
