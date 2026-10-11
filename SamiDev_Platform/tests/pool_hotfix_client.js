// API compatibility smoke only: WebGL/audio are mocked, no visual assertion.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const game='pool',root=path.resolve(__dirname,'..','game'),dir=game==='carrom'?root:path.join(root,'games',game);
const warnings=[],errors=[],frames=[],timers=new Set(),resourceRequests=[],nativeUploads=[],contextRequests=[],syncRequests=[];let context;
const mobile=process.env.SD_MOBILE==='1',layoutOnly=process.env.SD_LAYOUT_ONLY==='1';
const [viewWidth,viewHeight]=(process.env.SD_VIEWPORT||'700x950').split('x').map(Number);
const capacity=Number(process.env.SD_SEATS)||2;
const nativeAvatars=new Set();
const requestedTheme=process.argv[4]||'carrom_classic', failCatAtlas=process.argv[5]==='fail-cat';
const requestedCue=process.env.SD_CUE||'pool_cue_classic';
const afk=process.env.SD_AFK==='1';const online=true;const clientSeat=Number(process.env.SD_POOL_SEAT||0);const scenario=process.env.SD_POOL_SCENARIO||'all';let factory,room,deliver,emit,resyncCount=0;const sentPackets=[];
const noop=()=>{};
const gl=new Proxy({texImage2D:(...args)=>{const img=args.at(-1);if(typeof img?.src==='string')nativeUploads.push(img.src);},getParameter:()=>4096,getShaderParameter:()=>true,getProgramParameter:()=>true,getExtension:()=>null,getShaderInfoLog:()=>'',getProgramInfoLog:()=>''},{get:(o,k)=>k in o?o[k]:(/^[A-Z_0-9]+$/.test(k)?(o[k]=Object.keys(o).length):(...args)=>k.startsWith('create')?{}:0)});
const ctx2d=new Proxy({measureText:s=>({width:String(s).length*20})},{get:(o,k)=>o[k]||noop});
function elem(tag){const listeners=new Map();return {tag,listeners,style:{},classList:{add:noop,remove:noop,toggle:noop},dataset:{},appendChild(child){if(child.tag==='script'){try{let source=fs.readFileSync(path.join(dir,child.src.split('?')[0]),'utf8');source=source.replace(/(\.prototype.refresh=function\([a-z]\)\{)(var [a-z]=this\._imageRadius\*2)/,'$1globalThis.__avatarNodes.add(this);$2');vm.runInContext(source,context,{filename:'main.js'});child.onload();}catch(e){child.onerror?.(e);throw e;}}return child;},append:noop,addEventListener:(type,fn)=>{if(!listeners.has(type))listeners.set(type,[]);listeners.get(type).push(fn);},setAttribute:noop,remove:noop,getContext:(type,options)=>{if(type!=='2d')contextRequests.push({type,options});return type==='2d'?ctx2d:gl;},getBoundingClientRect:()=>({x:0,y:0,left:0,top:0,width:viewWidth,height:viewHeight}),querySelector:()=>null,querySelectorAll:()=>[],width:viewWidth,height:viewHeight};}
const canvas=elem('canvas'),status=elem('div');
const storage={getItem:()=>null,setItem:noop,removeItem:noop};
const doc={getElementById:id=>id==='game'?canvas:id==='status'?status:null,createElement:elem,body:elem('body'),head:elem('head'),addEventListener:noop,querySelector:()=>null,querySelectorAll:()=>[],documentElement:elem('html'),fonts:{ready:Promise.resolve()}};
function imageSize(file){
 const b=fs.readFileSync(file);
 if(b.subarray(1,4).toString()==='PNG')return [b.readUInt32BE(16),b.readUInt32BE(20)];
 if(b.toString('ascii',0,4)==='RIFF'&&b.toString('ascii',8,12)==='WEBP'){
  for(let offset=12;offset+8<b.length;){const type=b.toString('ascii',offset,offset+4),size=b.readUInt32LE(offset+4),data=offset+8;
   if(type==='VP8X')return [b.readUIntLE(data+4,3)+1,b.readUIntLE(data+7,3)+1];
   if(type==='VP8L'){const bits=b.readUInt32LE(data+1);return [(bits&0x3fff)+1,((bits>>>14)&0x3fff)+1];}
   if(type==='VP8 ')return [b.readUInt16LE(data+6)&0x3fff,b.readUInt16LE(data+8)&0x3fff];
   offset=data+size+(size%2);
  }
 }
 throw new Error('Unsupported image header: '+file);
}
class Image{constructor(){this.width=this.naturalWidth=0;this.height=this.naturalHeight=0;}set src(s){resourceRequests.push(s);this._src=s;queueMicrotask(()=>{const file=path.join(s.startsWith('/')?root:dir,s.split('?')[0]);if(fs.existsSync(file)&&!(failCatAtlas&&s.includes('cat-atlas'))){const [w,h]=imageSize(file);this.width=this.naturalWidth=w;this.height=this.naturalHeight=h;this.onload?.();}else this.onerror?.();});}get src(){return this._src;}}
class Audio{constructor(uri){if(uri)resourceRequests.push(uri);}play(){return Promise.resolve();}pause(){}addEventListener(){}load(){}}
class XHR{open(method,url){resourceRequests.push(url);this.url=url;syncRequests.push(url);}send(){try{this.responseText=fs.readFileSync(path.join(dir,this.url),'utf8');this.status=200;}catch{this.status=404;this.responseText='{}';}}}
const base={document:doc,Image,Audio,XMLHttpRequest:XHR,URLSearchParams,URL,AbortController,TextEncoder,TextDecoder,structuredClone,performance,queueMicrotask,location:{pathname:game==='carrom'?'/index.html':`/games/${game}/index.html`,search:'?play=1&live=0&clean=1',href:'http://local/'},localStorage:storage,sessionStorage:storage,navigator:{maxTouchPoints:mobile?5:0},devicePixelRatio:mobile?3:1,innerWidth:viewWidth,innerHeight:viewHeight,__avatarNodes:nativeAvatars,addEventListener:noop,requestAnimationFrame:fn=>{frames.push(fn);return frames.length;},cancelAnimationFrame:noop,console:{info:()=>{},log:noop,debug:noop,warn:(...a)=>warnings.push(a.map(x=>x?.stack||String(x)).join(' ')),error:(...a)=>errors.push(a.map(x=>x?.stack||String(x)).join(' '))},setTimeout:(fn,ms)=>{const h=setTimeout(()=>{timers.delete(h);try{fn();}catch(e){errors.push(e.stack);}},ms);timers.add(h);return h;},clearTimeout:h=>{clearTimeout(h);timers.delete(h);},setInterval:(fn,ms)=>{const h=setInterval(()=>{try{fn();}catch(e){errors.push(e.stack);}},ms);timers.add(h);return h;},clearInterval:h=>{clearInterval(h);timers.delete(h);}};
base.fetch=async url=>{if(url==='/api/store')return {ok:true,json:async()=>({equipped:{carrom_theme:requestedTheme,pool_theme:requestedTheme},catalog:[{id:requestedTheme,slot:'carrom_theme',owned:true}]})};const file=path.join(dir,url);if(url.startsWith('/api/')||!fs.existsSync(file))return {ok:false};const text=fs.readFileSync(file,'utf8');return {ok:true,json:async()=>JSON.parse(text),text:async()=>text};};
base.window=base;base.globalThis=base;context=vm.createContext(base);
if(online){
 const {GameRuntimeFactory}=require(path.join(root,'..','gamehost','runtime'));
 factory=new GameRuntimeFactory(dir,{gameId:game});
 if(game==='pool'&&!afk){const schedule=factory._scheduleAlarm;factory._scheduleAlarm=function(r,ms,id){return schedule.call(this,r,ms>1000?60000:ms,id);};}
 const settings=game==='pool'?{gameId:'pool',gameType:0,break:0,live:1,trickShots:0}:game==='crazy8'?{gameId:game,seats:capacity===2?0:capacity===3?1:capacity===4?2:3,special:0,live:afk?1:0}:{gameId:game,players:capacity===4?1:0,live:0,goalsToWin:0,passes:0,gamemode:0,break:0};
 const handlers=new Map();emit=(name,x)=>{for(const fn of handlers.get(name)||[])fn(x);};
 let revision=0;
 room=factory.createRoom('VMTEST',settings,capacity,event=>{
  const view={...event,authorityEpoch:1,revision:++revision,reveal:event.revealBySeat?.[String(clientSeat<0?0:clientSeat)]};delete view.snapshot;delete view.revealBySeat;
  emit(event.type,view);
  if(event.gameOver && event.snapshot)emit('resync_state',{...view,type:'resync_state',snapshot:game==='crazy8'?event.snapshot._samidev_clientViews['0']:event.snapshot,history:[]});
 });
 base.location.search='?online=1&action=join&room=VMTEST&clean=1';
 deliver=(seat,packet)=>{
  const official=structuredClone(packet),result=factory.processMove(room,seat,official);
  if(!result.accepted){errors.push('server rejected '+JSON.stringify(packet));return false;}
  emit('move',{seat,packet:official,reveal:result.revealBySeat?.[String(clientSeat<0?0:clientSeat)],authority:factory.describeRoom(room,false)});return true;
 };
 base.SamiDevNetwork={state:{roomId:'VMTEST',seat:clientSeat,capacity,roster:[]},on:(name,fn)=>{if(!handlers.has(name))handlers.set(name,[]);handlers.get(name).push(fn);},
  connectFromLocation:async()=>({roomId:'VMTEST',settings,capacity,seat:clientSeat,spectator:clientSeat<0,cosmetics:{'0':{pool_theme:requestedTheme,pool_cue:requestedCue},'1':{pool_theme:'pool_midnight'}},roster:Array.from({length:capacity},(_,seat)=>({seat,name:'لاعب باسم طويل للتجربة '+seat})),history:[],...(game==='pool'?{snapshot:factory.describeRoom(room,true).snapshot}:game==='crazy8'?{snapshot:factory.describeRoom(room,true).snapshot._samidev_clientViews['0']}: {})}),runtimeReady:()=>emit('begin_match',{}),
  sendMove:packet=>{sentPackets.push(structuredClone(packet));queueMicrotask(()=>deliver(clientSeat,packet));return true;},
  requestResync:()=>{if(game==='pool'){resyncCount++;if(resyncCount<8)base.setTimeout(()=>emit('resync_state',{...factory.describeRoom(room,true),history:[]}),50);else errors.push('pool resync loop');}else warnings.push('resync requested');return true;}};
}
(async()=>{try{
 vm.runInContext(fs.readFileSync(path.join(root,'samidev-games.js'),'utf8'),context);
 const html=fs.readFileSync(path.join(dir,'index.html'),'utf8');
 for(const m of html.matchAll(/<script>([\s\S]*?)<\/script>/g))if(m[1].includes('__assetImages'))vm.runInContext(m[1],context);
 vm.runInContext(fs.readFileSync(path.join(root,'browser-runtime.js'),'utf8'),context,{filename:'browser-runtime.js'});
 await context.__startSamiDevGame();
 const pump=async(n)=>{for(let i=0;i<n;i++){for(const fn of frames.splice(0))fn();await new Promise(r=>setTimeout(r,16));}};
 const g=context.__gameLogic;await pump(60);
 if(room.logic.awaitingReady)assert(deliver(0,{i:'remote-ready',n:room.logic._sequence[0],m:{__ready:1}}));
 await pump(40);
 let placements=0;
 if(clientSeat===0&&scenario!=='animation'){
  const cue=g.sceneMgr.table.cueBall;
  for(const raw of [[412,1000],[-250,1400],[2000,1200],[412,1700],[97,1419],[737,1419],[430,1250]]){
   cue.drag('begin',[412,1200]);cue.drag('apply',raw);cue.drag('end',raw);
   await pump(40);
   assert.equal(errors.length,0,'native drag must send a valid placement: '+raw);
   const packet=sentPackets.filter(p=>p.m?.a===2).at(-1);
   assert(packet,'drag emitted a native placement packet');
   assert(packet.m.ps[1]>=1119&&packet.m.ps[0]>=97&&packet.m.ps[0]<=737,'packet uses clamped table coordinates');
   assert(Math.hypot(g.table.cueBall.position[0]-room.logic.table.cueBall.position[0],g.table.cueBall.position[1]-room.logic.table.cueBall.position[1])<.02,'both peers use the same final cue position');
   assert.equal(g._localMoves.length,0,'placement echo acknowledges optimistic move');placements++;
  }
 }
 if(scenario!=='placement'){
  let completed=0;g.onPreAnimationFinished.receive(()=>completed++);
  const before=Array.from(g.table.cueBall.position);
  const shot={a:1,st:.8,an:-Math.PI/2,sp:[0,0]};
  if(clientSeat===0)assert(g.localMove(shot));else{
   assert(deliver(0,{i:'remote-preview',n:room.logic._sequence[0],m:{a:3,an:.7}}));
   assert(deliver(0,{i:'remote-break',n:room.logic._sequence[0],m:shot}));
  }
  await pump(1);
  const checkpoint=()=>emit('resync_state',{...factory.describeRoom(room,true),history:[]});
  assert(g.preshooting||g.animator.isAnimatingWorld()||g._queue.some(item=>item.data?.[1]?.m?.a===1),'native cue/physics animation started or queued behind aim');
  checkpoint();await pump(1);
  assert(g.preshooting||g.animator.isAnimatingWorld()||g._queue.some(item=>item.data?.[1]?.m?.a===1),'early checkpoint must preserve the cue/physics animation');
  for(let i=0;i<120&&!g.animator.isAnimatingWorld();i++)await pump(1);
  assert(g.animator.isAnimatingWorld(),'balls enter actual physics animation');
  const samples=new Set();const sample=()=>samples.add(Array.from(g.table.cueBall.position).map(n=>n.toFixed(2)).join(','));
  for(let i=0;i<20;i++){sample();await pump(1);}
  const middle=Array.from(g.table.cueBall.position);assert(Math.hypot(middle[0]-before[0],middle[1]-before[1])>1,'cue visibly travels before settling');
  checkpoint();checkpoint();
  assert(g.animator.isAnimatingWorld(),'repeated checkpoints must not teleport moving balls');
  // A move that arrives while the snapshot waits must survive queue draining.
  const nextSeat=room.logic.turn[0];
  assert(deliver(nextSeat,{i:'next-aim',n:room.logic._sequence[nextSeat],m:{a:3,an:0}}));
  for(let i=0;i<1400;i++){
   sample();await pump(1);
   const state=context.__SamiDevWebHost.state.network;
   if(completed>0&&!state.snapshotBusy&&!state.queuedSnapshot&&!g.animator.isAnimatingWorld()&&!g.preshooting&&!g._localMoves.length&&JSON.stringify(g._sequence)===JSON.stringify(room.logic._sequence))break;
  }
  assert(completed>0,'shot must finish through its native animation signal');
  assert(samples.size>=20,'shot includes intermediate ball positions');
  assert.deepEqual(Array.from(g.turn),Array.from(room.logic.turn),'final turn matches authority');
  assert.deepEqual(Array.from(g._sequence),Array.from(room.logic._sequence),'deferred move and snapshot sequences match');
  for(const [index,ball] of [g.table.cueBall,...g.table.balls].entries()){
   const other=[room.logic.table.cueBall,...room.logic.table.balls][index];
   assert(Math.hypot(ball.position[0]-other.position[0],ball.position[1]-other.position[1])<.025,'authoritative final ball '+index);
  }
  assert.equal(g._localMoves.length,0,'shot echo does not remain unacknowledged');
  console.log(JSON.stringify({ok:true,seat:clientSeat,placements,intermediatePositions:samples.size,completed,checkpointsDuringCueAndPhysics:true}));
 }else console.log(JSON.stringify({ok:true,seat:clientSeat,placements}));
 assert.equal(errors.length,0,'browser protocol errors: '+JSON.stringify(errors));
 assert(!warnings.some(w=>/live move rejected|world did not settle|sequence gap/.test(w)),'no rejected movement or animation timeout');
 }finally{for(const h of timers){clearTimeout(h);clearInterval(h);}if(room)factory.destroyRoom(room);}})().catch(e=>{console.log(e.stack.split('\n').filter(x=>x.length<1000).join('\n'));process.exitCode=1;});
