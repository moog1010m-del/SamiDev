// API compatibility smoke only: WebGL/audio are mocked, no visual assertion.
const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const game=process.argv[2]||'tablesoccer',root=path.resolve(__dirname,'..','game'),dir=game==='carrom'?root:path.join(root,'games',game);
const warnings=[],errors=[],frames=[],timers=new Set(),resourceRequests=[],nativeUploads=[],contextRequests=[],syncRequests=[];let context;
const mobile=process.env.SD_MOBILE==='1',layoutOnly=process.env.SD_LAYOUT_ONLY==='1';
const [viewWidth,viewHeight]=(process.env.SD_VIEWPORT||'700x950').split('x').map(Number);
const capacity=Number(process.env.SD_SEATS)||2;
const nativeAvatars=new Set();
const requestedTheme=process.argv[4]||'carrom_classic', failCatAtlas=process.argv[5]==='fail-cat';
const requestedCue=process.env.SD_CUE||'pool_cue_classic';
const afk=process.env.SD_AFK==='1';const online=process.argv[3]==='online';let factory,room,deliver,resyncCount=0;
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
 const handlers=new Map();const emit=(name,x)=>{for(const fn of handlers.get(name)||[])fn(x);};
 let revision=0;
 room=factory.createRoom('VMTEST',settings,capacity,event=>{
  const view={...event,authorityEpoch:1,revision:++revision,reveal:event.revealBySeat?.['0']};delete view.snapshot;delete view.revealBySeat;
  emit(event.type,view);
  if(event.gameOver && event.snapshot)emit('resync_state',{...view,type:'resync_state',snapshot:game==='crazy8'?event.snapshot._samidev_clientViews['0']:event.snapshot,history:[]});
 });
 base.location.search='?online=1&action=join&room=VMTEST&clean=1';
 deliver=(seat,packet)=>{
  const official=structuredClone(packet),result=factory.processMove(room,seat,official);
  if(!result.accepted){errors.push('server rejected '+JSON.stringify(packet));return false;}
  emit('move',{seat,packet:official,reveal:result.revealBySeat?.['0'],authority:factory.describeRoom(room,false)});return true;
 };
 base.SamiDevNetwork={state:{roomId:'VMTEST',seat:0,capacity,roster:[]},on:(name,fn)=>{if(!handlers.has(name))handlers.set(name,[]);handlers.get(name).push(fn);},
  connectFromLocation:async()=>({roomId:'VMTEST',settings,capacity,seat:0,cosmetics:{'0':{pool_theme:requestedTheme,pool_cue:requestedCue},'1':{pool_theme:'pool_midnight'}},roster:Array.from({length:capacity},(_,seat)=>({seat,name:'لاعب باسم طويل للتجربة '+seat})),history:[],...(game==='pool'?{snapshot:factory.describeRoom(room,true).snapshot}:game==='crazy8'?{snapshot:factory.describeRoom(room,true).snapshot._samidev_clientViews['0']}: {})}),runtimeReady:()=>emit('begin_match',{}),
  sendMove:packet=>{queueMicrotask(()=>deliver(0,packet));return true;},
  requestResync:()=>{if(game==='pool'){resyncCount++;if(resyncCount<8)base.setTimeout(()=>emit('resync_state',{...factory.describeRoom(room,true),history:[]}),50);else errors.push('pool resync loop');}else warnings.push('resync requested');return true;}};
}
(async()=>{try{
 vm.runInContext(fs.readFileSync(path.join(root,'samidev-games.js'),'utf8'),context);
 const html=fs.readFileSync(path.join(dir,'index.html'),'utf8');
 for(const m of html.matchAll(/<script>([\s\S]*?)<\/script>/g))if(m[1].includes('__assetImages'))vm.runInContext(m[1],context);
 if(game==='carrom')vm.runInContext(fs.readFileSync(path.join(root,'carrom-themes.js'),'utf8'),context,{filename:'carrom-themes.js'});
 vm.runInContext(fs.readFileSync(path.join(root,'browser-runtime.js'),'utf8'),context,{filename:'browser-runtime.js'});
 await context.__startSamiDevGame();
 for(let i=0;i<15;i++){const pending=frames.splice(0);for(const fn of pending)fn();await new Promise(r=>setTimeout(r,16));}
 if(game==='pool' && online && requestedCue==='pool_cue_moon'){
  assert.equal(context.SamiDevPoolCosmetics.cueForSeat(0),'pool_cue_moon');
  assert.equal(context.SamiDevPoolCosmetics.cueForSeat(1),'pool_cue_classic');
  assert.equal(context.__gameLogic.sceneMgr.cueStick.sku,900000003,'equipped moon cue reaches the rendered stick');
  assert(nativeUploads.includes('/images/cues/moon.webp'),'moon sprite uploaded into native rendering');
 }
 if(game==='crazy8' && online && !afk && !layoutOnly && !context.__previewError){
  const g=context.__gameLogic;
  const framesUntilSettled=async()=>{for(let i=0;i<150;i++){const pending=frames.splice(0);for(const fn of pending)fn();await new Promise(r=>setTimeout(r,16));if(i>30&&!g.paused&&!g._localMoves.length)break;}};
  await framesUntilSettled();
  for(let step=0;step<8&&!room.logic.gameOver;step++){
   const seat=room.logic.turn[0],card=room.logic.hands[seat].find(c=>room.logic.canPlayCard(seat,c));
   const m=step%2===0||card===undefined?{d:1}:{c:card,...([8,14,15,16].includes(card>>2)?{o:0}:{})};
   if(seat===0)assert(g.localMove(m),'local card move');
   else assert(deliver(seat,{i:'remote-'+step,n:room.logic._sequence[seat],m}));
   await framesUntilSettled();
   assert.deepEqual(Array.from(g.hands[0]).sort((a,b)=>a-b),Array.from(room.logic.hands[0]).sort((a,b)=>a-b),'own cards match the server after reveal');
   assert(g.hands[1].every(c=>c===-1),'opponent cards remain hidden');
   assert.deepEqual(Array.from(g._sequence),Array.from(room.logic._sequence),'client sequence matches server');
   assert.deepEqual(Array.from(g.turn),Array.from(room.logic.turn),'client turn matches server');
  }
 }
 if(game==='pool' && online && !afk && !layoutOnly && !context.__previewError){
  const g=context.__gameLogic;
  const pump=async(n)=>{for(let i=0;i<n;i++){const pending=frames.splice(0);for(const fn of pending)fn();await new Promise(r=>setTimeout(r,16));}};
  await pump(60);
  if(requestedTheme==='pool_emerald')assert.equal(g.activeTheme,900000002,'own table on own turn');

  assert(g.localMove({a:1,st:.01,an:0,sp:[0,0]}),'original native shot controls');
  await pump(650);

  assert.deepEqual(Array.from(g.turn),Array.from(room.logic.turn),'native pool turn matches authority');
  assert.equal(g.turn[0],1,'weak shot passes turn');
  assert.equal(g.activeTheme,0,'opponent default table on opponent turn');
  if(requestedCue==='pool_cue_moon')assert.equal(g.sceneMgr.cueStick.sku,0,'opponent classic cue on opponent turn');
  if(requestedTheme==='pool_emerald'){assert(deliver(1,{i:'remote-shot',n:room.logic._sequence[1],m:{a:1,st:.01,an:0,sp:[0,0]}}));await pump(300);assert.equal(g.turn[0],0);assert.equal(g.activeTheme,900000002,'own table restored next turn');if(requestedCue==='pool_cue_moon')assert.equal(g.sceneMgr.cueStick.sku,900000003,'moon cue restored on next own turn');}

  assert.deepEqual(Array.from(g._sequence),Array.from(room.logic._sequence),'native pool sequence matches authority');
  assert(Math.hypot(g.table.cueBall.position[0]-room.logic.table.cueBall.position[0],g.table.cueBall.position[1]-room.logic.table.cueBall.position[1])<.02,'authoritative final cue position');
  for(const uri of ['images/ui/ui.webp',requestedTheme==='pool_emerald'?'/images/themes/pool-emerald.webp':'images/imported/themes/th_basic_table.webp','images/imported/themes/th_basic_background.webp'])assert(nativeUploads.some(source=>source.split('?')[0]===uri),'texture uploaded '+uri);
 }
 if(game==='tablesoccer' && !layoutOnly && !context.__previewError){
  const h=context.__SamiDevWebHost;
  if(online){
    assert(context.__gameLogic.localMove({a:7,t:'Default'}));
    await new Promise(r=>setTimeout(r,50));
    assert(context.__gameLogic.localMove({a:5,team:'Red.c.h'}));
  }else assert(h.injectMove(0,{a:5,team:'Red.c.h'}));
  await new Promise(r=>setTimeout(r,100));
  if(online)assert(deliver(1,{i:'other-team',n:0,m:{a:5,team:'Blue.c.h'}}));
  else assert(h.injectMove(1,{a:5,team:'Blue.c.h'}));
  for(let i=0;i<190;i++){const pending=frames.splice(0);for(const fn of pending)fn();await new Promise(r=>setTimeout(r,16));}
  if(online){
    const g=context.__gameLogic;
    console.log('before-shot',g.turn,g.paused,room.logic.turn,JSON.stringify(g._sequence),JSON.stringify(room.logic._sequence),JSON.stringify(g._localMoves));
    assert(deliver(1,{i:'other-ready',n:1,m:{__ready:1}}));
    for(let i=0;i<120;i++){const pending=frames.splice(0);for(const fn of pending)fn();await new Promise(r=>setTimeout(r,16));}
    // Remote shot exercises the full browser physics animation and server acknowledgement.
    assert(deliver(0,{i:'skip',n:room.logic._sequence[0],m:{a:4}}));
    assert(deliver(1,{i:'test-shot',n:room.logic._sequence[1],m:{a:0,id:150,impulse:[100,0]}}));
    for(let i=0;i<280;i++){const pending=frames.splice(0);for(const fn of pending)fn();await new Promise(r=>setTimeout(r,16));}
    console.log('after-shot',g.turn,room.logic.turn,JSON.stringify(g._sequence),JSON.stringify(room.logic._sequence));
    assert.deepStrictEqual(Array.from(g.turn),Array.from(room.logic.turn));
    assert.deepStrictEqual(Array.from(g._sequence),Array.from(room.logic._sequence));
  }
 }
 if(afk && online){
  const g=context.__gameLogic;
  const pump=async(ms)=>{const end=performance.now()+ms;while(performance.now()<end){for(const fn of frames.splice(0))fn();await new Promise(r=>setTimeout(r,16));}};
  await pump(200);
  for(let i=0;i<15&&!room.logic.gameOver;i++){factory._scheduleAlarm(room,2,room.logic._nextAlarmId);await pump(game==='pool'?900:300);}
  await pump(1800);
  assert(room.logic.gameOver,'server AFK finish');assert(g.gameOver,'client learns AFK finish without input/reload');
  assert.deepEqual(Array.from(g._sequence),Array.from(room.logic._sequence),'final native sequence');
  assert.equal(context.__samidevGameState.network.finished,true,'terminal checkpoint applied');
  console.log('AFK_PASS '+game);
 }
 console.log(JSON.stringify({game,started:context.__samidevGameState.localHost.started,preview:context.__previewError,render:context.__renderError,turn:context.__gameLogic?.turn,flags:context.__gameLogic?.teamFlags,warnings,errors},null,2));
 assert(context.__samidevGameState.localHost.started&&!context.__previewError&&!context.__renderError,'browser bridge startup');
 if(game==='carrom'){const expected=failCatAtlas?'carrom_classic':requestedTheme;assert.equal(context.__samidevGameState.carromTheme,expected);const atlas=context.__samidevGameState.images.get('images/game.webp');assert(atlas&&atlas.src.includes(expected==='carrom_cat'?'cat-atlas.webp':'game.webp'),'selected atlas must be preloaded under the native texture key');assert.equal(atlas.naturalWidth,3116);assert.equal(atlas.naturalHeight,2128);assert(nativeUploads.includes(atlas.src),'selected carrom art uploaded by native renderer');assert(nativeUploads.some(uri=>uri.split('?')[0]==='images/table-background.webp'),'carrom background uploaded by native renderer');}
 if(game==='tablesoccer'&&!layoutOnly){
  for(const uri of ['images/main.webp','images/field-img-standard.png','images/bg-img-standard.png','images/default_home.png','images/default_away.png','images/ball-standard.png'])assert(nativeUploads.includes(uri),'native football texture uploaded: '+uri);
  assert(context.SamiDev.sceneManager?.background?.sprite,'native football background composed');
  assert(resourceRequests.every(uri=>!/^([a-z][a-z0-9+.-]*:)?\/\//i.test(uri)),'football resources are local');
  assert(!warnings.some(w=>w.includes('Missing preloaded texture')||w.includes('Invalid sprite')),'football sprites available');
 }
 if(game==='pool'){assert(resourceRequests.every(uri=>!/^([a-z][a-z0-9+.-]*:)?\/\//i.test(uri)),'pool resources stay local');assert(!warnings.some(w=>w.includes('Missing preloaded texture')||w.includes('Invalid sprite')),'original pool sprites complete');}
 if(game==='carrom'||game==='crazy8'){
  assert(resourceRequests.some(uri=>uri.split('?')[0]==='images/table-background.webp'),'game background loaded');
  assert(resourceRequests.every(uri=>!/^([a-z][a-z0-9+.-]*:)?\/\//i.test(uri)),'all game resources are local');
  assert(!warnings.some(w=>w.includes('Missing preloaded texture')||w.includes('Invalid sprite')),'required sprites available');
 }
 if(game==='crazy8'){
  assert(resourceRequests.includes('images/CardBackSheet.webp'),'generated card-back atlas loaded');
  assert(resourceRequests.every(uri=>!/^([a-z][a-z0-9+.-]*:)?\/\//i.test(uri)),'all runtime resource requests are local');
  assert(!warnings.some(w=>w.includes('Missing preloaded texture')||w.includes('Invalid sprite')),'all required sprites available');
 }

 assert.equal(syncRequests.length,0,'native resources preloaded without synchronous network requests: '+JSON.stringify(syncRequests));
 if(mobile){
  assert.equal(contextRequests[0].options.antialias,false);
  assert.equal(contextRequests[0].options.preserveDrawingBuffer,false);
  assert(canvas.width*canvas.height<1003000,'mobile backing buffer budget');
  assert(context.__samidevGameState.performance.pixelRatio<=1.5);
  const avatars=Array.from(nativeAvatars).filter(a=>a.parent&&a.seat>=0&&a.seat<capacity);
  assert(avatars.length>=capacity,'native players inspected');
  const ui=avatars.map(a=>({seat:a.seat,radius:a.imageRadius,fontSize:a.nameText.fontSize,name:a.nameText.text,maxNameWidth:a.maxNameWidth,x:a.x,y:a.y,parentWidth:a.parent?.width,parentHeight:a.parent?.height,ancestors:(()=>{let out=[],n=a;for(let i=0;n&&i<5;i++,n=n.parent)out.push({name:n.name,x:n.x,y:n.y,w:n.width,h:n.height,sx:n.scaleX,sy:n.scaleY,ax:n.anchorX,ay:n.anchorY});return out})()}));
  assert(ui.every(a=>a.fontSize>=40),'readable native player names');
  assert(ui.every(a=>a.radius>=50),'larger native avatars');
  // Exercise the real input bridge with a burst of touch samples and a release.
  const bridge=context.__samidevGameState,originalTouch=bridge.touch,originalMouse=bridge.mouse,calls=[],mouse=[];
  bridge.touch=e=>calls.push(e);bridge.mouse=e=>mouse.push(e);
  const fire=(type,x,y,extra={})=>{const e={pointerId:8,pointerType:'touch',clientX:x,clientY:y,buttons:type==='pointerup'?0:1,preventDefault:noop,...extra};for(const fn of canvas.listeners.get(type)||[])fn(e);};
  fire('pointerdown',20,30);
  for(let i=0;i<100;i++)fire('pointermove',20+i,30+i);
  assert.equal(calls.length,1,'move events wait for a frame or release');
  fire('pointerup',130,140);
  assert.deepEqual(calls.map(c=>c.action),[0,2,1],'latest queued move precedes release');
  assert.equal(calls[1].pointers[0].x,119*canvas.width/viewWidth);
  assert.equal(calls[1].pointers[0].y,canvas.height-129*canvas.height/viewHeight);
  assert.equal(mouse.length,0,'touch is not duplicated as a mouse gesture');
  assert.equal(bridge.activePointers.size,0);
  fire('pointerdown',20,30);fire('pointermove',40,50);fire('pointercancel',40,50);
  assert.equal(calls.at(-1).action,3,'touch cancellation retained');
  assert.equal(bridge.activePointers.size,0);
  bridge.touch=originalTouch;bridge.mouse=originalMouse;
  const nativeDraw=bridge.drawFrame;let drawCount=0;bridge.drawFrame=()=>drawCount++;
  const tickStart=performance.now()+100;for(let i=0;i<120;i++){bridge.frameRequested=true;const callbacks=frames.splice(0);for(const fn of callbacks)fn(tickStart+i*1000/120);}
  bridge.drawFrame=nativeDraw;assert(drawCount>=58&&drawCount<=61,'120 Hz input produces at most 60 native draws per second');
  console.log('MOBILE_UI '+JSON.stringify({viewport:[viewWidth,viewHeight],canvas:[canvas.width,canvas.height],players:ui}));
 }
 assert.equal(errors.length,0,'browser protocol errors');
 }finally{for(const h of timers){clearTimeout(h);clearInterval(h);}if(room)factory.destroyRoom(room);}
})().catch(e=>{console.log(e.stack.split('\n').filter(x=>x.length<1000).join('\n'));process.exitCode=1;});
