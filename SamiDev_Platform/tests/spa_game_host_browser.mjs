import assert from 'node:assert/strict';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL;
const browser=await chromium.launch({executablePath:process.env.SAMIDEV_CHROMIUM||'/usr/bin/chromium',args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const errors=[],results=[];let pending=[];
try{
 for(const game of (process.env.SAMIDEV_SPA_GAMES||'pool,carrom,crazy8,tablesoccer').split(',')){
  const pages=[],navigations=[];pending=pages;
  for(let i=0;i<2;i++){
   const context=await browser.newContext(process.env.SAMIDEV_SPA_MOBILE==='1'?{viewport:{width:390,height:844},isMobile:true,hasTouch:true,deviceScaleFactor:2}:{});assert.equal((await context.request.post(base+'/api/auth/login',{data:{username:`perf_${game}_${i}`,password:'Test-password-123'}})).status(),200);
   if(process.env.SAMIDEV_SPA_MOBILE==='1')await context.addInitScript(()=>{
    window.__avatarCorners=[];
    const original=WebGLRenderingContext.prototype.texImage2D;
    WebGLRenderingContext.prototype.texImage2D=function(...args){
     const source=args[5];
     if(args.length===6&&source instanceof HTMLCanvasElement&&source.width===256&&source.height===256){
      const ctx=source.getContext('2d'),corners=[[0,0],[255,0],[0,255],[255,255]].map(([x,y])=>ctx.getImageData(x,y,1,1).data[3]);
      window.__avatarCorners.push({corners,center:ctx.getImageData(128,128,1,1).data[3]});
     }
     return original.apply(this,args);
    };
   });
   const page=await context.newPage();pages.push(page);page.on('pageerror',e=>errors.push(e.message));page.on('console',m=>{if(m.type()==='error'&&/Content Security Policy|violates|Refused to/.test(m.text()))errors.push(m.text());});page.on('request',r=>{if(r.isNavigationRequest())navigations.push(r.url());});
   await page.goto(base+'/platform/?community=majlis');await page.locator('#community-room').waitFor();
   await page.evaluate(()=>window.__appKept='preserved');
  }
  const [owner,guest]=pages;
  await owner.locator('#open-create').click();await owner.locator(`[data-create-game="${game}"]`).click();
  if(game==='crazy8')await owner.locator('#create-card-seats').selectOption('0');
  await owner.locator('#create-go').click();
  await owner.waitForFunction(()=>document.querySelector('#sd-game-host')?.contentWindow.__samidevGameState?.performance.frames>0,{},{timeout:45000});
  let a=await owner.locator('#sd-game-host').contentFrame();
  const room=await a.locator('body').evaluate(()=>{window.__keptLogic=__gameLogic;window.__keptCanvas=document.getElementById('game');return SamiDevNetwork.state.roomId;});
  assert.equal(await a.locator('body').evaluate(()=>SamiDevNetwork.state.begun),false);
  if(process.env.SAMIDEV_SCREENSHOT_DIR)await owner.screenshot({path:`${process.env.SAMIDEV_SCREENSHOT_DIR}/spa-${game}-waiting.png`});
  assert.equal(await a.locator('#sd-waiting,.sd-waiting-own').count(),0,'game has no separate waiting overlay');
  assert.equal(await a.locator('#status').isVisible(),false,'loading status disappears when the game renders');
  if(process.env.SAMIDEV_SPA_MOBILE==='1'){
   const rendering=await a.locator('body').evaluate(()=>({ratio:__samidevGameState.performance.pixelRatio,pixels:document.getElementById('game').width*document.getElementById('game').height,avatars:window.__avatarCorners}));
   assert(rendering.ratio>1.5&&rendering.ratio<=2,'high DPI phone surface');assert(rendering.pixels<=2001000,'bounded surface memory');
   assert(rendering.avatars.length>0,'real avatar texture uploads observed');
   for(const avatar of rendering.avatars){assert.deepEqual(avatar.corners,[0,0,0,0]);assert(avatar.center>0);}
   for(const id of ['sd-room-menu-button','sd-room-back-button']){
    const box=await a.locator('#'+id).boundingBox();assert.equal(box.width,44);assert.equal(box.height,44);assert.equal(await a.locator('#'+id+' svg').count(),1);
   }
  }
  await a.locator('#sd-room-menu-button').click();await a.locator('#sd-info').click();
  assert.equal(await a.locator('[data-table-action="close"]').isVisible(),true,'table owner retains management in the existing menu');
  await a.locator('#sd-room-info-modal .sd-close').click();
  if(process.env.SAMIDEV_SPA_MOBILE==='1')await guest.locator('#community-tab-games').click();
  await guest.locator(`.join-room[data-room="${room}"]`).waitFor({timeout:12000});await guest.locator(`.join-room[data-room="${room}"]`).click();
  await guest.locator('[data-entry-cancel]').click();assert.equal(await guest.locator('#sd-game-host').count(),0,'cancel never opens a game');
  await guest.locator(`.join-room[data-room="${room}"]`).click();await guest.locator('[data-entry-confirm]').click();
  for(const page of pages){const f=page.frames().find(f=>f.parentFrame());await f.waitForFunction(()=>SamiDevNetwork.state.begun&&__samidevGameState.localHost.started&&!__samidevGameState.network.snapshotBusy,{},{timeout:45000});assert.equal(await page.evaluate(()=>__appKept),'preserved');assert(new URL(page.url()).pathname==='/platform/');}
  assert(await a.locator('body').evaluate(()=>__keptLogic===__gameLogic&&__keptCanvas===document.getElementById('game')),'same waiting renderer and logic survive opponent joining');
  assert(!navigations.some(url=>/\/games\/|\/index\.html/.test(url)),'no per-game HTML document requested');
  if(game==='pool'){
   const context=await browser.newContext();
   assert.equal((await context.request.post(base+'/api/auth/login',{data:{username:'perf_pool_2',password:'Test-password-123'}})).status(),200);
   const watcher=await context.newPage();watcher.on('pageerror',e=>errors.push(e.message));
   await watcher.goto(base+'/platform/?community=majlis');
   await watcher.locator('#open-create').click();await watcher.locator('[data-create-game="pool"]').click();await watcher.locator('#create-go').click();
   await watcher.waitForFunction(()=>document.querySelector('#sd-game-host')?.contentWindow.__samidevGameState?.performance.frames>0,{},{timeout:45000});
   await watcher.frameLocator('#sd-game-host').locator('#sd-room-menu-button').click();await watcher.frameLocator('#sd-game-host').locator('#sd-info').click();
   watcher.once('dialog',dialog=>dialog.accept());await watcher.frameLocator('#sd-game-host').locator('[data-table-action="close"]').click();
   await watcher.locator('#sd-game-host').waitFor({state:'detached',timeout:15000});
   await watcher.locator(`.watch-room[data-room="${room}"]`).click();await watcher.locator('[data-entry-confirm]').click();
   const watching=()=>watcher.waitForFunction(()=>{const w=document.querySelector('#sd-game-host')?.contentWindow;return w?.SamiDevNetwork?.state.begun&&w.SamiDevNetwork.state.spectator&&w.__samidevGameState?.localHost.started;},{},{timeout:45000});
   await watching();assert.equal(new URL(watcher.url()).searchParams.get('watch'),'1');
   await watcher.reload();await watching();
   await watcher.frameLocator('#sd-game-host').locator('#sd-room-back-button').click();
   await watcher.frameLocator('#sd-game-host').locator('#sd-exit-confirm').click();
   await watcher.locator('#sd-game-host').waitFor({state:'detached'});await context.close();
   assert(await a.locator('body').evaluate(()=>SamiDevNetwork.state.begun&&!SamiDevGameUI.isGameOver()),'spectator exit keeps the match running');
   await owner.evaluate(()=>history.back());await owner.frameLocator('#sd-game-host').locator('#sd-exit-cancel').waitFor();await owner.frameLocator('#sd-game-host').locator('#sd-exit-cancel').click();
   assert.equal(await owner.evaluate(()=>__appKept),'preserved');
   const oldFrame=owner.frames().find(f=>f.parentFrame());
   const detached=owner.waitForEvent('framedetached',{predicate:f=>f===oldFrame,timeout:15000});
   await oldFrame.evaluate(()=>SamiDevNetwork.state.ws.close(4000,'test reconnect'));
   await detached;
   await owner.waitForFunction(()=>{const w=document.querySelector('#sd-game-host')?.contentWindow;return w?.SamiDevNetwork?.state.begun&&w.__samidevGameState?.localHost.started&&!w.__samidevGameState.network.snapshotBusy;},{},{timeout:45000});
   assert.equal(await owner.evaluate(()=>__appKept),'preserved','socket recovery keeps platform context');
   assert(oldFrame.isDetached(),'old renderer was disposed on transport recovery');
   await owner.reload();
   await owner.waitForFunction(()=>{const w=document.querySelector('#sd-game-host')?.contentWindow;return w?.SamiDevNetwork?.state.begun&&w.__samidevGameState?.localHost.started&&!w.__samidevGameState.network.snapshotBusy;},{},{timeout:45000});
   assert.equal(await owner.frameLocator('#sd-game-host').locator('body').evaluate(()=>SamiDevNetwork.state.roomId),room);
   await owner.evaluate(()=>window.__appKept='preserved');
  }
  // Return through the same resignation/leave contract as standalone games.
  {const frame=owner.frameLocator('#sd-game-host');await frame.locator('#sd-room-back-button').click();await frame.locator('#sd-exit-confirm').click();await owner.locator('#sd-game-host').waitFor({state:'detached',timeout:15000});}
  await guest.frameLocator('#sd-game-host').locator('.sdpp-rating-skip').waitFor({timeout:15000});
  await guest.frameLocator('#sd-game-host').locator('.sdpp-rating-skip').click();await guest.locator('#sd-game-host').waitFor({state:'detached',timeout:15000});
  for(const page of pages){assert.equal(await page.evaluate(()=>__appKept),'preserved');await page.locator('#community-room').waitFor();}
  results.push({game,keptPlatform:true,keptRenderer:true,noGameHtmlNavigation:true,exit:true});console.log(JSON.stringify(results.at(-1)));
  for(const page of pages)await page.context().close();
 }
 assert.deepEqual(errors,[]);
}catch(error){console.error('PAGE_ERRORS',errors);for(const p of pending)for(const f of p.frames())try{console.error('FRAME',f.url(),await f.evaluate(()=>({text:document.body?.innerText.slice(0,400),preview:window.__previewError,game:window.__SAMIDEV_GAME_ID,logic:!!window.__gameLogic,net:window.SamiDevNetwork?.state.roomId})));}catch(_){}throw error;}finally{await browser.close();}
