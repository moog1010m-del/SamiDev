"""Verify public discovery through the real static handler, without authentication."""
import asyncio,json,os,sys,tempfile,xml.etree.ElementTree as ET
from pathlib import Path
from html.parser import HTMLParser
from urllib.robotparser import RobotFileParser
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
 app=web.Application();app.on_response_prepare.append(application.security_headers);app.router.add_get('/',application.SERVICE.landing);app.router.add_get('/discover/index.html',application.SERVICE.discovery_home_redirect);app.router.add_get('/discover/',application.SERVICE.discovery_home_redirect);app.router.add_get('/platform/',application.SERVICE.index);app.router.add_get('/{path:.*}',application.SERVICE.static_game)
 async with TestServer(app) as server,ClientSession() as client:
  async with client.get(server.make_url('/sitemap.xml')) as response:
   assert response.status==200;xml=ET.fromstring(await response.text())
  async with client.get(server.make_url('/robots.txt')) as response:
   robots=RobotFileParser();robots.parse((await response.text()).splitlines())
  urls=[e.text for e in xml.findall('.//{*}loc')];assert len(urls)==7 and len(set(urls))==7;assert ORIGIN+'/' in urls;assert ORIGIN+'/platform/' not in urls
  for url in urls:
   assert url.startswith(ORIGIN+'/');path=url[len(ORIGIN):]
   assert robots.can_fetch('Googlebot',url),(url,'blocked by robots.txt')
   async with client.get(server.make_url(path)) as response:
    assert response.status==200 and 'charset=utf-8' in response.headers['Content-Type'];html=await response.text()
   assert '\ufffd' not in html;doc=Document();doc.feed(html)
   assert not any(t=='meta' and a.get('name')=='robots' and 'noindex' in a.get('content','').lower() for t,a in doc.tags),(path,'sitemap page has noindex')
   async with client.get(server.make_url(path),headers={'User-Agent':'Googlebot'},allow_redirects=False) as bot_response:
    assert bot_response.status==200 and 'noindex' not in bot_response.headers.get('X-Robots-Tag','').lower()
    assert await bot_response.text()==html,'public content must not change for crawler user agents'
   canonical=[a['href'] for t,a in doc.tags if t=='link' and a.get('rel')=='canonical'];assert canonical==[url]
   assert any(t=='meta' and a.get('name')=='description' and a.get('content') for t,a in doc.tags)
   if path=='/' or path.startswith('/discover/'):
    assert sum(t=='h1' for t,a in doc.tags)==1
    schema=json.loads(html.split('<script type="application/ld+json">')[1].split('</script>')[0])
    if path=='/':
     graph={node['@type']:node for node in schema['@graph']};assert graph['WebPage']['url']==url;assert graph['WebSite']['name']=='Plazr';assert graph['WebSite']['alternateName']=='بلازر';assert graph['WebSite']['url']==ORIGIN+'/';assert graph['Organization']['url']==ORIGIN+'/'
    else:assert schema['url']==url
    assert not any(t=='script' and 'src' in a for t,a in doc.tags)
    for tag,attrs in doc.tags:
     target=attrs.get('src') if tag=='img' else attrs.get('href') if tag in ('a','link') else attrs.get('content') if tag=='meta' and attrs.get('property')=='og:image' else None
     if target and target.startswith(ORIGIN):target=target[len(ORIGIN):]
     if target and target.startswith('/'):
      async with client.get(server.make_url(target),allow_redirects=False) as response:assert response.status==200,(path,target,response.status)
  async with client.get(server.make_url('/robots.txt')) as response:
   assert response.status==200 and ORIGIN+'/sitemap.xml' in await response.text()
  async with client.get(server.make_url('/discover/does-not-exist.html')) as response:
   assert response.status==404,'unknown URL must not become an indexable soft 404'
  async with client.get(server.make_url('/discover/index.html'),allow_redirects=False) as response:
   assert response.status==301 and response.headers['Location']=='/'
  async with client.get(server.make_url('/?invite=fixture&game=pool'),allow_redirects=False) as response:
   assert response.status==302 and response.headers['Location']=='/platform/?invite=fixture&game=pool'
  async with client.get(server.make_url('/platform/')) as response:
   assert 'name="robots" content="noindex,follow"' in await response.text()
 print('SEO_PAGES_PASS: seven anonymous UTF-8 routes, canonical URLs, sitemap, linked assets, structured data and repeatable build')
if __name__=='__main__':asyncio.run(main())
