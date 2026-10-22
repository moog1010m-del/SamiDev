'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../game/browser-runtime.js'),'utf8');
const code=source.slice(source.indexOf('  const desktopPoolControls ='),source.indexOf('  const pendingPointerMoves ='));
let checks=0;
function fixture(stored=null,mobileDevice=false,touchDevice=false,finePointer=false){
 let now=0;const shots=[],angles=[],saved={};
 const meter={visible:true,setStrength(value){this.strength=value;}};
 const g={started:true,localSeat:0,turn:[0],sceneMgr:{layoutInfo:{logScale:1},table:{x:500,y:500,width:1000,height:1000,scaleX:1,scaleY:1,getCueBallWorldX:()=>500,getCueBallWorldY:()=>500},cueStick:{setRotation(a){angles.push(a);}},powerMeter:meter,onShoot:{emit(v){shots.push(v);}}},requestStickRotation(){},requestPowerChange(){}};
 const context={isPool:true,touchDevice,mobileDevice,state:{gameLogic:g},window:{addEventListener(){},matchMedia:()=>({matches:finePointer})},document:{querySelector:()=>null,hidden:false,addEventListener(){}},performance:{now:()=>now},localStorage:{getItem:()=>stored,setItem:(k,v)=>saved[k]=v},eventPoint:e=>({x:e.clientX,y:e.clientY})};
 vm.runInNewContext(code,context);return{api:context.window.SamiDevPoolControls,g,meter,shots,angles,saved,time:v=>now=v};
}
const ev={pointerType:'mouse',button:2,buttons:0,pointerId:7,clientX:700,clientY:600};
const f=fixture();assert.equal(f.api.mode,'hold');checks++;
f.api.tick(0);assert.equal(f.meter.visible,false);checks++;
assert(f.api.hover(ev));assert(Math.abs(f.angles.at(-1)-Math.atan2(100,200))<1e-9);checks++;
assert.equal(f.api.down({...ev,button:0}),false);checks++;
assert(f.api.down(ev));f.time(800);f.api.tick(800);assert.equal(f.api.hover(ev),false);assert(f.api.up(ev));assert.equal(f.shots.length,1);assert.equal(f.shots[0],.5);checks++;
f.api.down(ev);f.g.turn=[1];f.api.tick(900);f.api.up(ev);assert.equal(f.shots.length,1);checks++;
f.g.turn=[0];f.api.setMode('meter');assert.equal(f.meter.visible,true);assert.equal(f.saved.plazr_pool_control,'meter');assert.equal(f.api.hover(ev),false);checks++;
assert.equal(fixture('meter').api.mode,'meter');assert.equal(fixture(null,true).api,undefined);checks++;
assert.equal(fixture(null,false,true,false).api,undefined);assert(fixture(null,false,true,true).api);checks++;
const detection=source.slice(source.indexOf('  const touchDevice ='),source.indexOf('  const HOST_GLOBAL ='));
for(const [w,h,touch,expected] of [[1440,900,10,false],[768,1024,5,false],[390,844,5,true],[800,1280,0,false]]){
 const c={isPool:true,navigator:{maxTouchPoints:touch},window:{screen:{width:w,height:h},matchMedia:()=>({matches:!!touch})}};vm.runInNewContext(detection+'\nthis.result=mobileDevice;',c);assert.equal(c.result,expected);checks++;
}
console.log(JSON.stringify({ok:true,checks,freeHover:true,rightButtonOnly:true,cancelOnTurnChange:true,defaultAndSavedPreference:true,touchLaptopIsDesktop:true}));
