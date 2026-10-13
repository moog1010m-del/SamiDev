// Actual mobile renderer, authenticated creation UI, and Game Pool / three-player play.
import assert from 'node:assert/strict';
import fs from 'node:fs';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL;assert(base&&new URL(base).hostname==='127.0.0.1');
const out=process.env.SAMIDEV_TEST_ARTIFACTS||'/tmp/samidev-pool-modes';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const pages=[],contexts=[],errors=[];
try{
 for(let i=0;i<3;i++){
  const context=await browser.newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true,deviceScaleFactor:2,extraHTTPHeaders:{'X-Forwarded-Proto':'https','X-Real-IP':`10.45.0.${i+1}`,'Origin':base}});contexts.push(context);
  const response=await context.request.post(base+'/api/auth/register',{data:{username:'pool_ui_'+Date.now().toString(36)+'_'+i,password:'Test-password-123',displayName:'لاعب '+(i+1)}});assert.equal(response.status(),200);
  const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));pages.push(page);
 }
 const host=pages[0];await host.goto(base+'/platform/');await host.locator('.community-card[data-community="majlis"]').click();
 await host.locator('#quick-create-pool').click();await host.locator('#create-pool-mode').waitFor({state:'visible'});
 assert.equal(await host.locator('#create-pool-mode option').count(),10);await host.locator('#create-pool-mode').selectOption('7');
 await host.screenshot({path:out+'/pool-modes-picker.png'});await host.locator('#create-go').click();
 await host.waitForSelector('#sd-waiting.scene-ready',{timeout:30000});
 for(const mode of [7,6]){
  if(mode===6){await host.goto(base+'/games/pool/index.html?online=1&action=create&community=majlis&gameType=6');await host.waitForSelector('#sd-waiting.scene-ready',{timeout:30000});}
  const room=await host.evaluate(()=>window.SamiDevNetwork.state.roomId),capacity=mode===6?3:2;
  assert.equal(await host.evaluate(()=>window.SamiDevNetwork.state.settings.gameType),mode);
  for(let i=1;i<capacity;i++)await pages[i].goto(base+'/games/pool/index.html?online=1&action=join&community=majlis&room='+room);
  const current=pages.slice(0,capacity);
  for(const page of current)await page.waitForFunction(()=>window.SamiDevNetwork.state.begun&&window.__gameLogic.started&&!window.__samidevGameState.network.snapshotBusy,{},{timeout:30000});
  for(const page of current)assert.equal(await page.evaluate(()=>window.__gameLogic.seats),capacity);
  if(mode===7)for(const page of current)assert(await page.evaluate(()=>window.__gameLogic.freePool));
  const seat=await host.evaluate(()=>window.__gameLogic.turn[0]);await current[seat].waitForFunction(()=>window.__gameLogic.canShoot(window.__gameLogic.localSeat),{},{timeout:15000});
  const observer=current[(seat+1)%capacity];await observer.evaluate(()=>{
   window.poolSamples=[];const sample=()=>{const g=window.__gameLogic;if(g.animator.isAnimatingWorld())window.poolSamples.push(Array.from(g.table.cueBall.position));window.poolSampleTimer=requestAnimationFrame(sample);};sample();
  });
  assert(await current[seat].evaluate(()=>window.__gameLogic.localMove({a:1,st:.8,an:-Math.PI/2,sp:[0,0]})));
  await observer.waitForFunction(()=>window.poolSamples.length>10,{},{timeout:15000});
  for(const page of current)await page.waitForFunction(()=>!window.__gameLogic.animator.isAnimatingWorld()&&!window.__gameLogic.preshooting&&!window.__samidevGameState.network.snapshotBusy,{},{timeout:30000});
  const replicas=await Promise.all(current.map(page=>page.evaluate(()=>({turn:[...window.__gameLogic.turn],scores:[...window.__gameLogic.freePoolScores]}))));
  for(const value of replicas)assert.deepEqual(value,replicas[0]);
  assert(new Set(await observer.evaluate(()=>window.poolSamples.map(p=>p.map(v=>v.toFixed(1)).join(',')))).size>10,'opponent must see actual motion');
  await observer.evaluate(()=>cancelAnimationFrame(window.poolSampleTimer));
  await host.screenshot({path:out+`/pool-mode-${mode}-mobile.png`});
  for(const page of current)await page.evaluate(()=>window.SamiDevNetwork.leaveRoom({closeSocket:true}));
 }
 assert.deepEqual(errors,[]);console.log(JSON.stringify({ok:true,checks:['all ten choices visible','Game Pool created from UI','authoritative mode reaches both clients','three-player pool renders','remote shot animation','scores and turn agree'],artifacts:out}));
}finally{await browser.close();}
