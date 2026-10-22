"""The background cache can only contain fingerprinted public game files."""
import hashlib,json,re,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from build_asset_cache import build
class ContractTests(unittest.TestCase):
 def test_reproducible_public_contract(self):
  path=ROOT/'game/asset-worker.js';before=path.read_bytes();build();self.assertEqual(path.read_bytes(),before)
  text=before.decode();data=json.loads(re.search(r'const CONTRACT=(.*);\r?\n',text)[1])
  self.assertEqual(set(data['groups']),{'pool','carrom','crazy8','tablesoccer'})
  for url,digest in data['files'].items():
   self.assertFalse(url.startswith(('/api/','/ws/','/platform/')))
   self.assertNotEqual(url,'/client-config.js');self.assertFalse(url.endswith('.html'))
   self.assertEqual(hashlib.sha256((ROOT/'game'/url.lstrip('/')).read_bytes()).hexdigest(),digest)
  for game,paths in data['groups'].items():
   self.assertIn('/main.js' if game=='carrom' else f'/games/{game}/main.js',paths)
   self.assertTrue(set(paths)<=data['files'].keys())
if __name__=='__main__':unittest.main()
