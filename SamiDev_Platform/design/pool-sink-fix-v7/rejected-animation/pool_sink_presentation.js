'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../game/pool-sink-presentation.js'),'utf8');
class Signal{constructor(){this.listeners=new Set()}receive(fn){this.listeners.add(fn)}ignore(fn){this.listeners.delete(fn)}emit(...args){for(const fn of this.listeners)fn(...args)}}
function load(){const window={};vm.runInNewContext(source,{window,performance:{now:()=>0}});return window.PlazrPoolSinkPresentation;}
function fixture({realBody=null,logic=null,theme=''}={}){
 let time=0,invalidations=0;
 const pocket={id:4,position:[21,758],getRadius:()=>60};
 const body=realBody||{position:[60,758],velocity:[-180,0],sinking:false,onSunk:new Signal(),isSinking(){return this.sinking},getSinkingPocket(){return this.sinking?pocket:undefined}};
 const calls=[],view={body,x:body.position[0],y:body.position[1],_width:40,_height:40,hiliteX:0,hiliteY:0,hiliteSize:46,get width(){return this._width},get height(){return this._height},getRadius:()=>20,getDiameter:()=>40,_render(ctx){const p=this.body.getSinkingPocket();calls.push({receiver:this,ctx,x:this.x-20+this.width/2,y:this.y-20+this.height/2,size:this.width,pocket:p,radius:p?.getRadius()});return 'native-render';}};
 const scene={logic:logic||{table:{balls:[]},onSynchronize:new Signal(),onAnimationCanceled:new Signal()},table:{width:866,height:1546,shadowDims:[16,15],getBall:rank=>rank===0?view:null}};
 const api=load().create({now:()=>time,getTheme:()=>theme,onInvalidate:()=>invalidations++});
 api.frame(scene);
 return {api,scene,body,view,calls,pocket,time:v=>time=v,invalidations:()=>invalidations};
}
let checks=0;
const f=fixture(),originalOwnWidth=Object.getOwnPropertyDescriptor(f.view,'width');
assert.equal(f.view._render('ctx'),'native-render');assert.equal(f.calls.at(-1).receiver,f.view);checks++;
f.body.sinking=true;f.body.onSunk.emit(f.body);f.time(0);f.view._render('ctx');
assert.notEqual(f.calls.at(-1).receiver,f.view);assert.equal(f.calls.at(-1).x,60);assert.equal(f.calls.at(-1).size,40);assert.equal(f.calls.at(-1).radius,26);assert.deepEqual(Array.from(f.calls.at(-1).pocket.position),[42.5,757.5]);checks++;
f.body.position[0]=90;f.body.velocity[0]=120;f.view.x=90;f.time(130);f.view._render('ctx');
assert(f.calls.at(-1).x<60,'presentation never follows the inward return');assert.equal(f.calls.at(-1).size,30);assert.equal(f.body.position[0],90);assert.equal(f.view.x,90);assert.equal(f.view.width,40);assert.deepEqual(Object.getOwnPropertyDescriptor(f.view,'width'),originalOwnWidth);checks++;
const callsBeforeHidden=f.calls.length;f.time(270);f.view._render('ctx');assert.equal(f.calls.length,callsBeforeHidden,'hidden after descending; cannot reappear while sensor completes');checks++;
f.body.sinking=false;f.api.frame(f.scene);f.body.position[0]=55;f.view.x=55;f.body.sinking=true;f.body.onSunk.emit(f.body);f.time(1000);f.view._render('ctx');assert.equal(f.calls.at(-1).size,40,'next shot restarts visible fall');assert.equal(f.calls.at(-1).x,55);checks++;
f.scene.logic.onSynchronize.emit();f.time(1100);f.view._render('ctx');assert.equal(f.calls.at(-1).size,40,'synchronization resets stale presentation');checks++;
f.api.dispose();assert.equal(f.body.onSunk.listeners.size,0);assert.equal(f.scene.logic.onSynchronize.listeners.size,0);assert.equal(f.scene.logic.onAnimationCanceled.listeners.size,0);assert.equal(f.view._render('original'),'native-render');assert.equal(f.calls.at(-1).receiver,f.view);checks++;
const emerald=fixture({theme:'pool_emerald'});emerald.body.sinking=true;emerald.body.onSunk.emit();emerald.view._render();assert.equal(emerald.calls.at(-1).radius,31);emerald.api.dispose();checks++;

// Feed the actual native sinking path through the presentation, including its reversal.
const {GameRuntimeFactory}=require('../gamehost/runtime');
const factory=new GameRuntimeFactory(path.join(__dirname,'../game/games/pool'),{gameId:'pool'}),room=factory.createRoom('SINK_PRESENTATION',{gameType:7,break:0,live:1,trickShots:0},2,()=>{}),g=room.logic;
let actual;
try{
 const move=m=>factory.processMove(room,0,{i:'sink-regression',n:g._sequence[0],m});assert(move({__ready:1}).accepted);g.ballInHand=0;
 const body=g.table.cueBall;body.position[0]=417;body.position[1]=758;body.aabbNeedsUpdate=true;body.wakeUp();
 actual=fixture({realBody:body,logic:g});let step=0;const pathTrace=[];
 g.world.on('postStep',()=>{
  step++;actual.time(step*g.getFixedTimeStep()*1000);actual.view.x=body.position[0];actual.view.y=body.position[1];actual.api.frame(actual.scene);
  if(body.isSinking()){
   const before=JSON.stringify({position:body.position,velocity:body.velocity,masks:body.shapes.map(s=>s.collisionMask)});
   actual.view._render('native-sink');
   assert.equal(JSON.stringify({position:body.position,velocity:body.velocity,masks:body.shapes.map(s=>s.collisionMask)}),before,'draw cannot mutate authoritative body');
   pathTrace.push({x:body.position[0],vx:body.velocity[0]});
  }
 });
 assert(move({a:1,st:.2,an:Math.PI,sp:[0,0]}).accepted);assert(pathTrace.some(p=>p.vx<0)&&pathTrace.some(p=>p.vx>0),'reproduces the reported native return');
 assert(actual.calls.length>4&&actual.calls.length<pathTrace.length,'native internal motion finishes while display stays hidden');
 for(let i=1;i<actual.calls.length;i++)assert(actual.calls[i].x<=actual.calls[i-1].x+1e-9,'visible descent cannot reverse toward cloth');
 assert.equal(g.ballInHand,5);assert.equal(g.turn[0],1);checks++;
 console.log(JSON.stringify({ok:true,checks,nativeSinkingSteps:pathTrace.length,visibleSinkingFrames:actual.calls.length,nativeReversalReproduced:true,displayNeverReturns:true,bodyUnchanged:true,scratchAndTurnUnchanged:true}));
}finally{actual?.api.dispose();factory.destroyRoom(room)}
