import fs from 'node:fs';
import assert from 'node:assert/strict';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL;
const browser=await chromium.launch({executablePath:process.env.SAMIDEV_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const results=[],diagnostics=[];let pending=[];
try{
 for(const game of (process.env.JOIN_GAMES||'pool,carrom,crazy8,tablesoccer').split(',')){
  const pages=[],errors=[];pending=pages;
  for(let i=0;i<2;i++){
   const context=await browser.newContext();
   if(process.env.JOIN_SHARED_HOST==='1'){
    await context.addInitScript(()=>{window.SamiDevMobile={postMessage(raw){if(JSON.parse(raw).type==='game_runtime_ready')window.__nativeRuntimeReady=true;}};});
   }
   assert.equal((await context.request.post(base+'/api/auth/login',{data:{username:`perf_${game}_${i}`,password:'Test-password-123'}})).status(),200);
   const page=await context.newPage();pages.push(page);page.on('pageerror',e=>errors.push(e.message));
   page.on('console',m=>{if(m.type()==='error')diagnostics.push(m.text());});
   page.on('websocket',ws=>ws.on('socketerror',error=>diagnostics.push(error)));
   await page.addInitScript(()=>{
    const stats=window.__joinPerf={fetches:[],images:[],longTasks:[],syncXHR:[],gaps:[],events:[],joinAt:null};
    const fetch0=window.fetch;window.fetch=function(input){stats.fetches.push({path:String(input),at:performance.now()});return fetch0.apply(this,arguments);};
    const image=Object.getOwnPropertyDescriptor(HTMLImageElement.prototype,'src');Object.defineProperty(HTMLImageElement.prototype,'src',{get:image.get,set(value){stats.images.push({path:String(value),at:performance.now()});return image.set.call(this,value);}});
    const open=XMLHttpRequest.prototype.open;XMLHttpRequest.prototype.open=function(method,url,async){if(async===false)stats.syncXHR.push({path:String(url),at:performance.now()});return open.apply(this,arguments);};
    new PerformanceObserver(list=>{for(const entry of list.getEntries())stats.longTasks.push({at:entry.startTime,ms:entry.duration});}).observe({type:'longtask',buffered:true});
    let last;const frame=t=>{if(last!==undefined&&t-last>50)stats.gaps.push({at:t,ms:t-last});last=t;requestAnimationFrame(frame);};requestAnimationFrame(frame);
    let net;Object.defineProperty(window,'SamiDevNetwork',{configurable:true,get:()=>net,set:value=>{net=value;for(const event of ['assignment','start','room_state','begin_match'])value.on(event,()=>stats.events.push({type:event,at:performance.now()}));}});
   });
  }
  const [owner,guest]=pages;
  const entry=game==='carrom'?'/index.html':`/games/${game}/index.html`;
  await owner.goto(`${base}${entry}?online=1&action=create&community=majlis&seats=0`);
  await owner.waitForSelector('#sd-waiting.scene-ready',{timeout:45000});
  const room=await owner.evaluate(()=>SamiDevNetwork.state.roomId);
  await owner.evaluate(()=>__joinPerf.joinAt=performance.now());
  await guest.goto(`${base}${entry}?online=1&action=join&community=majlis&room=${room}`);
  for(const page of pages)await page.waitForFunction(()=>SamiDevNetwork.state.begun&&__samidevGameState.localHost.started&&!__samidevGameState.network.waiting,{},{timeout:45000});
  if(process.env.JOIN_SHARED_HOST==='1')for(const page of pages)assert(await page.evaluate(()=>window.__nativeRuntimeReady===true),'native host receives readiness after asynchronous bootstrap');
  await owner.waitForTimeout(500);
  const measured=[];
  for(const page of pages){
   measured.push(await page.evaluate(()=>{
    const p=__joinPerf;const initial=p.events.find(v=>v.type==='assignment')?.at??0;
    const start=p.events.find(v=>v.type==='start')?.at??0;
    const assets=p.fetches.filter(v=>new URL(v.path,location.href).pathname.endsWith('/__assets.json'));
    const presetPaths=new Set((window.__assetImages||[]).map(path=>new URL(path,window.__SAMIDEV_ASSET_ROOT||location.href).pathname));
    const presetCounts=p.images.reduce((all,v)=>{const path=new URL(v.path,location.href).pathname;if(presetPaths.has(path))all[path]=(all[path]||0)+1;return all;},{});
    const duplicateImages=Object.entries(p.images.reduce((all,v)=>{all[v.path]=(all[v.path]||0)+1;return all;},{})).filter(([path,n])=>n>1);
    return {presetRepeats:Object.entries(presetCounts).filter(([path,n])=>n>1),assetIndexLoads:assets.length,assetIndexAt:assets.map(v=>Math.round(v.at)),duplicateImageLoads:duplicateImages.length,images:p.images.length,
     assignmentToBeginMs:Math.round((p.events.find(v=>v.type==='begin_match')?.at??performance.now())-initial),
     startToBeginMs:Math.round((p.events.find(v=>v.type==='begin_match')?.at??performance.now())-start),
     postStartLongTasks:p.longTasks.filter(v=>v.at>=start),syncXHR:p.syncXHR,
     events:p.events,gapsAfterJoin:p.gaps.filter(v=>v.at>=(p.joinAt??0)).sort((a,b)=>b.ms-a.ms).slice(0,4),
     scriptLoads:performance.getEntriesByType('resource').filter(v=>v.name.includes('/main.js')).length,
     logicStarted:__gameLogic.started,frames:__samidevGameState.performance.frames};
   }));
   const record=measured.at(-1);
   assert.equal(record.assetIndexLoads,1,'waiting and match startup share one asset preparation');
   assert.deepEqual(record.presetRepeats,[],'initial atlas images must not be rebuilt on join');
   assert.equal(record.scriptLoads,1,'native bundle executes once');
   assert(record.logicStarted&&record.frames>0,'native scene starts and renders');
   assert.deepEqual(record.syncXHR,[],'no synchronous network resource fallback during normal startup');
   await page.context().close();
  }
  assert.deepEqual(errors,[]);
  results.push({game,owner:measured[0],guest:measured[1],errors});console.log(JSON.stringify({game,assetPreparations:measured.map(v=>v.assetIndexLoads),presetRepeats:measured.map(v=>v.presetRepeats.length),startToBeginMs:measured.map(v=>v.startToBeginMs)}));
 }
}catch(error){console.error('DIAGNOSTICS',diagnostics.map(text=>String(text).replace(/([?&](?:ticket|token)=)[^&'"\s]+/g,'$1[redacted]')));for(const page of pending)try{console.error('PAGE_STATE',await page.evaluate(()=>({url:location.href,text:document.body?.innerText.slice(0,600),bootstrap:!!window.SamiDevGameBootstrap,game:window.__SAMIDEV_GAME_ID,logic:!!window.__gameLogic,base:document.baseURI})));}catch(_){}throw error;}finally{await browser.close();fs.writeFileSync(process.env.JOIN_PERF_REPORT||'/tmp/samidev-game-join.json',JSON.stringify(results,null,2));}
