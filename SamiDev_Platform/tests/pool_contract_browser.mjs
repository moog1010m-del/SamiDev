import assert from 'node:assert/strict';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL;assert(new URL(base).hostname==='127.0.0.1');
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const pages=[],errors=[],results=[];
try{
 for(let i=0;i<2;i++){
  const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,extraHTTPHeaders:{Origin:base,'X-Forwarded-Proto':'https','X-Real-IP':`10.92.0.${i+1}`}});
  // The HTTP fixture maps the native entry alias to the verified shared host.
  await context.addInitScript(()=>{window.SamiDevMobile={postMessage(){}};});
  assert.equal((await context.request.post(base+'/api/auth/register',{data:{username:'contract_'+Date.now().toString(36)+'_'+i,password:'Test-password-123'}})).status(),200);
  const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));pages.push(page);
 }
 for(const mode of [0,7]){
  let reconnectResyncs=0;
  const driftRecoveries=[];
  const [a,b]=pages;
  await a.goto(base+'/games/pool/index.html?online=1&action=create&community=majlis&gameType='+mode);
  await a.waitForFunction(()=>window.__samidevGameState?.network.waiting&&window.__samidevGameState.performance.frames>0,{},{timeout:30000});const rid=await a.evaluate(()=>SamiDevNetwork.state.roomId);
  await b.goto(base+'/games/pool/index.html?online=1&action=join&community=majlis&room='+rid);
  for(const page of pages){await page.waitForFunction(()=>window.SamiDevNetwork?.state.begun&&!window.__samidevGameState.network.snapshotBusy&&window.__gameLogic?.started,{},{timeout:30000});await page.evaluate(()=>{window.contractResyncs=0;SamiDevNetwork.on('resync_state',()=>window.contractResyncs++);});}
  for(const page of pages){assert(await page.evaluate(()=>!!window.SamiDevGameBootstrap&&window.__SAMIDEV_QUERY===undefined),'native host keeps URL-based lifecycle');assert.equal(new URL(page.url()).searchParams.get('room'),rid);}
  for(let i=0;i<8;i++){
   for(const page of pages)await page.waitForFunction(()=>!SamiDevNetwork.state.resyncInFlight&&!window.__samidevGameState.network.snapshotBusy&&!window.__gameLogic.animator.isAnimatingWorld()&&!window.__gameLogic.preshooting&&!window.__gameLogic.paused,{},{timeout:30000});
   const turn=await a.evaluate(()=>window.__gameLogic.turn[0]);
   await pages[turn].waitForFunction(()=>window.__gameLogic.canShoot(window.__gameLogic.localSeat),{},{timeout:15000});
   const shot=await pages[turn].evaluate(i=>{const g=window.__gameLogic,c=g.table.cueBall;const target=g.table.balls.find(x=>!x.isPocketed()&&x.rank!==8);return {a:1,st:i===0?.8:.2,an:i===0?-Math.PI/2:Math.atan2(target.position[1]-c.position[1],target.position[0]-c.position[0])+.12,sp:[0,0]};},i);
   const before=await a.evaluate(()=>window.__gameLogic.noAnimations);
   // Exercise accumulated fine-aim revolutions through the real native client,
   // before its optimistic move/sequence bookkeeping, then shoot the same angle.
   const turns=(i%2===0?1:-1)*Math.PI*20;
   assert(await pages[turn].evaluate(an=>window.__gameLogic.localMove({a:3,an}),shot.an+turns));
   await pages[turn].waitForFunction(()=>window.__gameLogic._localMoves.length===0,{},{timeout:15000});
   shot.an+=turns;
   if(i===0){
    assert(await pages[turn].evaluate(shot=>{const g=window.__gameLogic,before=[...g._sequence];SamiDevNetwork.state.connected=false;const blocked=!g.localMove(shot);SamiDevNetwork.state.connected=true;return blocked&&JSON.stringify(before)===JSON.stringify(g._sequence);},shot),'disconnected transport blocks local mutation');
    assert(await pages[turn].evaluate(shot=>{const g=window.__gameLogic,before=[...g._sequence];window.__samidevGameState.network.snapshotBusy=true;const blocked=!g.localMove(shot);window.__samidevGameState.network.snapshotBusy=false;return blocked&&JSON.stringify(before)===JSON.stringify(g._sequence);},shot),'checkpoint blocks local mutation');
   }
   let driftCounter;
   if(mode===7&&(i===2||i===4)){
    driftCounter=await b.evaluate(field=>{const g=window.__gameLogic;if(field==='scores')g.freePoolScores[0]++;else {const rank=g.table.balls.find(x=>!g.freePoolPocketed.includes(x.rank)).rank;g.freePoolPocketed.push(rank);}return window.contractResyncs;},i===2?'scores':'creditedRanks');
   }
   assert(await pages[turn].evaluate(shot=>window.__gameLogic.localMove(shot),shot));
   if(i===3)await b.evaluate(()=>SamiDevNetwork.requestResync());

   for(const page of pages)await page.waitForFunction(before=>window.__gameLogic.noAnimations>before&&!window.__gameLogic.animator.isAnimatingWorld()&&!window.__gameLogic.preshooting&&!window.__samidevGameState.network.snapshotBusy,before,{timeout:30000});
   if(driftCounter!==undefined){
    await b.waitForFunction(before=>window.contractResyncs>before,driftCounter,{timeout:15000});
    await b.waitForFunction(()=>!SamiDevNetwork.state.resyncInFlight&&!window.__samidevGameState.network.snapshotBusy&&!window.__gameLogic._awaitingResync&&!window.__gameLogic.paused,{},{timeout:30000});
    driftRecoveries.push(i===2?'scores':'creditedRanks');
   }
   // Allow native reveal/ready queues to finish; both clients must agree without a checkpoint per shot.
   await a.waitForFunction(()=>window.__gameLogic._localMoves.length===0,{},{timeout:15000});
   await b.waitForFunction(()=>window.__gameLogic._localMoves.length===0,{},{timeout:15000});
   const state=await Promise.all(pages.map(p=>p.evaluate(()=>{const g=window.__gameLogic;return {turn:[...g.turn],sequence:[...g._sequence],positions:g.getPositionsToValidate(),random:[...g.random.state],noAnimations:g.noAnimations,lastValidAnim:g.lastValidAnim,gameOver:g.gameOver,ballInHand:g.ballInHand,scores:[...g.freePoolScores],creditedRanks:[...g.freePoolPocketed].sort((a,b)=>a-b)};})));
   assert.deepEqual(state[0],state[1],`replica mismatch mode=${mode} shot=${i}`);
   if(i===5&&!state[0].gameOver){
    reconnectResyncs+=await b.evaluate(()=>window.contractResyncs);
    await b.reload();
    await b.waitForFunction(()=>window.SamiDevNetwork?.state.begun&&window.__gameLogic?.started&&!SamiDevNetwork.state.resyncInFlight&&!window.__samidevGameState.network.snapshotBusy,{},{timeout:30000});
    assert.equal(await b.evaluate(()=>SamiDevNetwork.state.roomId),rid,'reconnect retains room');
    await b.evaluate(()=>{window.contractResyncs=0;SamiDevNetwork.on('resync_state',()=>window.contractResyncs++);});
   }
   if(state[0].gameOver)break;
  }
  const resyncs=await Promise.all(pages.map(p=>p.evaluate(()=>window.contractResyncs)));
  resyncs[1]+=reconnectResyncs;
  assert(resyncs.reduce((a,b)=>a+b,0)<=(mode===7?7:5),'no forced full snapshot per shot');
  results.push({mode,resyncs,driftRecoveries});
  // Close the authoritative match before reusing these accounts. Leaving the
  // transport alone correctly keeps their active-match admission reservation.
  if(!await a.evaluate(()=>SamiDevGameUI.isGameOver()))assert((await a.evaluate(()=>SamiDevGameUI.resignMatch(5000))).ok);
  for(const page of pages)await page.evaluate(()=>SamiDevNetwork.leaveRoom({closeSocket:true}));
 }
 assert.deepEqual(errors,[]);console.log(JSON.stringify({ok:true,results}));
}catch(error){
 console.error('PAGE_ERRORS',errors);
 for(const page of pages)try{console.error('PAGE_STATE',await page.evaluate(()=>({url:location.href,text:document.body?.innerText.slice(0,600),bootstrap:!!window.SamiDevGameBootstrap,game:window.__SAMIDEV_GAME_ID,logic:!!window.__gameLogic})));}catch(_){}
 throw error;
}finally{await browser.close();}
