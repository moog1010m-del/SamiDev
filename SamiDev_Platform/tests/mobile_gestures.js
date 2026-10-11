const fs=require('fs'),path=require('path'),vm=require('vm'),assert=require('assert');
const handlers=new Map(),canvasHandlers=new Map();
const listen=(map,type,fn)=>{if(!map.has(type))map.set(type,[]);map.get(type).push(fn);};
const canvas={addEventListener:(type,fn,options)=>{assert.equal(options.passive,false);listen(canvasHandlers,type,fn);}};
const doc={getElementById:()=>canvas,addEventListener:(type,fn)=>listen(handlers,type,fn)};
let now=0;
vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../game/game-touch.js'),'utf8'),{document:doc,performance:{now:()=>now}});
const plain={closest:()=>null},input={closest:()=>({})};
const fire=(map,type,target,extra={})=>{let prevented=false;const event={target,cancelable:true,preventDefault:()=>{prevented=true;},...extra};for(const fn of map.get(type)||[])fn(event);return prevented;};
for(const type of ['touchstart','touchmove','touchend','gesturestart','gesturechange','gestureend'])assert(fire(canvasHandlers,type,canvas),type);
for(const type of ['dblclick','selectstart','contextmenu','dragstart']){assert(fire(handlers,type,plain),type);assert(!fire(handlers,type,input),'editing remains available: '+type);}
const touch={changedTouches:[{clientX:40,clientY:70}]};
assert(!fire(handlers,'touchend',plain,touch));now=120;assert(fire(handlers,'touchend',plain,touch),'double tap default blocked');
now=600;assert(!fire(handlers,'touchend',plain,touch),'ordinary later tap retained');
now=700;assert(!fire(handlers,'touchend',input,touch),'input touch retained');
now=750;assert(!fire(handlers,'touchend',plain,touch),'input resets tap history');
assert(!fire(handlers,'touchend',plain,{changedTouches:[]}));
console.log(JSON.stringify({ok:true,canvasGesturesBlocked:true,selectionAndCalloutBlocked:true,editableControlsRetained:true,doubleTapBlocked:true}));
