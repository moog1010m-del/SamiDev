// Desktop rendering and real pointer input preserve native pool coordinates.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const root=fileURLToPath(new URL('../game',import.meta.url));

const server=spawn(process.env.PYTHON||'python3',['-u','-c',`import sys
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw): super().__init__(*a,directory=sys.argv[1],**kw)
 def log_message(self,*a): pass
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
print(server.server_port,flush=True)
server.serve_forever()`,root],{stdio:['ignore','pipe','inherit']});
let browser;
try {
 const port=await new Promise((resolve,reject)=>{server.stdout.once('data',b=>resolve(Number(b.toString().trim())));server.once('error',reject);server.once('exit',c=>reject(Error('static fixture exited '+c)));});
 browser=await chromium.launch({executablePath:process.env.SAMIDEV_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 for(const viewport of [{width:1366,height:900},{width:1024,height:768},{width:390,height:844}]){
 const page=await browser.newPage({viewport,hasTouch:viewport.width<600});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(`http://127.0.0.1:${port}/games/pool/index.html?play=1&gameType=0&clean=1`);
 await page.waitForFunction(()=>window.__gameLogic?.sceneMgr&&window.__samidevGameState?.localHost.started,{},{timeout:30000});
 const context=await page.evaluate(()=>document.querySelector('canvas').getContext('webgl').getContextAttributes());assert.equal(context.antialias,viewport.width>=900);assert.equal(context.stencil,true,'pocket clipping stencil remains available');
 await page.waitForTimeout(300);
 const setup=await page.evaluate(()=>{const g=window.__gameLogic,s=window.__samidevGameState;for(const h of s.localHost.alarms.values())clearTimeout(h);s.localHost.alarms.clear();g.onSetAlarm=()=>{};s.localHost.hotseat=false;const original=g.getPositionsToValidate();window.__testScreen=(point)=>{const a=window.__samidevPoolPresentation,c=document.querySelector('canvas'),r=c.getBoundingClientRect(),l=g.sceneMgr.layoutInfo,p=a.forward({x:point[0],y:point[1]});return {x:r.left+p.x/l.logScale*r.width/c.width,y:r.top+p.y/l.logScale*r.height/c.height};};const p=g.table.cueBall.position;return {original,enabled:window.__samidevPoolPresentation.enabled,from:window.__testScreen(g.sceneMgr.table.toWorldCoordinates(p)),to:window.__testScreen(g.sceneMgr.table.toWorldCoordinates([p[0]+45,p[1]])),before:[...p]};});
 assert.equal(setup.enabled,viewport.width>=900);if(viewport.width<600)assert(await page.evaluate(()=>window.__gameLogic.sceneMgr.table.render.toString().includes('this._preRender')),'phone renderer is not wrapped');
 await page.mouse.move(setup.from.x,setup.from.y);await page.mouse.down();await page.mouse.move(setup.to.x,setup.to.y,{steps:12});await page.mouse.up();await page.waitForTimeout(250);
 const after=await page.evaluate(()=>({pos:[...window.__gameLogic.table.cueBall.position],moves:window.__samidevGameState.localHost.moves}));
 assert(Math.abs(after.pos[0]-setup.before[0]-45)<3,'drag X matches physical intent');assert(Math.abs(after.pos[1]-setup.before[1])<3,'drag Y unchanged');
 const aim=await page.evaluate(()=>{const t=window.__gameLogic.sceneMgr.table;return {from:window.__testScreen(t.toWorldCoordinates([300,700])),to:window.__testScreen(t.toWorldCoordinates([350,700]))};});
 await page.mouse.move(aim.from.x,aim.from.y);await page.mouse.down();await page.mouse.move(aim.to.x,aim.to.y,{steps:8});await page.mouse.up();
 const trace=await page.evaluate(()=>window.__samidevGameState.localHost.moves);assert(trace.some(m=>(m.m||m).a===3),'real pointer aim reaches engine');
 const geometry=await page.evaluate(()=>{const a=window.__samidevPoolPresentation,g=window.__gameLogic;for(const p of [{x:0,y:0},{x:500,y:900},{x:1800,y:1500}]){const q=a.inverse(a.forward(p));if(Math.hypot(q.x-p.x,q.y-p.y)>1e-6)throw Error('round trip mismatch');}return {geometry:a.geometry,positions:g.getPositionsToValidate()};});
 assert.deepEqual(geometry.positions.slice(1),setup.original.slice(1),'no other body moved during UI transforms');
 await fs.promises.mkdir('/workspace/artifacts/plazr/pool-landscape',{recursive:true});await page.screenshot({path:`/workspace/artifacts/plazr/pool-landscape/${viewport.width}.png`});
 // A resize toggles only presentation, including after a real placement and aim.
 const beforeResize=await page.evaluate(()=>window.__gameLogic.getPositionsToValidate());
 if(viewport.width>=900){await page.setViewportSize({width:600,height:900});await page.waitForFunction(()=>!window.__samidevPoolPresentation.enabled);await page.setViewportSize(viewport);await page.waitForFunction(()=>window.__samidevPoolPresentation.enabled);const afterResize=await page.evaluate(()=>window.__gameLogic.getPositionsToValidate());assert.deepEqual(afterResize,beforeResize,'resize preserves authoritative positions');}
 if(viewport.width===1366){
  await page.evaluate(()=>window.SamiDevPoolControls.setMode('hold'));
  await page.mouse.move(aim.from.x,aim.from.y);await page.mouse.down();await page.waitForTimeout(900);
  const rising=await page.evaluate(()=>window.__gameLogic.sceneMgr.powerMeter.getStrength());
  if(!rising)console.log(await page.evaluate(()=>{const g=window.__gameLogic,s=g.sceneMgr;return {mode:window.SamiDevPoolControls.mode,started:g.started,paused:g.paused,turn:g.turn,seat:g.localSeat,sequence:g._sequence,moves:window.__samidevGameState.localHost.moves.slice(-5),width:s.table.width,height:s.table.height,scale:s.table.scaleX,center:[s.table.x,s.table.y],spin:s.spinPanel.visible,settings:s.settingsWidget.visible,shop:s.shopWidget.visible};}));
  assert(rising>.25&&rising<.95,'holding charges through native power meter: '+rising);
  await page.waitForTimeout(1600);
  const falling=await page.evaluate(()=>window.__gameLogic.sceneMgr.powerMeter.getStrength());
  assert(falling<.7,'charge descends after maximum: '+falling);
  await page.evaluate(()=>window.dispatchEvent(new Event('blur')));await page.mouse.up();
  assert(!await page.evaluate(()=>window.__samidevGameState.localHost.moves.some(p=>(p.m||p).a===1)),'blur cancels without firing');
  await page.mouse.down();await page.waitForTimeout(750);await page.mouse.up();
 }else{
 const meter=await page.evaluate(()=>{const s=window.__gameLogic.sceneMgr,m=s.powerMeter,c=document.querySelector('canvas'),r=c.getBoundingClientRect(),factor=s.layoutInfo.logScale;const point=(x,y)=>({x:r.left+x/factor*r.width/c.width,y:r.top+y/factor*r.height/c.height});return {from:point(m.worldTransform[2]+m.width*.5,m.worldTransform[5]+m.height*.2),to:point(m.worldTransform[2]+m.width*.5,m.worldTransform[5]+m.height*.65)};});
 await page.mouse.move(meter.from.x,meter.from.y);await page.mouse.down();await page.mouse.move(meter.to.x,meter.to.y,{steps:12});await page.mouse.up();
 }
 await page.waitForFunction(()=>window.__samidevGameState.localHost.moves.some(p=>(p.m||p).a===1),{},{timeout:5000});
 await page.waitForFunction(()=>window.__gameLogic.animator.isAnimatingWorld()||window.__gameLogic.preshooting,{},{timeout:5000});
 await page.waitForFunction(()=>!window.__gameLogic.animator.isAnimatingWorld()&&!window.__gameLogic.preshooting,{},{timeout:30000});assert.deepEqual(errors,[]);
 console.log(JSON.stringify({viewport,landscape:setup.enabled,drag:true,aim:true,powerShot:true,holdCycleAndCancel:viewport.width===1366,resizePreservesPhysics:true,physicsUnchanged:true}));await page.close();
 }
}finally{await browser?.close();server.kill();}
