import assert from 'node:assert/strict';
const {chromium} = await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE || 'playwright-core');
const base = process.env.SAMIDEV_TEST_BASE_URL;
assert.equal(new URL(base).hostname, '127.0.0.1');
const browser = await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const pages=[], faults=[{},{}], errors=[], results=[];
const settled = page => page.waitForFunction(() => {
  const g=window.__gameLogic,n=window.SamiDevNetwork;
  return g?.started&&n?.state.begun&&!n.state.resyncInFlight&&!window.__samidevGameState.network.snapshotBusy&&!window.__samidevGameState.network.pendingAuthority&&!g._awaitingResync&&!g.paused&&!g.preshooting&&!g.animator.isAnimatingWorld()&&g._localMoves.length===0;
}, {}, {timeout:35000});
const state = page => page.evaluate(() => {const g=window.__gameLogic;return {turn:[...g.turn],sequence:[...g._sequence],balls:g.getPositionsToValidate(),scores:[...g.freePoolScores],ranks:[...g.freePoolPocketed].sort((a,b)=>a-b),random:[...g.random.state],animations:g.noAnimations};});
async function parity(label){for(const p of pages)await settled(p);assert.deepEqual(await state(pages[0]),await state(pages[1]),label);results.push(label);console.log(JSON.stringify({checkpoint:label}));}
async function shoot(){
  const seat=await pages[0].evaluate(()=>__gameLogic.turn[0]);
  await pages[seat].waitForFunction(()=>__gameLogic.canShoot(__gameLogic.localSeat),{},{timeout:15000});
  assert(await pages[seat].evaluate(()=>__gameLogic.localMove({a:1,st:.3,an:-Math.PI/2,sp:[.2,0]})));
}
try {
  for(let i=0;i<2;i++){
    const context=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true,extraHTTPHeaders:{Origin:base,'X-Forwarded-Proto':'https','X-Real-IP':`10.93.0.${i+1}`}});
    assert.equal((await context.request.post(base+'/api/auth/register',{data:{username:'recover_'+Date.now().toString(36)+'_'+i,password:'Test-password-123'}})).status(),200);
    const page=await context.newPage();pages.push(page);page.on('pageerror',e=>errors.push(e.message));
    await page.addInitScript(()=>{window.recoverySnapshots=0;window.recoveryAlarms=0;});
    // Faults affect transport only. Native sequence, animation and rule methods
    // remain untouched in both clients and the actual fixture GameHost.
    await page.routeWebSocket('**/ws*', socket => {
      const upstream=socket.connectToServer();
      socket.onMessage(raw=>{
        const msg=JSON.parse(String(raw));
        if(msg.type==='move'&&msg.packet?.m?.a===1&&faults[i].rejectShot){
          faults[i].rejectShot=false;
          socket.send(JSON.stringify({type:'error',code:'GAMELOGIC_EXCEPTION',message:'injected rolled-back host failure'}));
          return;
        }
        upstream.send(raw);
      });
      upstream.onMessage(raw=>{
        const msg=JSON.parse(String(raw));
        if(faults[i].loseTurnEvents&&['authority_alarm','authority_state'].includes(msg.type)){faults[i].lost=(faults[i].lost||0)+1;return;}
        if(faults[i].closeOnShot&&msg.type==='move'&&msg.packet?.m?.a===1){faults[i].closeOnShot=false;socket.close({code:1011,reason:'injected loss after server acceptance'});return;}
        socket.send(raw);
      });
    });
  }
  const [a,b]=pages;
  await a.goto(base+'/games/pool/index.html?online=1&action=create&community=majlis&gameType=7');
  await a.waitForFunction(()=>window.__samidevGameState?.network.waiting&&window.__samidevGameState.performance.frames>0,{},{timeout:30000});
  const rid=await a.evaluate(()=>SamiDevNetwork.state.roomId);
  await b.goto(base+'/games/pool/index.html?online=1&action=join&community=majlis&room='+rid);
  for(const p of pages){await settled(p);await p.evaluate(()=>{SamiDevNetwork.on('resync_state',()=>recoverySnapshots++);SamiDevNetwork.on('authority_alarm',()=>recoveryAlarms++);});}
  const before=await state(a),counter=await a.evaluate(()=>recoverySnapshots);
  faults[0].rejectShot=true;
  await shoot();
  await a.waitForFunction(n=>recoverySnapshots>n,counter,{timeout:2000});
  await parity('rolled-back shot requests immediate recovery');
  const recovered=await state(a);
  assert.deepEqual(recovered.balls,before.balls);assert.equal(recovered.animations,before.animations);
  await shoot();
  await a.waitForFunction(n=>__gameLogic.noAnimations>n,before.animations,{timeout:15000});
  await parity('retry remains playable');

  // Drop all turn broadcasts to one client, while heartbeat responses still
  // arrive. Recovery must work without a new user move or a manual refresh.
  const oldTurn=await a.evaluate(()=>__gameLogic.turn[0]);
  const oldSnapshots=await b.evaluate(()=>recoverySnapshots);
  faults[1].loseTurnEvents=true;
  const timeoutBudget=await a.evaluate(()=>{const g=__gameLogic;const remaining=Math.max(0,(g._localAlarmTime-SamiDev.hrtime())/1e6);return Math.ceil(remaining+(g.awaitingReady?g.turnDuration:0)+15000);});
  assert(Number.isFinite(timeoutBudget)&&timeoutBudget<=60000,'bounded native ready + turn deadline');
  await a.waitForFunction(turn=>__gameLogic.turn[0]!==turn,oldTurn,{timeout:timeoutBudget});
  await b.waitForFunction(n=>recoverySnapshots>n,oldSnapshots,{timeout:15000});
  assert(faults[1].lost>0);
  faults[1].loseTurnEvents=false;
  await parity('lost turn alarm recovers through heartbeat');

  const oldAnimations=await a.evaluate(()=>__gameLogic.noAnimations);
  faults[1].closeOnShot=true;
  const navigation=b.waitForEvent('framenavigated',{predicate:frame=>frame===b.mainFrame(),timeout:30000});
  await shoot();await navigation;
  await settled(b);
  assert.equal(await b.evaluate(()=>SamiDevNetwork.state.roomId),rid);
  await parity('disconnect after shot acceptance restores the committed shot');
  assert.equal(await a.evaluate(()=>__gameLogic.noAnimations),oldAnimations+1);
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({ok:true,results}));
} catch(error) {
  for(let i=0;i<pages.length;i++)console.error(JSON.stringify({client:i, fault:faults[i], state:await pages[i].evaluate(()=>{const g=window.__gameLogic,n=window.SamiDevNetwork;return g?{turn:g.turn,sequence:g._sequence,alarmId:g._nextAlarmId,pending:g._pendingAlarm,ready:g.awaitingReady,seconds:g.turnDuration/1000,localAlarmTime:g._localAlarmTime,now:performance.now()*1e6,paused:g.paused,animating:g.animator?.isAnimatingWorld(),preshooting:g.preshooting,snapshotBusy:window.__samidevGameState.network.snapshotBusy,requesting:n.state.resyncInFlight,localMoves:g._localMoves.length,snapshots:window.recoverySnapshots}:null;}).catch(()=>null)}));
  throw error;
} finally {await browser.close();}
