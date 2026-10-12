// Local PostgreSQL/Redis and real browsers: preview -> confirmation -> atomic purchase.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL||'http://127.0.0.1:8100';
assert(['127.0.0.1','localhost'].includes(new URL(base).hostname));assert(process.env.SAMIDEV_TEST_DATABASE_URL&&process.env.SAMIDEV_TEST_REDIS_URL);
const out=process.env.SAMIDEV_TEST_ARTIFACTS||'/workspace/SamiDev-store-products';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
const contexts=[],users=[],errors=[];let buys=0;
const python=process.env.SAMIDEV_TEST_PYTHON||'python3';
function seedCoins(id,amount){const result=spawnSync(python,['-c',`import asyncio,os,sys
sys.path.insert(0,'backend')
from postgres_platform import PostgresPlatformService
import redis.asyncio as redis
async def main():
 r=redis.from_url(os.environ['SAMIDEV_TEST_REDIS_URL'],decode_responses=True);s=PostgresPlatformService(os.environ['SAMIDEV_TEST_DATABASE_URL'],r);await s.start()
 try:await s.r.hset(s.k_user(sys.argv[1]),'coins',sys.argv[2])
 finally:await s.close();await r.aclose()
asyncio.run(main())`,id,String(amount)],{encoding:'utf8'});assert.equal(result.status,0,result.stderr);}
try{
 for(let i=0;i<2;i++){
  const context=await browser.newContext({viewport:{width:390,height:844}});contexts.push(context);
  await context.addInitScript(()=>localStorage.setItem('samidev_theme','dark'));
  const r=await context.request.post(base+'/api/auth/register',{data:{username:'product_'+Date.now().toString(36)+'_'+i,password:'Test-password-123',displayName:i?'زائر المتجر':'نجم SamiDev'}});assert.equal(r.status(),200,await r.text());users.push((await r.json()).user);
 }
 seedCoins(users[0].id,1000);
 const page=await contexts[0].newPage();page.on('pageerror',error=>errors.push(error.message));page.on('request',request=>{if(request.method()==='POST'&&request.url().endsWith('/api/store/buy'))buys++;});
 await page.goto(base+'/platform/');await page.locator('#app').waitFor({state:'visible'});
 assert.equal(await page.locator('.lobby-profile-star:not([hidden])').count(),0);
 await page.locator('.bottom-btn[data-page="store"]').click();await page.locator('.store-item-card').first().waitFor();
 assert.equal(await page.locator('.store-item-card').count(),6);
 assert.equal(await page.locator('.store-catalog').evaluate(node=>getComputedStyle(node).gridTemplateColumns.split(' ').length),2);
 await page.screenshot({path:out+'/store-mobile.png',fullPage:true});
 await page.locator('[data-item-id="badge_crown"]').click();
 assert.equal(buys,0);assert.equal(await page.locator('#store-product-modal svg').count(),2);
 await page.screenshot({path:out+'/sticker-preview.png'});
 await page.locator('[data-product-action]').click();assert.equal(buys,0);
 await page.locator('[data-product-back]').click();assert.equal(buys,0);
 await page.locator('[data-product-close]').click();
 await page.locator('[data-item-id="profile_star"]').click();await page.locator('[data-product-action]').click();
 assert.equal(buys,0);await page.screenshot({path:out+'/purchase-confirmation.png'});
 await page.locator('[data-product-confirm]').evaluate(button=>{button.click();button.click();});
 await page.waitForFunction(()=>document.querySelector('.store-star-count')?.textContent.includes('تملك 1'));
 assert.equal(buys,1);let data=await (await contexts[0].request.get(base+'/api/store')).json();assert.equal(data.starsCount,1);assert.equal(data.coins,950);
 await page.locator('[data-product-close]').click();assert.equal(await page.locator('.lobby-profile-star:not([hidden])').count(),1);
 assert.equal(await page.locator('#page-profile .profile-sprite-star:not([hidden])').count(),1);
 await page.locator('[data-item-id="badge_crown"]').click();await page.locator('[data-product-action]').click();await page.locator('[data-product-confirm]').click();
 await page.waitForFunction(()=>document.querySelector('[data-product-action]')?.textContent.includes('تفعيل'));
 await page.locator('[data-product-action]').click();await page.waitForFunction(()=>document.querySelector('[data-product-action]')?.textContent==='مفعّل الآن');
 assert.equal(buys,2);data=await (await contexts[0].request.get(base+'/api/store')).json();assert.equal(data.coins,850);assert.equal(data.equipped.name_badge,'badge_crown');
 await page.locator('[data-product-close]').click();
 for(const width of [320,390,600,768,1280]){
  await page.setViewportSize({width,height:900});
  assert.equal(await page.locator('.store-catalog').evaluate(node=>getComputedStyle(node).gridTemplateColumns.split(' ').length),width<=600?2:3);
  assert(await page.locator('.store-item-card').count()<=(width<=600?6:12));
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 }
 await page.setViewportSize({width:390,height:844});await page.goto(base+'/platform/?community=majlis');await page.locator('#community-room').waitFor({state:'visible'});
 const visitor=await contexts[1].newPage();visitor.on('pageerror',error=>errors.push(error.message));await visitor.goto(base+'/platform/?community=majlis');await visitor.locator('#community-room').waitFor({state:'visible'});
 await visitor.locator('[data-community-tab="members"]').click();const member=visitor.locator('.community-member').filter({hasText:users[0].username});await member.waitFor();
 assert.equal(await member.locator('.community-member-star:not([hidden])').count(),1);await member.click();await visitor.locator('#community-profile-name').filter({hasText:'نجم SamiDev'}).waitFor();
 assert.equal(await visitor.locator('#community-profile-modal .community-public-profile-star:not([hidden])').count(),1);
 assert.equal(await visitor.locator('#community-profile-modal .profile-sticker svg').getAttribute('viewBox'),'0 0 1 1');
 await visitor.screenshot({path:out+'/public-one-star-new-sticker.png'});
 const publicData=await (await contexts[1].request.get(base+'/api/public-profile/'+users[0].id)).json();assert.equal(publicData.user.starsCount,1);
 assert.equal(publicData.user.nameBadgeAsset,'/platform/assets/stickers/samidev-stickers.png#cell-0');
 assert.deepEqual(errors,[]);console.log(JSON.stringify({ok:true,checks:['Six products in two phone columns; three desktop columns','Preview and cancel never buy; only explicit confirmation charges','Double click charges once and buys exactly one star','Own lobby, own profile, member row and public card show one star','Original sprite sticker purchases, equips and appears publicly'],artifacts:out}));
}finally{
 for(const context of contexts)await context.request.post(base+'/api/communities/majlis/leave',{data:{}}).catch(()=>{});
 await browser.close();
 if(users.length){const clean=spawnSync(python,['-c',`import asyncio,os,sys,json,asyncpg
async def main():
 c=await asyncpg.connect(os.environ['SAMIDEV_TEST_DATABASE_URL'])
 for u in json.load(sys.stdin):
  await c.execute("DELETE FROM samidev_social_documents WHERE key=$1 OR key=$2 OR strpos(key, ':' || $3 || ':')>0 OR right(key,length($3)+1)=':' || $3",'sdp:user:'+u['id'],'sdp:username:'+u['username'].lower(),u['id'])
 await c.close()
asyncio.run(main())`],{input:JSON.stringify(users),encoding:'utf8'});assert.equal(clean.status,0,clean.stderr);}
}
