"""Local isolated UI fixture. No real accounts, purchases, or game connections."""
import json
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'backend'))
from social_platform import STORE_CATALOG, STORE_DEFAULT_EQUIPPED

equipped=dict(STORE_DEFAULT_EQUIPPED)
catalog=[dict(value,id=key,owned=True) for key,value in STORE_CATALOG.items()]
html='''<!doctype html><html lang="ar" dir="rtl" data-theme="dark"><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>معاينة المقتنيات</title>
<link rel="stylesheet" href="/inventory-ui.css"><style>body{background:#102027;color:#fff;font:16px system-ui;padding:24px}h1{font-size:20px}</style>
<h1>معاينة المقتنيات — بيانات اختبار محلية</h1><script>window.SamiDevGames={current:()=>({id:'pool'})};</script>
<script src="/sticker-art.js"></script><script src="/inventory-ui.js"></script></html>'''

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):super().__init__(*args,directory=str(ROOT/'game'),**kwargs)
    def send_data(self,data,content_type):
        self.send_response(200);self.send_header('Content-Type',content_type);self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
    def do_GET(self):
        if self.path=='/':self.send_data(html.encode(),'text/html; charset=utf-8')
        elif self.path=='/api/store':self.send_data(json.dumps(dict(ok=True,catalog=catalog,equipped=equipped)).encode(),'application/json')
        else:super().do_GET()
    def do_POST(self):
        if self.path!='/api/store/equip':self.send_error(404);return
        data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        item=STORE_CATALOG[data['itemId']];equipped[item['slot']]=data['itemId']
        self.send_data(json.dumps(dict(ok=True,equipped=equipped)).encode(),'application/json')
    def log_message(self,*args):pass

if __name__=='__main__':
    print('Isolated inventory preview: http://127.0.0.1:56649',flush=True)
    ThreadingHTTPServer(('127.0.0.1',56649),Handler).serve_forever()
