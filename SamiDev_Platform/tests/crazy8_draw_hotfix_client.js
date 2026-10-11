// Exercises real Crazy8 logic and card scene values with WebGL/audio mocks; no pixel or physical-device verification.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const game='crazy8',root=path.resolve(__dirname,'..','game'),dir=game==='carrom'?root:path.join(root,'games',game);
const warnings=[],errors=[],frames=[],timers=new Set(),resourceRequests=[],nativeUploads=[],contextRequests=[],syncRequests=[];let context;
const mobile=process.env.SD_MOBILE==='1',layoutOnly=process.env.SD_LAYOUT_ONLY==='1';
const [viewWidth,viewHeight]=(process.env.SD_VIEWPORT||'700x950').split('x').map(Number);
const capacity=Number(process.env.SD_SEATS)||2;
const nativeAvatars=new Set();
const requestedTheme=process.argv[4]||'carrom_classic', failCatAtlas=process.argv[5]==='fail-cat';
const requestedCue=process.env.SD_CUE||'pool_cue_classic';
const afk=process.env.SD_AFK==='1';const online=true;const clientSeat=Number(process.env.SD_CARD_SEAT||0);const teamMode=process.env.SD_CARD_TEAMS==='1';let factory,room,deliver,emit,lastMessage,resyncCount=0;
const noop=()=>{};
const gl=new Proxy({texImage2D:(...args)=>{const img=args.at(-1);if(typeof img?.src==='string')nativeUploads.push(img.src);},getParameter:()=>4096,getShaderParameter:()=>true,getProgramParameter:()=>true,getExtension:()=>null,getShaderInfoLog:()=>'',getProgramInfoLog:()=>''},{get:(o,k)=>k in o?o[k]:(/^[A-Z_0-9]+$/.test(k)?(o[k]=Object.keys(o).length):(...args)=>k.startsWith('create')?{}:0)});
const ctx2d=new Proxy({measureText:s=>({width:String(s).length*20})},{get:(o,k)=>o[k]||noop});
function elem(tag){const listeners=new Map();return {tag,listeners,style:{},classList:{add:noop,remove:noop,toggle:noop},dataset:{},appendChild(child){if(child.tag==='script'){try{let source=fs.readFileSync(path.join(dir,child.src.split('?')[0]),'utf8');source=source.replace(/(\.prototype.refresh=function\([a-z]\)\{)(var [a-z]=this\._imageRadius\*2)/,'$1globalThis.__avatarNodes.add(this);$2');source=source.replace('function re(i,e,t,r=!1){','function re(i,e,t,r=!1){globalThis.__cardHands=Zt;globalThis.__cardSceneState=()=>({active:Pi,queued:dd.length});');vm.runInContext(source,context,{filename:'main.js'});child.onload();}catch(e){child.onerror?.(e);throw e;}}return child;},append:noop,addEventListener:(type,fn)=>{if(!listeners.has(type))listeners.set(type,[]);listeners.get(type).push(fn);},setAttribute:noop,remove:noop,getContext:(type,options)=>{if(type!=='2d')contextRequests.push({type,options});return type==='2d'?ctx2d:gl;},getBoundingClientRect:()=>({x:0,y:0,left:0,top:0,width:viewWidth,height:viewHeight}),querySelector:()=>null,querySelectorAll:()=>[],width:viewWidth,height:viewHeight};}
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
 const settings=game==='pool'?{gameId:'pool',gameType:0,break:0,live:1,trickShots:0}:game==='crazy8'?{gameId:game,seats:teamMode?4:capacity===2?0:capacity===3?1:capacity===4?2:3,special:0,live:afk?1:0}:{gameId:game,players:capacity===4?1:0,live:0,goalsToWin:0,passes:0,gamemode:0,break:0};
 const handlers=new Map();emit=(name,x)=>{for(const fn of handlers.get(name)||[])fn(x);};
 let revision=0;
 room=factory.createRoom('VMTEST',settings,capacity,event=>{
  const view={...event,authorityEpoch:1,revision:++revision,reveal:event.revealBySeat?.[String(clientSeat)]};delete view.snapshot;delete view.revealBySeat;
  emit(event.type,view);
  if(event.gameOver && event.snapshot)emit('resync_state',{...view,type:'resync_state',snapshot:game==='crazy8'?event.snapshot._samidev_clientViews[String(clientSeat)]:event.snapshot,history:[]});
 });
 base.location.search='?online=1&action=join&room=VMTEST&clean=1';
 deliver=(seat,packet)=>{
  const official=structuredClone(packet),result=factory.processMove(room,seat,official);
  if(!result.accepted){errors.push('server rejected '+JSON.stringify(packet));return false;}
  lastMessage={seat,packet:official,reveal:result.revealBySeat?.[String(clientSeat)],authority:factory.describeRoom(room,false)};emit('move',lastMessage);return true;
 };
 base.SamiDevNetwork={state:{roomId:'VMTEST',seat:clientSeat,capacity,roster:[]},on:(name,fn)=>{if(!handlers.has(name))handlers.set(name,[]);handlers.get(name).push(fn);},
  connectFromLocation:async()=>({roomId:'VMTEST',settings,capacity,seat:clientSeat,cosmetics:{'0':{pool_theme:requestedTheme,pool_cue:requestedCue},'1':{pool_theme:'pool_midnight'}},roster:Array.from({length:capacity},(_,seat)=>({seat,name:'لاعب باسم طويل للتجربة '+seat})),history:[],...(game==='pool'?{snapshot:factory.describeRoom(room,true).snapshot}:game==='crazy8'?{snapshot:factory.describeRoom(room,true).snapshot._samidev_clientViews[String(clientSeat)]}: {})}),runtimeReady:()=>emit('begin_match',{}),
  sendMove:packet=>{base.setTimeout(()=>deliver(clientSeat,packet),180);return true;},
  requestResync:()=>{if(game==='pool'){resyncCount++;if(resyncCount<8)base.setTimeout(()=>emit('resync_state',{...factory.describeRoom(room,true),history:[]}),50);else errors.push('pool resync loop');}else warnings.push('resync requested');return true;}};
}
(async()=>{try{
 vm.runInContext(fs.readFileSync(path.join(root,'samidev-games.js'),'utf8'),context);
 const html=fs.readFileSync(path.join(dir,'index.html'),'utf8');
 for(const m of html.matchAll(/<script>([\s\S]*?)<\/script>/g))if(m[1].includes('__assetImages'))vm.runInContext(m[1],context);
 vm.runInContext(fs.readFileSync(path.join(root,'browser-runtime.js'),'utf8'),context,{filename:'browser-runtime.js'});
 await context.__startSamiDevGame();
 const pump=async(n)=>{for(let i=0;i<n;i++){for(const fn of frames.splice(0))fn();await new Promise(r=>setTimeout(r,16));}};
 const g=context.__gameLogic;await pump(160);let reveals=0;
 g.emitter.on('move',(type)=>{if(type==='revealDraw')reveals++;});
 const checkpoint=()=>emit('resync_state',{...factory.describeRoom(room,true),snapshot:factory.describeRoom(room,true).snapshot._samidev_clientViews[String(clientSeat)],history:[]});
 const fixture=async(crank=0,attack=0)=>{
  factory._activate(room);const server=room.logic;
  server.hands=Array.from({length:capacity},()=>[4,8]);
  const attacker=(clientSeat+capacity-1)%capacity;if(attack)server.hands[attacker]=[attack,4];
  server.discard=[28];server.stock=Array.from({length:40},(_,i)=>4+i);server.won=-1;server.dir=1;server.crank=crank;server.lastPlay=-1;
  server._turn=[attack?attacker:clientSeat];
  server.seatInactivity=Array(capacity).fill(false);server._sequence=Array(capacity).fill(0);
  checkpoint();await pump(70);return attacker;
 };
 const verify=()=>{
  for(let seat=0;seat<capacity;seat++){
   const visible=seat===clientSeat||teamMode&&seat%2===clientSeat%2;
   if(visible)assert.deepEqual(Array.from(g.hands[seat]).sort((a,b)=>a-b),Array.from(room.logic.hands[seat]).sort((a,b)=>a-b),'visible hand matches authority');
   else assert(g.hands[seat].every(c=>c===-1),'opponent hand stays private');
  }
  assert(g.stock.every(c=>c===-1),'stock stays private');
  assert.equal(g._localMoves.length,0,'matching echo acknowledged');
  assert.deepEqual(Array.from(g._sequence),Array.from(room.logic._sequence),'no duplicate local execution');
  const views=context.__cardHands;assert(views,'native scene hand views captured');
  for(let seat=0;seat<capacity;seat++){
   const visible=seat===clientSeat||teamMode&&seat%2===clientSeat%2;
   const values=Array.from(views[seat].childrenCards).map(card=>card.value);
   if(visible)assert.deepEqual(values.sort((a,b)=>a-b),Array.from(room.logic.hands[seat]).sort((a,b)=>a-b),'rendered card faces match actual hand '+JSON.stringify({seat,values,expected:Array.from(room.logic.hands[seat])}));
   else assert(values.every(c=>c===-1),'rendered opponent cards keep their backs');
  }
 };
 const settle=async()=>{for(let i=0;i<550;i++){await pump(1);const view=context.__cardSceneState?.();if(i>60&&!g.paused&&!g._localMoves.length&&!view?.active&&!view?.queued)break;}};
 const counts=[];
 for(const count of [1,2,4,8]){
  await fixture(count===1?0:count);const before=g.hands[clientSeat].length;
  assert(g.localMove({d:1}),'local draw accepted');
  assert(g.hands[clientSeat].includes(-1),'temporary private placeholders before delayed echo');
  await settle();verify();assert.equal(g.hands[clientSeat].length,before+count,'exact draw count');
  const previous=JSON.stringify(g.hands),revealCount=reveals;
  emit('move',structuredClone(lastMessage));await pump(3);
  assert.equal(JSON.stringify(g.hands),previous,'duplicate echo does not add cards');assert.equal(reveals,revealCount,'duplicate echo does not flip again');
  checkpoint();await pump(60);emit('move',structuredClone(lastMessage));await pump(3);verify();
  assert.equal(reveals,revealCount,'stale echo after snapshot does not reveal twice');counts.push(count);
 }
 for(const rank of [52,56]){
  const attacker=await fixture(0,rank);const before=g.hands[clientSeat].length;
  assert(deliver(attacker,{i:'automatic-'+rank,n:room.logic._sequence[attacker],m:{c:rank,...(rank===56?{o:0}:{})}}),'automatic draw attack accepted');
  await settle();verify();assert.equal(g.hands[clientSeat].length,before+(rank===52?2:4),'automatic penalty draw count');
 }
 assert.equal(errors.length,0,'browser errors: '+JSON.stringify(errors));
 console.log(JSON.stringify({ok:true,clientSeat,capacity,teamMode,drawCounts:counts,automaticDraw2And4:true,nativeCardFaces:true,opponentPrivacy:true,duplicateAndSnapshotEchoSafety:true}));
 }finally{for(const h of timers){clearTimeout(h);clearInterval(h);}if(room)factory.destroyRoom(room);}})().catch(e=>{console.log(e.stack.split('\n').filter(x=>x.length<1000).join('\n'));process.exitCode=1;});
