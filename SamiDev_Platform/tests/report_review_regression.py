"""Authenticated block-and-report, human review, permissions and repeat protection."""
import asyncio,os,sys
from pathlib import Path
from aiohttp import web,ClientSession
from aiohttp.test_utils import TestServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'backend'))
os.environ.update(SAMIDEV_FIREBASE_AUTH='0',SAMIDEV_PRODUCTION='0')
from social_platform import PlatformService,PlatformHttp,PlatformError
from store import MemoryStore
from report_review import review

async def main():
 p=PlatformService();api=PlatformHttp(p,MemoryStore())
 admin=await p.create_user('ReviewAdmin','Test-password-123',role='admin')
 a=await p.create_user('ReportReader','Test-password-123');b=await p.create_user('ReportTarget','Test-password-123')
 ta,tb,tc=[await p.create_session(u['id']) for u in (admin,a,b)]
 @web.middleware
 async def errors(request,handler):
  try:return await handler(request)
  except PlatformError as e:return web.json_response({'ok':False,'error':e.code,'message':e.message},status=e.status)
 app=web.Application(middlewares=[errors]);app.router.add_post('/api/users/{user_id}/report',api.report_user);app.router.add_get('/api/admin/reports',api.admin_reports);app.router.add_post('/api/admin/reports/{report_id}/review',api.admin_review_report)
 async with TestServer(app) as server,ClientSession(cookies={'samidev_session':ta}) as owner,ClientSession(cookies={'samidev_session':tb}) as member,ClientSession() as anon:
  path=server.make_url('/api/users/'+b['id']+'/report')
  async with anon.post(path,json={'reason':'spam','block':True}) as r:assert r.status==401
  async with member.post(path,json={'reason':'invented','block':True}) as r:assert r.status==400
  assert not await p.safety.blocked(a['id'])
  async with member.post(path,json={'reason':'harassment','message':'test evidence','block':True}) as r:
   assert r.status==200;result=await r.json();rid=result['reportId'];assert result['blocked']
  assert b['id'] in await p.safety.blocked(a['id'])
  rows=await p.list_reports();assert rows[0]['status']=='open' and rows[0]['reason']=='harassment'
  assert (await p.get_user(b['id'])).get('banned')!='1' # A report never automatically bans.
  url=server.make_url('/api/admin/reports/'+rid+'/review')
  async with member.post(url,json={'decision':'ban'}) as r:assert r.status==403
  async with owner.post(url,json={'decision':[]}) as r:assert r.status==400
  async with owner.post(url,json={'decision':'dismiss'}) as r:assert r.status==200
  assert (await p.list_reports())[0]['status']=='dismissed'
  assert await p.resolve_session(tc) # Dismissal is not a sanction.
  async with owner.post(url,json={'decision':'ban'}) as r:assert r.status==409
  second=await p.submit_report(a['id'],b['id'],reason='cheating')
  url=server.make_url('/api/admin/reports/'+second['id']+'/review')
  async with owner.post(url,json={'decision':'ban','note':'reviewed evidence'}) as r:assert r.status==200
  assert await p.resolve_session(tc) is None
  assert (await p.get_user(b['id']))['banned']=='1'
  async with owner.get(server.make_url('/api/admin/reports')) as r:
   rows=(await r.json())['reports'];assert rows[0]['status']=='actioned' and rows[0]['actorId']==admin['id']
  # Two concurrent decisions cannot overwrite a final review.
  third=await p.submit_report(a['id'],b['id'])
  results=await asyncio.gather(review(p,admin,third['id'],'dismiss'),review(p,admin,third['id'],'ban'),return_exceptions=True)
  assert sum(isinstance(x,PlatformError) and x.code=='REPORT_REVIEWED' for x in results)==1
 await p.live.close();await p.direct.close()
 print('REPORT_REVIEW_PASS: combined block, pending report, admin-only decisions, dismissal, session revocation, duplicate/concurrent protection')
if __name__=='__main__':asyncio.run(main())
