"""Public legal pages must remain honest about unimplemented safeguards."""
from pathlib import Path
import json,sys,unittest,subprocess,os
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from build_legal_pages import build
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  for key,value in attrs:
   if key in ('href','src') and value and value.startswith('/'):self.links.append(value)
class LegalTests(unittest.TestCase):
 def test_utf8_build_does_not_depend_on_host_locale(self):
  env=dict(os.environ,LC_ALL='C',PYTHONUTF8='0',PYTHONCOERCECLOCALE='0')
  subprocess.run([sys.executable,str(ROOT/'tools/build_legal_pages.py')],env=env,check=True,capture_output=True)
  raw=(ROOT/'game/platform/privacy.html').read_bytes()
  self.assertIn('سياسة الخصوصية',raw.decode('utf-8'))
  self.assertNotIn('\ufffd',raw.decode('utf-8'))
  self.assertNotIn('????',raw.decode('utf-8'))
 def test_public_offline_documents_are_consistent_and_draft(self):
  data=build();self.assertTrue(data['draft']);self.assertEqual(data['supportEmail'],'support@plazr.cc')
  self.assertEqual({p['id'] for p in data['pages']},{'privacy','terms','about','contact','community-guidelines','children'})
  self.assertTrue(any('13' in item for item in data['reviewItems']))
  for page in data['pages']:
   text=(ROOT/'game/platform'/f"{page['id']}.html").read_text();self.assertNotIn('مسودة للمراجعة',text);self.assertNotIn('جهة مسجلة',text);self.assertNotIn('لم يُستكمل الاسم',text);self.assertNotIn('<script',text)
   links=Links();links.feed(text)
   for url in links.links:
    if url=='/platform/':continue
    self.assertTrue((ROOT/'game'/url.lstrip('/')).is_file(),url)
  public=json.loads((ROOT/'game/platform/legal-content.json').read_text());self.assertEqual(public['pages'],data['pages']);self.assertNotIn('reviewItems',public);self.assertNotIn('operatorLegalName',public);self.assertNotIn('draft',public)
 def test_child_and_retention_disclosures(self):
  data=build();privacy=next(p for p in data['pages'] if p['id']=='privacy');text=json.dumps(privacy,ensure_ascii=False)
  self.assertIn('اللعب المحلي',text);self.assertIn('لا يرسله إلى الخادم',text);self.assertIn('ليس إثبات عمر',text);self.assertIn('حد عددي وليس مدة حذف',text);self.assertIn('لا تحدد هذه السياسة مدة حذف موحدة',text)
if __name__=='__main__':unittest.main()
