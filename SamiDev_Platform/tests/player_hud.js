const assert=require('node:assert/strict');require('../design/avatar-layout-v36.js');
const hud=globalThis.SamiDevAvatarLayout,state=globalThis.SamiDevAvatarHUDState;
const avatars=[0,1,2].map((seat)=>({x:200+seat*300,y:100,_imageRadius:50,nameMargin:10,nameText:{fontSize:30},scaleX:1}));
function ball(rank){return{getRank:()=>rank,visible:true,width:40,height:40,position(x,y){this.x=x;this.y=y;}}}
let balls=[ball(1),ball(9)];const logic={seats:2,turn:[0],getSolids:()=>0,is8BallGame:()=>true,is9BallGame:()=>false,isCutthroatGame:()=>false,isPlayerPlayingSolids:s=>s===0};
const scene={logic,avatars:{get:s=>avatars[s]},gapBalls:balls};hud.poolBalls(scene);assert.equal(balls[0].x,200);assert.equal(balls[1].x,500);assert(balls[0].y>150);
logic.seats=3;logic.is8BallGame=()=>false;logic.isCutthroatGame=()=>true;logic.getCutthroatGroupBySeat=s=>[s*5+1,s*5+2,s*5+3,s*5+4,s*5+5];scene.gapBalls=[ball(1),ball(6),ball(11)];hud.poolBalls(scene);scene.gapBalls.forEach((b,i)=>assert.equal(b.x,avatars[i].x));
const arcs=[];const ctx={setTransform(){},clearRect(){},beginPath(){},arc(...args){arcs.push(args)},stroke(){}};global.document={createElement:()=>({style:{},setAttribute(){},getContext:()=>ctx}),body:{appendChild(){}}};
const transformed=hud.point({x:20,y:10,parent:{x:100,y:50,scaleX:.5,scaleY:.5}},0,0);assert.deepEqual(transformed,{x:110,y:55});
const parent={visible:true};const timer={time:30000,countdown:15000,timer:1,parent,visible:true};hud.trackTimer(timer);state.avatars.add({_turn:true,parent,x:200,y:100,worldTransform:[1,0,999,0,1,999],_imageRadius:50});
assert(hud.frame({width:1000,height:500,getBoundingClientRect:()=>({left:0,top:0,width:1000,height:500})},100));assert.equal(timer.alpha,0);assert.equal(timer.countdown,15000);assert.equal(arcs.length,2);assert.deepEqual(arcs[0].slice(0,3),[200,100,54]);assert(Math.abs(arcs[1][4]-Math.PI/2)<1e-6);
timer.timer=0;assert.equal(hud.frame({width:1000,height:500,getBoundingClientRect:()=>({left:0,top:0,width:1000,height:500})},200),false);
let badge;ctx.roundRect=(x,y,w,h)=>{badge={x,y,w,h}};ctx.fill=()=>{};ctx.fillText=()=>{};
state.avatars.clear();state.avatars.add({_plazrTurnBadge:true,parent,x:400,y:100,scaleX:1,scaleY:1,idContainer:{x:0,y:60,anchorX:.5,anchorY:0,width:100,height:40},nameText:{x:0,width:100},nameTextMeasure:{width:60}});
hud.frame({width:1000,height:500,getBoundingClientRect:()=>({left:0,top:0,width:1000,height:500})},300,{layoutInfo:{logScale:2}});assert.equal(badge.x,232);assert.equal(badge.w,37);
console.log('PLAYER_HUD_PASS: eight-ball ownership; three players; below-name positions; native countdown unchanged; ring projection; stopped timer');
