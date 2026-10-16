// Inspect the real self and public profile at phone/tablet widths using test accounts.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL||'http://127.0.0.1:8088';
assert(['127.0.0.1','localhost'].includes(new URL(base).hostname));assert(process.env.SAMIDEV_TEST_DATABASE_URL&&process.env.SAMIDEV_TEST_REDIS_URL);
const out=process.env.SAMIDEV_TEST_ARTIFACTS||'/tmp/samidev-identity';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
const accounts=[],errors=[],contexts=[];
const python=process.env.SAMIDEV_TEST_PYTHON||'python3';
function runPython(code,data){const r=spawnSync(python,['-c',code],{input:JSON.stringify(data),encoding:'utf8'});assert.equal(r.status,0,r.stderr);}
try {
 for(let i=0;i<2;i++) {
  const c=await browser.newContext({viewport:{width:390,height:900}});contexts.push(c);
  await c.addInitScript(()=>localStorage.setItem('samidev_theme','dark'));
  const response=await c.request.post(base+'/api/auth/register',{data:{username:'identity_'+Date.now().toString(36)+'_'+i,password:'Test-password-123',displayName:i?'زائر التجربة':'نجم SamiDev'}});
  assert.equal(response.status(),200);accounts.push((await response.json()).user);
 }
 runPython(`import asyncio,os,json,sys
sys.path.insert(0,'backend')
from postgres_platform import PostgresPlatformService
import redis.asyncio as redis
async def main():
 r=redis.from_url(os.environ['SAMIDEV_TEST_REDIS_URL'],decode_responses=True);s=PostgresPlatformService(os.environ['SAMIDEV_TEST_DATABASE_URL'],r);await s.start();u=json.load(sys.stdin)
 try:
  await s.r.hset(s.k_user(u['id']),'coins','2000')
  for item in ['badge_crown','badge_fire','profile_star','profile_star','profile_star']:await s.buy_store_item(u['id'],item)
  await s.grant_store_item(u['id'],'pool_cue_moon')
  for game,wins in [('pool',23),('carrom',8)]:
   for i in range(wins):await s.record_game_result(u['id'],game,'identity-'+game+str(i),won=True)
 finally:await s.close();await r.aclose()
asyncio.run(main())`,accounts[0]);
 const own=await contexts[0].newPage(),publicPage=await contexts[1].newPage();
 for(const page of [own,publicPage])page.on('pageerror',e=>errors.push(e.message));
 await own.goto(base+'/platform/');await own.waitForFunction(()=>window.SamiDevMobilePlatform);await own.evaluate(()=>window.SamiDevMobilePlatform.navigate('profile'));
 await own.locator('#own-profile-details .sd-rank-row').first().waitFor();
 await own.locator('.profile-cover').first().evaluate(n=>document.fonts.ready);
 assert.equal(await own.locator('#own-profile-details .sd-owned-card').count(),3);
 await publicPage.goto(base+'/platform/');await publicPage.waitForFunction(()=>window.SamiDevMobilePlatform);
 await publicPage.evaluate(id=>window.SamiDevMobilePlatform.openProfile(id),accounts[0].id);
 await publicPage.locator('#community-profile-loading').waitFor({state:'hidden'});
 assert(await publicPage.locator('#sd-public-extra').isHidden());
 assert((await publicPage.locator('#community-profile-featured').innerText()).includes('البلياردو'));
 const starArt=await publicPage.locator('.community-public-profile-star').first().evaluate(n=>getComputedStyle(n).backgroundImage);
 assert(starArt.includes('/identity/profile-atlas.png'));
 const coverArt=await publicPage.locator('.community-public-profile-card .profile-cover').evaluate(n=>getComputedStyle(n).backgroundImage);
 assert(coverArt.includes('samidev-night-cover.png'));
 await publicPage.locator('.community-public-profile-card').screenshot({path:out+'/profile-compact.png'});
 await publicPage.locator('#community-profile-full').click();
 assert(await publicPage.locator('#sd-public-extra').isVisible());assert.equal(await publicPage.locator('#sd-public-extra .sd-owned-card').count(),3);assert.equal(await publicPage.locator('#sd-public-extra .sd-rank-row').count(),2);
 const card=publicPage.locator('.community-public-profile-card');
 for(const width of [320,390,768]) {
  await publicPage.setViewportSize({width,height:1050});
  assert(await card.evaluate(n=>n.scrollWidth<=n.clientWidth+1),'Profile overflows at '+width);
 }
 await publicPage.setViewportSize({width:390,height:1100});
 await publicPage.locator('.community-public-profile-shell').evaluate(n=>n.scrollTop=0);
 await publicPage.locator('.community-public-profile-shell').screenshot({path:out+'/profile-full.png'});
 await own.locator('#page-profile .profile-showcase').screenshot({path:out+'/profile-own.png'});
 await publicPage.locator('#community-profile-close').click();assert(await publicPage.locator('#sd-public-extra').isHidden());
 await publicPage.locator('#community-profile-collection').click();assert(await publicPage.locator('#sd-public-extra .sd-collection-grid').isVisible());
 await publicPage.locator('#community-profile-friend').click();await publicPage.waitForFunction(()=>document.querySelector('#community-profile-friend').textContent.includes('تم إرسال الطلب'));assert((await publicPage.locator('#community-profile-friend').innerText()).includes('تم إرسال الطلب'));
 assert(await publicPage.locator('#sd-public-extra').isVisible(),'Friend action preserves full profile mode');
 assert.deepEqual(errors,[]);
 console.log(JSON.stringify({ok:true,checks:['Original raster cover and 4x2 atlas','Compact card and full-profile transition','Real top game, owned sample and played game ranks','Responsive 320/390/768 layouts','Friend action preserves full view; collection shortcut works'],artifacts:out}));
} finally {
 await browser.close();
 if(accounts.length)runPython(`import asyncio,json,os,sys,asyncpg
async def main():
 c=await asyncpg.connect(os.environ['SAMIDEV_TEST_DATABASE_URL'])
 for u in json.load(sys.stdin):await c.execute("DELETE FROM samidev_social_documents WHERE key=$1 OR key=$2 OR strpos(key, ':' || $3 || ':')>0 OR right(key,length($3)+1)=':' || $3",'sdp:user:'+u['id'],'sdp:username:'+u['username'].lower(),u['id'])
 await c.close()
asyncio.run(main())`,accounts);
}
