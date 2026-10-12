// Real Chromium/WebGL + running backend/PostgreSQL/Redis/GameHost. Test databases only.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL||'http://127.0.0.1:8088';
assert(['127.0.0.1','localhost'].includes(new URL(base).hostname),'Use a local test deployment');
assert(process.env.SAMIDEV_TEST_DATABASE_URL&&process.env.SAMIDEV_TEST_REDIS_URL,'Test database URLs required');
const out=process.env.SAMIDEV_TEST_ARTIFACTS||'/tmp/samidev-profile-browser';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:process.env.SAMIDEV_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const contexts=[],errors=[],checks=[];
let accounts=[];
const python=process.env.SAMIDEV_TEST_PYTHON||'python3';
function seed(uid){
  const result=spawnSync(python,['-c',`
import asyncio,json,os,sys
sys.path.insert(0,'backend')
from postgres_platform import PostgresPlatformService
import redis.asyncio as redis
async def main():
 r=redis.from_url(os.environ['SAMIDEV_TEST_REDIS_URL'],decode_responses=True)
 s=PostgresPlatformService(os.environ['SAMIDEV_TEST_DATABASE_URL'],r)
 await s.start()
 try:
  uid=json.load(sys.stdin)['uid']
  await s.r.hset(s.k_user(uid),'coins','2000')
  for item in ['badge_crown','badge_fire','profile_star','profile_star']:
   await s.buy_store_item(uid,item)
  await s.grant_store_item(uid,'pool_cue_moon')
  for gid,wins in [('pool',23),('carrom',8),('crazy8',51)]:
   for i in range(wins):await s.record_game_result(uid,gid,'browser-'+gid+':'+str(i),won=True)
 finally:await s.close();await r.aclose()
asyncio.run(main())
  `],{cwd:path.resolve(import.meta.dirname,'..'),input:JSON.stringify({uid}),encoding:'utf8'});
  assert.equal(result.status,0,result.stderr);
}
try{
  for(let i=0;i<2;i++){
    const context=await browser.newContext({viewport:{width:390,height:844}});contexts.push(context);
    const registered=await context.request.post(base+'/api/auth/register',{data:{username:'br_'+Date.now().toString(36)+'_'+i,password:'Test-password-123',displayName:i?'الخصم':'نجم SamiDev'}});
    assert.equal(registered.status(),200,await registered.text());accounts.push((await registered.json()).user);
  }
  seed(accounts[0].id);
  const page=await contexts[0].newPage();page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/platform/');await page.waitForFunction(()=>window.SamiDevMobilePlatform);await page.locator('#app').waitFor({state:'visible'});
  await page.evaluate(()=>window.SamiDevMobilePlatform.navigate('profile'));
  const own=page.locator('#own-profile-details');await own.locator('.sd-rank-row').first().waitFor();
  assert.equal(await own.locator('.sd-rank-row').count(),4);
  assert.equal(await own.locator('.sd-owned-card').count(),3);
  await own.locator('.sd-collection-more').click();assert.equal(await own.locator('.sd-owned-card').count(),4);
  await own.locator('select').selectOption('pool');assert.equal(await own.locator('.sd-owned-card').count(),1);
  await own.locator('.sd-owned-card').click();assert(await own.locator('.sd-item-detail').isVisible());
  await page.keyboard.press('Escape');assert(!await own.locator('.sd-item-detail').isVisible());
  await own.locator('select').selectOption('all');await own.locator('.sd-collection-more').click();
  const pool=own.locator('[data-game="pool"]');assert((await pool.innerText()).includes('٢٣'));
  assert.equal(await pool.locator('.sd-rank-star').getAttribute('aria-label'),'المستوى 3');assert.equal(await pool.locator('.sd-rank-star b').innerText(),'3');
  await own.locator('.sd-profile-full').click();assert(await pool.locator('.sd-rank-expanded').isVisible());
  for(const width of [320,390,768,1280]){
    await page.setViewportSize({width,height:900});
    assert(await own.evaluate(n=>n.scrollWidth<=n.clientWidth+1),'Profile details overflow at '+width);
  }
  await page.setViewportSize({width:390,height:1000});
  await own.screenshot({path:path.join(out,'profile-own.png')});
  checks.push('own profile: real inventory preview/browse/filter/detail, four games, rank progress, compact/full and responsive widths');

  const visitor=await contexts[1].newPage();visitor.on('pageerror',e=>errors.push(e.message));
  await visitor.goto(base+'/platform/');await visitor.waitForFunction(()=>window.SamiDevMobilePlatform);await visitor.locator('#app').waitFor({state:'visible'});
  await visitor.evaluate(id=>window.SamiDevMobilePlatform.openProfile(id),accounts[0].id);
  await visitor.locator('#community-profile-full').click();
  const publicCard=visitor.locator('#sd-public-extra');await publicCard.locator('.sd-owned-card').first().waitFor();
  assert.equal(await publicCard.locator('.sd-owned-card').count(),3);
  assert.equal(await publicCard.locator('.sd-rank-row').count(),4);
  const api=await contexts[1].request.get(base+'/api/public-profile/'+accounts[0].id);const profile=(await api.json()).user;
  assert(!('coins' in profile)&&!('passwordHash' in profile));
  await publicCard.locator('.sd-collection-more').click();assert.equal(await publicCard.locator('.sd-owned-card').count(),4);
  await visitor.screenshot({path:path.join(out,'profile-public.png')});
  checks.push('another player sees the same owned items and progression, without private wallet or credentials');
  await page.close();await visitor.close();

  for(const [game,entry] of Object.entries({pool:'games/pool/index.html',carrom:'index.html',tablesoccer:'games/tablesoccer/index.html',crazy8:'games/crazy8/index.html'})){
    const host=await contexts[0].newPage(),opponent=await contexts[1].newPage(),sent=[];
    host.on('pageerror',e=>errors.push(game+': '+e.message));opponent.on('pageerror',e=>errors.push(game+': '+e.message));
    host.on('websocket',socket=>socket.on('framesent',event=>{try{sent.push(JSON.parse(event.payload));}catch{}}));
    await host.goto(`${base}/${entry}?online=1&action=create&community=majlis&players=0&seats=0&live=1`);
    await host.waitForSelector('#sd-waiting.scene-ready',{timeout:30000});
    await host.waitForFunction(()=>window.__samidevGameState?.performance?.frames>0);
    const waiting=await host.evaluate(()=>({error:window.__previewError,waiting:window.__samidevGameState.network.waiting,started:window.__gameLogic.started,room:window.SamiDevNetwork.state.roomId,ready:window.SamiDevNetwork.state.roster.some(x=>x?.ready),logic:!!window.__gameLogic,renderer:document.querySelector('#sd-waiting').dataset.renderer}));
    assert(!waiting.error);assert(waiting.waiting&&!waiting.started&&!waiting.ready&&waiting.logic);assert.equal(waiting.renderer,'native');
    assert(!sent.some(x=>['move','runtime_ready'].includes(x.type)),game+' must stay server gated');
    assert.equal(await host.locator('.sd-waiting-board,.sd-waiting-mirror').count(),0);
    assert(await host.evaluate(()=>!!window.SamiDevProfileDetails));
    if(game==='carrom')assert.equal(await host.evaluate(()=>window.__samidevGameState.carromBoardArtwork),'samidev-walnut');
    await host.screenshot({path:path.join(out,game+'-waiting.png')});
    await host.evaluate(()=>window.SamiDevPlayerProfileUI.openSeat(0));
    await host.waitForSelector('#sdpp-card [data-action=full]');
    assert.equal(await host.locator('#sdpp-card [data-profile-details]').isVisible(),false);
    await host.screenshot({path:path.join(out,game+'-profile-compact.png')});
    await host.locator('#sdpp-card [data-action=full]').click();
    await host.waitForSelector('#sdpp-card [data-profile-details] .sd-rank-row',{timeout:10000});
    assert.equal(await host.locator('#sdpp-card .sd-rank-row').count(),4);
    assert.equal(await host.locator('#sdpp-card .sd-owned-card').count(),3);
    await host.screenshot({path:path.join(out,game+'-profile-full.png')});
    await host.locator('.sdpp-close').click();
    assert.equal(await host.locator('#sdpp-card [data-profile-details]').isVisible(),false);
    await host.locator('.sdpp-close').click();
    // The scene is reused, rather than replaced by an imitation or second logic.
    await host.evaluate(()=>{window.__waitingLogicForTest=window.__gameLogic;});
    await opponent.goto(`${base}/${entry}?online=1&action=join&room=${waiting.room}&community=majlis&players=0&seats=0&live=1`);
    for(const p of [host,opponent])await p.waitForFunction(()=>window.__samidevGameState?.localHost?.started&&!window.__samidevGameState.network.waiting,{},{timeout:30000});
    assert(await host.evaluate(()=>window.__waitingLogicForTest===window.__gameLogic));
    assert.equal(await host.locator('#sd-waiting').count(),0);assert(!await host.evaluate(()=>window.__previewError||window.__renderError));
    for(const p of [host,opponent])await p.waitForFunction(()=>window.SamiDevNetwork.state.begun&&window.__gameLogic.started,{},{timeout:10000});
    assert.equal(sent.filter(x=>x.type==='runtime_ready').length,1);
    await host.screenshot({path:path.join(out,game+'-started.png')});
    checks.push(game+': real native waiting scene, no early ready/moves, same scene after opponent joins');
    for(const p of [host,opponent])await p.evaluate(()=>window.SamiDevNetwork.leaveRoom({closeSocket:true}));
    await host.close();await opponent.close();
  }
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({ok:true,checks,count:checks.length,artifacts:out}));
}finally{
  await browser.close();
  // Delete only this test's account documents; result rows cascade with accounts.
  if(accounts.length){
    const cleaned=spawnSync(python,['-c',`import asyncio,json,os,sys,asyncpg
async def main():
 c=await asyncpg.connect(os.environ['SAMIDEV_TEST_DATABASE_URL'])
 for user in json.load(sys.stdin):
  uid=user['id']
  await c.execute("DELETE FROM samidev_social_documents WHERE key=$1 OR key=$2 OR strpos(key, ':' || $3 || ':')>0 OR right(key,length($3)+1)=':' || $3",'sdp:user:'+uid,'sdp:username:'+user['username'].lower(),uid)
 await c.close()
asyncio.run(main())`],{input:JSON.stringify(accounts),encoding:'utf8'});
    assert.equal(cleaned.status,0,cleaned.stderr);
  }
}
