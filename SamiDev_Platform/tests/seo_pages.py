"""Verify public discovery through the real static handler, without authentication."""
import asyncio,json,os,sys,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
from html.parser import HTMLParser
from aiohttp import web,ClientSession
from aiohttp.test_utils import TestServer
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'));sys.path.insert(0,str(ROOT/'tools'))
os.environ.update(SAMIDEV_STORE='memory',SAMIDEV_PLATFORM_STORE='memory',SAMIDEV_FIREBASE_AUTH='0')
from build_seo_pages import build,ORIGIN
from check_runtime_branding import audit
import app as application
class Document(HTMLParser):
 def __init__(self):super().__init__();self.tags=[]
 def handle_starttag(self,tag,attrs):self.tags.append((tag,dict(attrs)))
async def main():
 with tempfile.TemporaryDirectory() as directory:
  fixture=Path(directory);(fixture/'samidev-games.js').write_text('')
  (fixture/'discover').mkdir();page=fixture/'discover/alternatives.html'
  page.write_text('Plato');assert not audit(fixture)['ok']
  page.write_text('Plazr مشروع مستقل، غير تابع لبلاتو (Plato) أو قيمزر (Gamezer).');assert audit(fixture)['ok']
  (fixture/'samidev-games.js').write_text('Plato');assert not audit(fixture)['ok']
 files=build();before={p:(ROOT/'game'/p).read_bytes() for p in files};build()
 assert all((ROOT/'game'/p).read_bytes()==v for p,v in before.items())
 app=web.Application();app.router.add_get('/platform/',application.SERVICE.index);app.router.add_get('/{path:.*}',application.SERVICE.static_game)
 async with TestServer(app) as server,ClientSession() as client:
  async with client.get(server.make_url('/sitemap.xml')) as response:
   assert response.status==200;xml=ET.fromstring(await response.text())
  urls=[e.text for e in xml.findall('.//{*}loc')];assert len(urls)==8 and len(set(urls))==8
  for url in urls:
   assert url.startswith(ORIGIN+'/');path=url[len(ORIGIN):]
   async with client.get(server.make_url(path)) as response:
    assert response.status==200 and 'charset=utf-8' in response.headers['Content-Type'];html=await response.text()
   assert '\ufffd' not in html;doc=Document();doc.feed(html)
   canonical=[a['href'] for t,a in doc.tags if t=='link' and a.get('rel')=='canonical'];assert canonical==[url]
   assert any(t=='meta' and a.get('name')=='description' and a.get('content') for t,a in doc.tags)
   if path.startswith('/discover/'):
    assert sum(t=='h1' for t,a in doc.tags)==1
    schema=json.loads(html.split('<script type="application/ld+json">')[1].split('</script>')[0]);assert schema['url']==url
    assert not any(t=='script' and 'src' in a for t,a in doc.tags)
    for tag,attrs in doc.tags:
     target=attrs.get('href') if tag in ('a','link') else attrs.get('content') if tag=='meta' and attrs.get('property')=='og:image' else None
     if target and target.startswith(ORIGIN):target=target[len(ORIGIN):]
     if target and target.startswith('/'):
      async with client.get(server.make_url(target)) as response:assert response.status==200,(path,target,response.status)
  async with client.get(server.make_url('/robots.txt')) as response:
   assert response.status==200 and ORIGIN+'/sitemap.xml' in await response.text()
 print('SEO_PAGES_PASS: eight anonymous UTF-8 routes, canonical URLs, sitemap, linked assets, structured data and repeatable build')
if __name__=='__main__':asyncio.run(main())
