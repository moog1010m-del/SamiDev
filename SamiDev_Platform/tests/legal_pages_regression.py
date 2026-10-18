"""Public legal pages must remain honest about unimplemented safeguards."""
from pathlib import Path
import json,sys,unittest
from html.parser import HTMLParser
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from build_legal_pages import build
class Links(HTMLParser):
 def __init__(self):super().__init__();self.links=[]
 def handle_starttag(self,tag,attrs):
  for key,value in attrs:
   if key in ('href','src') and value and value.startswith('/'):self.links.append(value)
class LegalTests(unittest.TestCase):
 def test_public_offline_documents_are_consistent_and_draft(self):
  data=build();self.assertTrue(data['draft']);self.assertEqual(data['supportEmail'],'support@plazr.cc')
  self.assertEqual({p['id'] for p in data['pages']},{'privacy','terms','about','contact','community-guidelines','children'})
  self.assertTrue(any('13' in item for item in data['reviewItems']))
  for page in data['pages']:
   text=(ROOT/'game/platform'/f"{page['id']}.html").read_text();self.assertIn('مسودة للمراجعة',text);self.assertNotIn('<script',text)
   links=Links();links.feed(text)
   for url in links.links:
    if url=='/platform/':continue
    self.assertTrue((ROOT/'game'/url.lstrip('/')).is_file(),url)
  self.assertEqual(json.loads((ROOT/'game/platform/legal-content.json').read_text())['pages'],data['pages'])
 def test_child_and_retention_disclosures(self):
  data=build();privacy=next(p for p in data['pages'] if p['id']=='privacy');text=json.dumps(privacy,ensure_ascii=False)
  self.assertIn('لا تطبق بوابة عمر',text);self.assertIn('حد عددي وليس مدة حذف',text);self.assertIn('لا نضع مدة حذف غير مطبقة',text)
if __name__=='__main__':unittest.main()
