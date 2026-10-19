import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'/workspace/.samidev-ui-tools/node_modules/playwright-core/index.mjs');
const [launch,game]=process.argv.slice(2),origin=new URL(launch).origin;
const browser=await chromium.launch({executablePath:process.env.SAMIDEV_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try {
 const page=await browser.newPage({viewport:{width:390,height:844},deviceScaleFactor:1,isMobile:true,hasTouch:true});
 const errors=[],external=[],denied=[],sockets=[];
 page.on('pageerror',e=>errors.push(e.message));
 page.on('request',r=>{if(!r.url().startsWith('data:')&&new URL(r.url()).origin!==origin)external.push(r.url());});
 page.on('response',r=>{if(r.status()>=400)denied.push([r.status(),new URL(r.url()).pathname]);});
 page.on('websocket',s=>sockets.push(s.url()));
 await page.goto(launch,{waitUntil:'domcontentloaded'});
 try{await page.waitForFunction(()=>window.__samidevGameState?.localHost?.started&&window.__samidevGameState?.performance?.frames>1,{timeout:60000});}
 catch(e){throw new Error(JSON.stringify({game,errors,denied,status:await page.locator('#status').textContent(),preview:await page.evaluate(()=>window.__previewError)})+' '+e.message);}
 const state=await page.evaluate(()=>({online:window.__samidevGameState.network.online,frames:window.__samidevGameState.performance.frames,turn:window.__gameLogic.turn,started:window.__gameLogic.started}));
 assert.equal(state.online,false);assert.equal(state.started,true);assert.deepEqual(external,[]);assert.deepEqual(sockets,[]);assert.deepEqual(errors,[]);assert.deepEqual(denied,[]);
 assert.equal(await page.locator('#sd-room-ui,.sd-inventory-trigger,#community-profile-modal').count(),0);
 const moved=await page.evaluate(game=>{
  const logic=window.__gameLogic,host=window.__SamiDevWebHost;
  let seat=logic.turn?.[0]??0;
  if(game==='tablesoccer')seat=0;
  const before=logic._sequence?.[seat]??0;
  const move=game==='pool'?{a:3,an:0}:game==='carrom'?{m:6,ps:.5}:{a:5,team:'Red.c.h'};
  const accepted=host.injectMove(seat,move);
  return {before,after:logic._sequence?.[seat]??0,accepted};
 },game);
 assert.ok(moved.after>moved.before,JSON.stringify({game,...moved}));
 const out=process.env.PLAZR_CHILD_SCREENSHOTS;
 if(out){await fs.mkdir(out,{recursive:true});await page.screenshot({path:out+'/'+game+'.png'});}
 console.log(JSON.stringify({game,offline:true,renderedFrames:state.frames,localMove:true,externalRequests:external.length,webSockets:sockets.length}));
} finally {await browser.close();}
