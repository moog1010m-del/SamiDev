// Real browser/store API plus a controlled server-event fixture for the reward widget.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL||'http://127.0.0.1:8088';
assert(['127.0.0.1','localhost'].includes(new URL(base).hostname));
assert(process.env.SAMIDEV_TEST_DATABASE_URL);
const out=process.env.SAMIDEV_TEST_ARTIFACTS||'/tmp/samidev-store-preview';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
let user,game;
const errors=[],checks=[];
try {
 const context=await browser.newContext({viewport:{width:390,height:900}});
 const response=await context.request.post(base+'/api/auth/register',{data:{username:'shop_'+Date.now().toString(36),password:'Test-password-123'}});
 assert.equal(response.status(),200);user=(await response.json()).user;
 const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/platform/');await page.locator('#app').waitFor({state:'visible'});
 assert(await page.locator('.bottom-nav').isVisible());assert.equal(await page.locator('.bottom-btn svg').count(),5);
 await page.locator('.bottom-btn[data-page="store"]').click();
 await page.locator('.store-item-card').first().waitFor();
 assert.equal(await page.locator('.daily-reward-card').count(),0);
 for(const width of [320,390,768,1280]) {
  await page.setViewportSize({width,height:900});
  const dimensions=await page.locator('.store-catalog').evaluate(n=>({cols:getComputedStyle(n).gridTemplateColumns.split(' ').length,overflow:n.scrollWidth>n.clientWidth+1}));
  assert.equal(dimensions.cols,width<=600?2:3);assert(!dimensions.overflow);
  assert(await page.locator('.store-item-card').count()<=(width<=600?6:12));
 }
 await page.setViewportSize({width:390,height:900});
 const pager=page.locator('#store-pagination');
 if(await pager.isVisible()) {
  const first=await page.locator('.store-item-copy strong').first().innerText();
  await pager.getByRole('button',{name:'التالي'}).click();
  assert.notEqual(await page.locator('.store-item-copy strong').first().innerText(),first);
 }
 await page.locator('[data-category="pool"]').click();
 const catalog=await context.request.get(base+'/api/store');const pool=(await catalog.json()).catalog.filter(x=>x.category==='pool');
 assert.equal(await page.locator('.store-item-card').count(),Math.min(12,pool.length));
 await page.locator('[data-category="all"]').click();
 await page.screenshot({path:out+'/store-mobile.png',fullPage:true});
 checks.push('Two phone columns with six-item pages; three wider columns with twelve-item pages; filters and no permanent reward card');
 await page.locator('.bottom-btn[data-page="lobby"]').click();
 await page.goto(base+'/platform/?community=majlis');await page.locator('#community-room').waitFor({state:'visible'});
 assert(!await page.locator('.bottom-nav').isVisible());
 await page.evaluate(()=>window.SamiDevMobilePlatform.navigate('profile'));
 assert(!await page.locator('.bottom-nav').isVisible());
 await page.locator('#mobile-menu').click();
 await page.locator('#exit-community').click();
 await page.locator('.bottom-nav').waitFor({state:'visible'});
 checks.push('Bottom bar stays hidden throughout room/profile navigation and returns only on leaving the room');
 game=await context.newPage();game.on('pageerror',e=>errors.push(e.message));let socket;
 await game.routeWebSocket('**/ws*',ws=>{socket=ws;const upstream=ws.connectToServer();upstream.onMessage(m=>ws.send(m));ws.onMessage(m=>upstream.send(m));});
 await game.goto(base+'/games/pool/index.html?online=1&action=create&community=majlis&players=0&live=1');
 await game.waitForSelector('#sd-waiting.scene-ready',{timeout:30000});
 const fixture={type:'match_reward',id:'controlled-notice',amount:50,rewardedMatches:2,remainingMatches:3};
 socket.send(JSON.stringify(fixture));await game.locator('#sd-match-reward').waitFor();
 assert((await game.locator('#sd-match-reward').innerText()).includes('2/5'));
 socket.send(JSON.stringify(fixture));assert.equal(await game.locator('#sd-match-reward').count(),1);
 await game.locator('#sd-match-reward').waitFor({state:'detached',timeout:7000});
 socket.send(JSON.stringify({...fixture,id:'daily-limit',amount:0,rewardedMatches:5,remainingMatches:0}));
 await game.locator('#sd-match-reward').waitFor();assert((await game.locator('#sd-match-reward').innerText()).includes('اكتملت مكافآت اليوم'));
 await game.getByRole('button',{name:'إغلاق إشعار المكافأة'}).click();
 assert.equal(await game.locator('#sd-match-reward').count(),0);
 checks.push('Server-event fixture renders one brief reward notice with progress, dismisses automatically, and handles daily limit');
 assert.deepEqual(errors,[]);console.log(JSON.stringify({ok:true,checks,artifacts:out}));
} finally {
 if(game&&!game.isClosed())await game.evaluate(()=>window.SamiDevNetwork?.leaveRoom({closeSocket:true})).catch(()=>{});
 await browser.close();
 if(user){const cleanup=spawnSync(process.env.SAMIDEV_TEST_PYTHON||'python3',['-c',`import asyncio,asyncpg,os,json,sys
async def main():
 u=json.load(sys.stdin);c=await asyncpg.connect(os.environ['SAMIDEV_TEST_DATABASE_URL']);await c.execute('DELETE FROM samidev_social_documents WHERE key=$1 OR key=$2','sdp:user:'+u['id'],'sdp:username:'+u['username'].lower());await c.close()
asyncio.run(main())`],{input:JSON.stringify(user),encoding:'utf8'});assert.equal(cleanup.status,0,cleanup.stderr);}
}
