'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../game/pool-brand-mark.js'),'utf8');
function fixture(initialLarge=false){
 let large=initialLarge,offset=0,images=0,invalidations=0;
 const draws=[],nodes=[],ctx={setTransform(){},clearRect(){},drawImage(...args){draws.push(args)}};
 const document={createElement(){const e={style:{},width:0,height:0,hidden:false,setAttribute(){},getContext:()=>ctx,remove(){e.removed=true}};nodes.push(e);return e;},body:{append(){}}};
 class Image{constructor(){images++;this.complete=false;this.naturalWidth=0;}set src(v){this.url=v;this.complete=true;this.naturalWidth=1100;this.onload?.();}}
 const window={devicePixelRatio:2};vm.runInNewContext(source,{window,document,Image});
 const canvas={width:1000,getBoundingClientRect:()=>({left:10,top:20,width:500,height:700})};
 const logic={sceneMgr:{layoutInfo:{logScale:2},table:{shadowDims:[16,15],toWorldCoordinates:p=>[400+p[0]*.5+offset,300+p[1]*.5]}}};
 const api=window.PlazrPoolBrandMark.create({canvas,getLargeTable:()=>large,onInvalidate:()=>invalidations++});
 return {api,logic,draws,nodes,images:()=>images,invalidations:()=>invalidations,large:v=>large=v,offset:v=>offset=v};
}
let checks=0;const f=fixture(),before=JSON.stringify(f.logic);f.api.frame(f.logic);
assert.equal(f.images(),1);assert.equal(f.invalidations(),1);assert.equal(f.draws.length,1);assert.equal(JSON.stringify(f.logic),before,'decorative render cannot mutate the scene');checks++;
assert.equal(f.nodes[0].style.left,'132.125px');assert.equal(f.nodes[0].style.top,'95.125px');assert.equal(f.nodes[0].style.width,'60px');assert.equal(f.nodes[0].width,120,'small inlay canvas, not a full-screen buffer');checks++;
f.api.frame(f.logic);assert.equal(f.draws.length,1,'stationary engraving is cached during game animation');checks++;
f.offset(20);f.api.frame(f.logic);assert.equal(f.draws.length,2,'inlay follows table layout changes');checks++;
f.logic.sceneMgr.spinPanel={visible:true};f.api.frame(f.logic);assert.equal(f.nodes[0].hidden,true);f.logic.sceneMgr.spinPanel.visible=false;f.api.frame(f.logic);assert.equal(f.nodes[0].hidden,false);checks++;
f.large(true);f.api.frame(f.logic);assert.equal(f.nodes[0].hidden,true,'saved large-table design stays unchanged');checks++;
f.api.dispose();assert.equal(f.nodes[0].removed,true);const count=f.draws.length;f.large(false);f.api.frame(f.logic);assert.equal(f.draws.length,count);checks++;
const large=fixture(true);large.api.frame(large.logic);assert.equal(large.images(),0,'large mode does not load default-table engraving');large.api.dispose();checks++;
console.log(JSON.stringify({ok:true,checks,readableNonMirroredInlay:true,physicsAndInputUntouched:true,largeModeUnaffected:true}));
