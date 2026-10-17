"""Extract immutable bootstrap data; runtime never fetches per-game HTML."""
from html.parser import HTMLParser
from pathlib import Path
import json
import re
ROOT=Path(__file__).resolve().parents[1]/'game'
class Resources(HTMLParser):
 def __init__(self):super().__init__();self.scripts=[];self.styles=[]
 def handle_starttag(self,tag,attrs):
  a=dict(attrs)
  if tag=='script' and a.get('src'):self.scripts.append(a['src'])
  if tag=='link' and a.get('rel')=='stylesheet':self.styles.append(a['href'])
def extract(text,key):
 m=re.search(r'window\.'+re.escape(key)+r'\s*=\s*',text)
 return json.JSONDecoder().raw_decode(text[m.end():])[0] if m else None
def build():
 result={}
 for gid,entry in {'carrom':'index.html','pool':'games/pool/index.html','crazy8':'games/crazy8/index.html','tablesoccer':'games/tablesoccer/index.html'}.items():
  text=(ROOT/entry).read_text();r=Resources();r.feed(text)
  result[gid]={'root':'/'+str(Path(entry).parent).replace('.','').strip('/')+'/' if '/' in entry else '/',
   'dictionary':extract(text,'__dictEn'),'images':extract(text,'__assetImages'), 'styles':r.styles,'scripts':r.scripts}
  if not isinstance(result[gid]['dictionary'],dict) or not isinstance(result[gid]['images'],list):raise RuntimeError('Missing game bootstrap data: '+gid)
 (ROOT/'runtime-games.json').write_text(json.dumps(result,ensure_ascii=False,separators=(',',':'))+'\n')
 return result
if __name__=='__main__':build()
