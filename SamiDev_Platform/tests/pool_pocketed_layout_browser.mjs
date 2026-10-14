// Native renderer regression: restore a real seven-pocketed-ball checkpoint,
// then exercise every legal live collection size from both players' views.
import fs from 'node:fs';
import assert from 'node:assert/strict';
import {spawn} from 'node:child_process';
import {fileURLToPath} from 'node:url';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const root=fileURLToPath(new URL('../game',import.meta.url));
const recorded=JSON.parse(fs.readFileSync(new URL('./fixtures/pool_seven_pocketed.json',import.meta.url),'utf8'));
const server=spawn(process.env.PYTHON||'python3',['-u','-c',`import sys
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
class Handler(SimpleHTTPRequestHandler):
 def __init__(self,*a,**kw): super().__init__(*a,directory=sys.argv[1],**kw)
 def log_message(self,*a): pass
server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
print(server.server_port,flush=True)
server.serve_forever()`,root],{stdio:['ignore','pipe','inherit']});
let browser;let cases=0;
try {
 const port=await new Promise((resolve,reject)=>{server.stdout.once('data',b=>resolve(Number(b.toString().trim())));server.once('error',reject);server.once('exit',c=>reject(Error('static fixture exited '+c)));});
 browser=await chromium.launch({executablePath:process.env.SAMIDEV_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
 for(const viewport of [{width:1024,height:757},{width:390,height:844}])for(const seat of [0,1]) {
  const page=await browser.newPage({viewport});const errors=[];
  page.on('pageerror',e=>errors.push(e.message));
  await page.goto(`http://127.0.0.1:${port}/games/pool/index.html?play=1&gameType=7&clean=1`);
  await page.waitForFunction(()=>window.__gameLogic?.sceneMgr&&window.__samidevGameState?.localHost.started,{},{timeout:30000});
  const initialPositions=await page.evaluate(()=>{
   const s=window.__samidevGameState,g=window.__gameLogic;
   // Isolate rendering from the offline host's own timers/hotseat automation.
   s.localHost.hotseat=false;for(const h of s.localHost.alarms.values())clearTimeout(h);
   s.localHost.alarms.clear();g.onSetAlarm=()=>{};
   return g.getPositionsToValidate();
  });
  const snapshots=[{label:'recorded incident',snapshot:recorded}];
  const ranks=[8,2,12,4,6,5,15,9,1,3,7,10,11,13,14];
  for(let count=0;count<=15;count++) {
   const snapshot=structuredClone(recorded);snapshot.d.p=structuredClone(initialPositions);
   snapshot.d.fpr=ranks.slice(0,count);snapshot.d.fps=[Math.ceil(count/2),Math.floor(count/2)];
   for(const rank of snapshot.d.fpr)snapshot.d.p[rank]=[-1000-rank*60,-1000];
   if(count===15){snapshot.g=1;snapshot.t=[];snapshot.p=0;snapshot.f=[[0],[1]];snapshot.d.gos={isGameOver:true,order:[[0],[1]]};snapshot.d.egs.ballPositions=structuredClone(snapshot.d.p);}
   snapshots.push({label:`collection ${count}`,snapshot});
  }
  for(const {label,snapshot} of snapshots) {
   const measured=await page.evaluate(({snapshot,seat})=>{
    const g=window.__gameLogic;g.deserialize(structuredClone(snapshot),seat);
    // Turn notification and layout resize are both paths that used to throw.
    g.onTurnChange.emit(g.turn);g.sceneMgr.updateLayout(g.sceneMgr.layoutInfo);
    const before=g.getPositionsToValidate();g.sceneMgr.table.reset(false);
    const active=g.sceneMgr.gapBalls.filter(v=>v.visible);
    return {before,after:g.getPositionsToValidate(),scores:[...g.freePoolScores],canShoot:g.canShoot(seat),
     balls:[g.table.cueBall,...g.table.balls].map(b=>{const v=g.sceneMgr.table.getBall(b.rank);return {body:[...b.position],visual:[v.x,v.y],sameBody:v.body===b,pocketed:b.isPocketed(),visible:v.visible};}),
     collected:active.map(v=>({rank:v.getRank(),x:v.x,y:v.y,width:v.width*v.scaleX,height:v.height*v.scaleY})),
     width:g.sceneMgr.layoutInfo.logW,height:g.sceneMgr.layoutInfo.logH,
     heading:g.sceneMgr.pocketed?{x:g.sceneMgr.pocketed.x,y:g.sceneMgr.pocketed.y}:null,
    };
   },{snapshot,seat});
   assert.deepEqual(measured.before,snapshot.d.p,label);
   assert.deepEqual(measured.after,snapshot.d.p,'visual reset preserves authoritative coordinates');
   assert.deepEqual(measured.scores,snapshot.d.fps);
   for(const b of measured.balls){assert(b.sameBody);assert.deepEqual(b.visual,b.body,'renderer follows restored body');if(b.pocketed)assert(!b.visible);}
   assert.deepEqual(measured.collected.map(v=>v.rank).sort((a,b)=>a-b),snapshot.g?[]:[...snapshot.d.fpr].sort((a,b)=>a-b),'all pocketed ranks, including eight, appear exactly once');
   for(const v of measured.collected){
    assert(Number.isFinite(v.x)&&Number.isFinite(v.y));
    assert(v.x-v.width/2>=0&&v.x+v.width/2<=measured.width);
    assert(v.y>measured.heading.y&&v.y+v.height/2<=measured.height);
    assert.equal(v.x>measured.width/2,seat===0,'collection stays on the active player side');
   }
   for(let i=0;i<measured.collected.length;i++)for(let j=i+1;j<measured.collected.length;j++){
    const a=measured.collected[i],b=measured.collected[j];
    assert(Math.abs(a.x-b.x)>=(a.width+b.width)/2||Math.abs(a.y-b.y)>=(a.height+b.height)/2,'collection items do not overlap');
   }
   if(!snapshot.g)assert.equal(measured.canShoot,seat===0,'snapshot recovery keeps the current player able to shoot');
   cases++;
   if((label==='recorded incident'||label==='collection 14')&&process.env.SAMIDEV_SCREENSHOT_DIR)await page.screenshot({path:`${process.env.SAMIDEV_SCREENSHOT_DIR}/${label==='recorded incident'?'incident-restored':'collection-14'}-${viewport.width}-seat${seat}.png`});
  }
  assert.deepEqual(errors,[]);await page.close();
 }
 console.log(JSON.stringify({ok:true,cases,viewports:2,seats:2,recordedCheckpoint:true,syntheticCollections:'0-14 live; 15 ended'}));
} finally {await browser?.close();server.kill('SIGTERM');}
