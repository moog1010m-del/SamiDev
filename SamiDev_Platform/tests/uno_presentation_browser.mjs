// Real native four-player waiting/start scenes and chat; local test deployment only.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL||'http://127.0.0.1:8088';
assert(['127.0.0.1','localhost'].includes(new URL(base).hostname));assert(process.env.SAMIDEV_TEST_DATABASE_URL);
const out=process.env.SAMIDEV_TEST_ARTIFACTS||'/tmp/samidev-uno';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const users=[],contexts=[],pages=[],errors=[];
try {
 for(let i=0;i<4;i++){
  const context=await browser.newContext({viewport:{width:1440,height:900}});contexts.push(context);
  const r=await context.request.post(base+'/api/auth/register',{data:{username:'uno_'+Date.now().toString(36)+'_'+i,password:'Test-password-123',displayName:'لاعب '+(i+1)}});assert.equal(r.status(),200);users.push((await r.json()).user);
  const page=await context.newPage();pages.push(page);page.on('pageerror',e=>errors.push(e.message));
 }
 const host=pages[0];
 await host.goto(base+'/games/crazy8/index.html?online=1&action=create&community=majlis&seats=2&special=0&live=1');
 await host.waitForSelector('#sd-waiting.scene-ready',{timeout:30000});
 assert((await host.title()).includes('Uno'));
 const waiting=await host.evaluate(()=>({room:window.SamiDevNetwork.state.roomId,started:window.__samidevGameState.localHost.started,texture:window.__samidevGameState.images.get('images/table-background.webp').src}));
 assert(!waiting.started);assert(waiting.texture.includes('samidev-uno-felt.png'));
 assert(await host.locator('.sd-waiting-own').isHidden());
 const dimensions=await host.locator('#game').boundingBox();assert(dimensions.width/dimensions.height<.9);assert(dimensions.x>0);
 await host.screenshot({path:out+'/uno-waiting-desktop.png'});
 for(let i=1;i<4;i++)await pages[i].goto(base+'/games/crazy8/index.html?online=1&action=join&community=majlis&room='+waiting.room);
 for(const page of pages)await page.waitForFunction(()=>window.SamiDevNetwork.state.begun&&window.__gameLogic.started,{},{timeout:30000});
 await host.locator('#sd-chat-input').fill('أهلًا، مباراة أونو جميلة');await host.locator('#sd-chat-form').evaluate(form=>form.requestSubmit());
 for(const page of pages)await page.locator('.sd-chat-text').filter({hasText:'أهلًا، مباراة أونو جميلة'}).waitFor();
 await pages[1].locator('#sd-chat-input').fill('رسالة اللاعب الآخر');await pages[1].locator('#sd-chat-form').evaluate(form=>form.requestSubmit());
 await host.locator('.sd-chat-text').filter({hasText:'رسالة اللاعب الآخر'}).waitFor();
 const own=host.locator('.sd-chat-message').filter({hasText:'أهلًا، مباراة أونو جميلة'}),other=host.locator('.sd-chat-message').filter({hasText:'رسالة اللاعب الآخر'});
 assert(await own.evaluate(row=>row.classList.contains('me')));assert(!await other.evaluate(row=>row.classList.contains('me')));
 const ownRect=await own.boundingBox(),otherRect=await other.boundingBox();assert(ownRect.x+ownRect.width>otherRect.x+otherRect.width);
 const appearance=row=>{const style=getComputedStyle(row.querySelector('.sd-chat-message-body'));return [style.backgroundColor,style.borderColor,style.borderRadius];};
 assert.deepEqual(await own.evaluate(appearance),await other.evaluate(appearance));
 assert.equal(await host.locator('#sd-chat-send svg').count(),1);
 await host.waitForFunction(()=>!window.__samidevGameState.network.snapshotBusy&&!window.__samidevGameState.unoWaitingNeedsLayout,{},{timeout:15000});
 await host.waitForTimeout(300);
 await host.screenshot({path:out+'/uno-started-desktop.png',animations:'disabled'});
 await host.setViewportSize({width:390,height:844});
 await host.locator('#sd-chat-launcher').click();await host.locator('#sd-chat-ui.mobile-open').waitFor();
 assert(await host.locator('#sd-chat-input').isVisible());
 await host.locator('#sd-chat-close').click();
 await host.screenshot({path:out+'/uno-mobile.png'});
 assert(!await host.evaluate(()=>window.__previewError||window.__renderError));assert.deepEqual(errors,[]);
 console.log(JSON.stringify({ok:true,checks:['Original felt texture and bounded desktop table','No duplicate waiting player badges','Four real players start and exchange chat','Mobile chat opens/closes without render errors'],artifacts:out}));
} finally {
 for(const page of pages)if(!page.isClosed())await page.evaluate(()=>window.SamiDevNetwork?.leaveRoom({closeSocket:true})).catch(()=>{});
 await browser.close();
 if(users.length){const clean=spawnSync(process.env.SAMIDEV_TEST_PYTHON||'python3',['-c',`import asyncio,asyncpg,os,sys,json
async def main():
 c=await asyncpg.connect(os.environ['SAMIDEV_TEST_DATABASE_URL'])
 for u in json.load(sys.stdin):await c.execute('DELETE FROM samidev_social_documents WHERE key=$1 OR key=$2','sdp:user:'+u['id'],'sdp:username:'+u['username'].lower())
 await c.close()
asyncio.run(main())`],{input:JSON.stringify(users),encoding:'utf8'});assert.equal(clean.status,0,clean.stderr);}
}
