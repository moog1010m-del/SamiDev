// Two real mobile browsers: queued aim/power must play the remote shot, not skip to its result.
import assert from 'node:assert/strict';
import fs from 'node:fs';
import {spawnSync} from 'node:child_process';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL||'http://127.0.0.1:8088';
assert(['127.0.0.1','localhost'].includes(new URL(base).hostname));assert(process.env.SAMIDEV_TEST_DATABASE_URL);
const out=process.env.SAMIDEV_TEST_ARTIFACTS||'/tmp/samidev-pool-shot';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const users=[],contexts=[],pages=[],errors=[];
try {
 for(let i=0;i<2;i++){
  const context=await browser.newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true,deviceScaleFactor:2});contexts.push(context);
  const r=await context.request.post(base+'/api/auth/register',{data:{username:'shot_'+Date.now().toString(36)+'_'+i,password:'Test-password-123',displayName:'لاعب '+(i+1)}});assert.equal(r.status(),200);users.push((await r.json()).user);
  const page=await context.newPage();pages.push(page);page.on('pageerror',e=>errors.push(e.message));page.on('console',msg=>{if(/live move sequence gap|live move rejected|world did not settle/.test(msg.text()))errors.push(msg.text());});
 }
 const host=pages[0],peer=pages[1];const intermediatePositions=[];
 await host.goto(base+'/games/pool/index.html?online=1&action=create&community=majlis&players=0&live=1');
 await host.waitForSelector('#sd-waiting.scene-ready',{timeout:30000});
 const room=await host.evaluate(()=>window.SamiDevNetwork.state.roomId);
 await peer.goto(base+'/games/pool/index.html?online=1&action=join&community=majlis&room='+room);
 for(const page of pages)await page.waitForFunction(()=>window.SamiDevNetwork.state.begun&&window.__gameLogic.started&&!window.__samidevGameState.network.snapshotBusy,{},{timeout:30000});
 await host.waitForFunction(()=>window.__gameLogic.canShoot(0),{},{timeout:15000});
 for(const page of pages)await page.evaluate(()=>{
   window.shotTrace={samples:[],events:[]};
   for(const type of ['move','resync_state','authority_state'])window.SamiDevNetwork.on(type,msg=>window.shotTrace.events.push({type,t:performance.now(),seat:msg.seat,packet:msg.packet,turn:msg.authority?.turn||msg.turn,seq:[...window.__gameLogic._sequence],queue:window.__gameLogic._queue.map(q=>({type:q.type,seat:q.data?.[0],packet:q.data?.[1]}))}));
   const sample=()=>{const g=window.__gameLogic;window.shotTrace.samples.push({t:performance.now(),p:Array.from(g.table.cueBall.position),renderFrames:window.__samidevGameState.performance.frames,anim:g.animator.isAnimatingWorld(),pre:g.preshooting,paused:g.paused,seq:[...g._sequence]});if(window.shotTrace.samples.length<1200)requestAnimationFrame(sample);};sample();
 });
 assert(await host.evaluate(()=>{const g=window.__gameLogic;for(const an of [.7,.9,1.1,1.3])g.localMove({a:3,an});g.localMove({a:4,st:.8});return g.localMove({a:1,st:.8,an:-Math.PI/2,sp:[0,0]});}));
 await peer.waitForFunction(()=>window.shotTrace.events.some(e=>e.type==='move'&&e.packet?.m?.a===1),{},{timeout:15000});
 try{await peer.waitForFunction(()=>window.shotTrace.samples.some(s=>s.anim),{},{timeout:15000});}catch(e){fs.writeFileSync(out+'/failed-trace.json',JSON.stringify(await peer.evaluate(()=>window.shotTrace)));throw e;}
 await peer.waitForFunction(()=>{const g=window.__gameLogic;return window.shotTrace.samples.some(s=>s.anim)&&!g.animator.isAnimatingWorld()&&!g.preshooting&&!window.__samidevGameState.network.snapshotBusy;},{},{timeout:30000});
 for(let i=0;i<pages.length;i++){const trace=await pages[i].evaluate(()=>window.shotTrace);fs.writeFileSync(out+'/pool-shot-'+i+'.json',JSON.stringify(trace));const positions=new Set(trace.samples.filter(s=>s.anim).map(s=>s.p.map(n=>n.toFixed(1)).join(',')));assert(positions.size>20,'player '+i+' sees intermediate positions');const frames=trace.samples.filter(s=>s.anim).map(s=>s.renderFrames);assert(Math.max(...frames)-Math.min(...frames)>20,'native scene renders throughout the shot');intermediatePositions.push(positions.size);}
 // Corrupt one replica while the socket stays OPEN and no new shot is sent.
 // The periodic public authority probe must restore the turn without refresh.
 const expectedTurn=await peer.evaluate(()=>[...window.__gameLogic.turn]);
 assert.equal(expectedTurn.length,1);
 await peer.evaluate(()=>{const g=window.__gameLogic;g.turn.splice(0,g.turn.length,1-g.turn[0]);});
 await peer.waitForFunction(expected=>{
   const g=window.__gameLogic,s=window.__samidevGameState;
   return JSON.stringify(g.turn)===JSON.stringify(expected)&&!s.network.snapshotBusy&&!g._awaitingResync;
 },expectedTurn,{timeout:15000});
 assert.deepEqual(errors,[]);console.log(JSON.stringify({ok:true,intermediatePositions,checks:["Aim and power burst reaches the opponent in order","Both players render intermediate ball positions","No sequence-gap resync skips the remote shot","A lost turn recovers by heartbeat without page refresh or a new move"],artifacts:out}));
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
