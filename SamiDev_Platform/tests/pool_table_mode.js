'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const window={};for(const name of ['samidev-games.js','pool-presentation.js','pool-table-mode.js'])vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../game',name),'utf8'),{window,location:{pathname:'/games/pool/'},URLSearchParams});
async function main(){
 let checks=0;
 const settings=q=>window.SamiDevGames.settings(new URLSearchParams(q),'pool');
 assert.equal(settings('').largeTable,0);assert.equal(settings('largeTable=1').largeTable,1);assert.equal(settings('largeTable=bogus').largeTable,0);checks++;
 const ordinary=window.PlazrPoolTableMode.create();await ordinary.ready;assert.equal(ordinary.large,false);assert.equal(ordinary.source('images/imported/themes/th_basic_table.webp'),'images/imported/themes/th_basic_table.webp');checks++;
 const choices=[],online=window.PlazrPoolTableMode.create({online:true,settings:{largeTable:1},presentation:{setLargeTable(v){choices.push(v)}}});let resolved=false;online.ready.then(()=>resolved=true);await Promise.resolve();assert.equal(resolved,false,'joining URL cannot choose artwork before room assignment');checks++;
 online.configure({largeTable:1});await online.ready;assert.equal(online.source('images/imported/themes/th_basic_table.webp'),'/images/pool-large/table.webp');assert.equal(online.source('/images/themes/pool-emerald.webp'),'/images/pool-large/emerald.webp');assert.equal(online.source('scene-avatars/player_indicator.png'),'scene-avatars/player_indicator.png');assert.deepEqual(choices,[true]);checks++;
 online.configure({largeTable:1});assert.throws(()=>online.configure({largeTable:0}),/الطاولة/,'room cannot change mode during asset load');checks++;
 const stale=window.PlazrPoolTableMode.create({online:true,settings:{largeTable:1}});stale.configure({});await stale.ready;assert.equal(stale.large,false,'old rooms and authoritative default ignore stale large-table URL');checks++;
 for(const device of [{mobileDevice:false},{mobileDevice:true},{mobileDevice:true,native:true}]){
  const canvas={width:1000,getBoundingClientRect:()=>({left:0,top:0,width:1000,height:1000})};
  const table={x:2000,y:1400,width:866,height:1546,scaleX:1,scaleY:1,render(){}};
  const scene={table,layoutInfo:{logW:4000,logH:2700,logScale:2,cbGapsPos:[]},logic:{freePool:false},bgnd:{createSprite(){},render(){},updateSprite(){}},updateLayout(){},updateCBGapsPos(){},updateGapBallsPos(){},updatePocketedPos(){}};
  const api=window.SamiDevPoolPresentation.create({canvas,...device});api.beforeFrame(scene);assert.equal(api.enabled,false,'original layout is the default on every device');
  api.setLargeTable(true);api.beforeFrame(scene);assert.equal(api.enabled,true,'explicit match option works on desktop, phone and app');const p={x:2100,y:1500},round=api.inverse(api.forward(p));assert(Math.abs(round.x-p.x)<1e-9&&Math.abs(round.y-p.y)<1e-9,'aim coordinates round-trip');assert(api.tableBounds().height>0);checks++;
  if(device.mobileDevice){scene.layoutInfo={...scene.layoutInfo,logW:2000,logH:4000};api.beforeFrame(scene);assert.equal(api.enabled,false,'portrait phone retains a usable tall table; large skin selection is independent');checks++;}
 }
 console.log(JSON.stringify({ok:true,checks,authoritativeModeBeforeAssets:true,originalDefault:true,largeWorksOnPhoneAndApp:true}));
}
main().catch(e=>{console.error(e);process.exit(1)});
