// Real mobile client: cue selection is an authoritative action, not a cosmetic swap.
import assert from 'node:assert/strict';
import fs from 'node:fs';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL;assert(base&&new URL(base).hostname==='127.0.0.1');
const out=process.env.SAMIDEV_TEST_ARTIFACTS||'/tmp/samidev-pyramid';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const pages=[],errors=[],results=[];
try{
 for(let i=0;i<2;i++){
  const c=await browser.newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true,deviceScaleFactor:2,extraHTTPHeaders:{Origin:base,'X-Forwarded-Proto':'https','X-Real-IP':`10.67.0.${i+1}`}});
  assert.equal((await c.request.post(base+'/api/auth/register',{data:{username:'pyr_'+Date.now().toString(36)+'_'+i,password:'Test-password-123',displayName:'لاعب '+(i+1)}})).status(),200);
  const p=await c.newPage();pages.push(p);p.on('pageerror',e=>errors.push(e.message));
  p.on('console',msg=>{if(/live move sequence gap|live move rejected|world did not settle/.test(msg.text()))errors.push(msg.text());});
 }
 const [host,peer]=pages;
 for(const mode of [8,9]){
  await host.goto(base+'/games/pool/index.html?online=1&action=quick&preset='+({8:'pool-pyramid',9:'pool-scratch'}[mode])+'&community=square&gameType='+mode);await host.waitForSelector('#sd-waiting.scene-ready',{timeout:30000});
  const room=await host.evaluate(()=>SamiDevNetwork.state.roomId);await peer.goto(base+'/games/pool/index.html?online=1&action=quick&preset='+({8:'pool-pyramid',9:'pool-scratch'}[mode])+'&community=square&gameType='+mode);
  for(const page of pages)await page.waitForFunction(()=>SamiDevNetwork.state.begun&&window.__gameLogic?.pyramid&&window.__gameLogic.canShoot(0),{},{timeout:30000});
  for(const page of pages){assert.equal(await page.evaluate(()=>window.__gameLogic.pyramid.mode),mode);assert((await page.evaluate(()=>window.__samidevGameState.images.get('images/ui/ui.webp').src)).includes('pyramid-ui.webp'));}
  assert.equal(await peer.evaluate(()=>SamiDevNetwork.state.roomId),room,'quick play must reuse the waiting room');
  for(const page of pages)assert(!(await page.evaluate(()=>window.__samidevGameState.images.get('images/imported/themes/th_basic_table.webp').src)).includes('samidev-pyramid-table.webp'));
  assert.equal(await host.locator('.pyr-pocket-jaw').count(),0,'no floating pocket knobs');
  await host.locator('.pyr-select-ball[data-rank="1"]').waitFor({state:'visible'});
  assert.equal(await peer.locator('.pyr-select-ball:not([hidden])').count(),0,'opponent has no cue-choice controls');
  assert.equal(await host.locator('.pyr-select-ball:not([hidden])').count(),15);
  await host.screenshot({path:out+`/pyramid-${mode}-choices.png`});
  await host.locator('.pyr-select-ball[data-rank="1"]').click();
  for(const page of pages)await page.waitForFunction(()=>window.__gameLogic.pyramid.ids[0]===1&&!window.__gameLogic.pyramid.canSelect,{},{timeout:15000});
  assert.equal(await host.locator('.pyr-select-ball:not([hidden])').count(),0);
  const seq=await host.evaluate(()=>[...window.__gameLogic._sequence]);
  await host.evaluate(()=>SamiDevNetwork.requestResync());
  await host.waitForFunction(()=>!window.__samidevGameState.network.snapshotBusy&&!window.__gameLogic._awaitingResync,{},{timeout:15000});
  assert.equal(await host.evaluate(()=>window.__gameLogic.pyramid.canSelect),false,'resync cannot reset choice quota');
  await host.evaluate(()=>{window.pyramidTrace=[];const sample=()=>{const g=window.__gameLogic;if(g.animator.isAnimatingWorld())window.pyramidTrace.push(JSON.parse(JSON.stringify(window.__samidevGameState.pyramidBallRotations||{})));window.pyramidTraceTimer=requestAnimationFrame(sample);};sample();});
  await peer.evaluate(()=>{window.pyramidTrace=[];const sample=()=>{const g=window.__gameLogic;if(g.animator.isAnimatingWorld())window.pyramidTrace.push(JSON.parse(JSON.stringify(window.__samidevGameState.pyramidBallRotations||{})));window.pyramidTraceTimer=requestAnimationFrame(sample);};sample();});
  await host.waitForFunction(()=>window.__gameLogic.canShoot(0),{},{timeout:15000});
  assert(await host.evaluate(()=>window.__gameLogic.localMove({a:1,st:.8,an:Math.PI/2,sp:[0,0]})));
  for(const page of pages)await page.waitForFunction(()=>window.pyramidTrace.length>10,{},{timeout:15000});
  for(const page of pages)await page.waitForFunction(()=>!window.__gameLogic.animator.isAnimatingWorld()&&!window.__gameLogic.preshooting&&!window.__samidevGameState.network.snapshotBusy,{},{timeout:30000});
  const states=await Promise.all(pages.map(page=>page.evaluate(()=>JSON.parse(JSON.stringify(window.__gameLogic.pyramid)))));assert.deepEqual(states[0],states[1]);
  for(const page of pages){
   const trace=await page.evaluate(()=>{cancelAnimationFrame(window.pyramidTraceTimer);return window.pyramidTrace;});
   const changed=Array.from({length:16},(_,id)=>new Set(trace.map(frame=>JSON.stringify(frame[id]))).size).filter(n=>n>5).length;
   assert(changed>4,'numbered sphere surfaces must roll at both clients');
  }
  assert(states[0].canSelect,'new shot permits one new selection');
  results.push({mode,selectionSequence:seq,finalState:states[0]});
  await host.screenshot({path:out+`/pyramid-${mode}-after-shot.png`});
  for(const page of pages)await page.evaluate(()=>SamiDevNetwork.leaveRoom({closeSocket:true}));
 }
 assert.deepEqual(errors,[]);fs.writeFileSync(out+'/report.json',JSON.stringify({ok:true,results},null,2));console.log(JSON.stringify({ok:true,modes:2,checks:['white selection circles','one authoritative selection','resync retains quota','role identities match','numbered sphere rolling at both clients','turn and scores consistent'],artifacts:out}));
}finally{await browser.close();}
