"""Validate a generated release tree independently of the obfuscation runner."""
import argparse, hashlib, json, re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def verify(output):
 output=Path(output).resolve(); source=ROOT/'game'
 digest=lambda p,a='sha256':hashlib.new(a,p.read_bytes()).hexdigest()
 report=json.loads((output.parent/(output.name+'-protection-report.json')).read_text())
 integrity=json.loads((output/'samidev-integrity.json').read_text())
 for game,item in integrity['games'].items():
  file=output/item['main']; original=source/item['main']
  assert digest(file)==item['sha256']==report['engines'][game]['sha256']
  assert digest(original)==report['engines'][game]['sourceSha256'], 'Source modified'
  assert digest(file)!=digest(original), 'Engine was not transformed'
  for name,sha in json.loads((file.parent/'__assets.json').read_text()).items():
   assert digest(file.parent/name.removeprefix(game+'/'),'sha1')==sha,(game,name)
  for name,sha in json.loads((file.parent/'attestation.json').read_text())['files'].items():
   assert digest(file.parent/name)==sha,(game,name)
 worker=(output/'asset-worker.js').read_text()
 contract=json.loads(re.search(r'^const CONTRACT=(.*);$',worker,re.M)[1])
 for path,sha in contract['files'].items():assert digest(output/path.lstrip('/'))==sha,path
 for path,sha in json.loads((output/'platform/build.json').read_text())['files'].items():assert digest(output/path)==sha,path
 assert not list(output.rglob('*.map')), 'Source maps leaked'
 print(json.dumps({'ok':True,'engines':4,'sourcesUnchanged':True,'workerFilesVerified':len(contract['files']),'sourceMaps':0}))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('output',type=Path);verify(p.parse_args().output)
