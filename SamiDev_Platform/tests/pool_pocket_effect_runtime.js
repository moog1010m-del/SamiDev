'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');let now=0,draws=0,invalidated=0,removed=0;const translated=[];
const context={setTransform(){},clearRect(){},save(){},restore(){},translate(x,y){translated.push([x,y]);},rotate(){},drawImage(){draws++;}};
const win={devicePixelRatio:1};class ImageMock{set src(v){this.complete=true;this.naturalWidth=2048;this.onload?.();}}
vm.runInNewContext(fs.readFileSync(require('node:path').join(__dirname,'../game/pool-pocket-effects.js'),'utf8'),{window:win,Image:ImageMock,performance:{now:()=>now},document:{createElement:()=>({style:{},setAttribute(){},getContext:()=>context,remove(){removed++;}}),body:{appendChild(){}}}});
function signal(){const handlers=[];return{receive:f=>handlers.push(f),emit:(...a)=>handlers.forEach(f=>f(...a))};}
const cosmetics={'0':{pool_pocket_effect:'pool_pocket_water'},'1':{pool_pocket_effect:'pool_pocket_default'}};
const g={turn:[0],currentShot:{seat:0},onPreShot:signal(),onBallSinkInPocket:signal(),sceneMgr:{layoutInfo:{logScale:.5},table:{scaleX:1,toWorldCoordinates:([x,y])=>[100+x*2,100+y*2]}}};
let sounds=0;
const effect=win.PlazrPocketEffects.create({canvas:{width:1200,getBoundingClientRect:()=>({left:20,top:30,width:600,height:400})},getCosmetics:()=>cosmetics,onInvalidate:()=>invalidated++,onSound:()=>sounds++});
effect.frame(g);g.onPreShot.emit();g.turn=[1];g.onBallSinkInPocket.emit({},10,20);now=180;
assert(effect.frame(g,{enabled:true,geometry:{scale:1},forward:p=>({x:p.x+10,y:p.y+20})},now));assert(draws>0);assert.deepEqual(translated[0],[130,160]);assert(invalidated>0);assert.equal(sounds,1);
now=1000;assert.equal(effect.frame(g,null,now),false);const previous=draws;
g.currentShot={seat:1};g.onPreShot.emit();g.onBallSinkInPocket.emit({},10,20);assert.equal(effect.frame(g,null,now),false);assert.equal(draws,previous);
assert.equal(sounds,1);effect.dispose();assert.equal(removed,1);assert.equal(effect.frame(g),false);
console.log(JSON.stringify({ok:true,ownerAtShotStart:true,desktopProjection:true,expiry:true,unequippedDoesNotPlay:true,cleanup:true}));
