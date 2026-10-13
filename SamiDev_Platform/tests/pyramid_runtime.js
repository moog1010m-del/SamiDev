'use strict';
const assert=require('node:assert/strict'),path=require('node:path');
const {GameRuntimeFactory}=require('../gamehost/runtime');
const f=new GameRuntimeFactory(path.join(__dirname,'../game/games/pool'),{gameId:'pool'});
let checks=0;const check=(v,m)=>{assert(v,m);checks++;};
function create(mode){const r=f.createRoom('P'+mode,{gameType:mode,live:1,break:0,trickShots:0},2,()=>{});f.processMove(r,0,{i:'ready',n:r.logic._sequence[0],m:{__ready:1}});return r;}
function move(r,seat,m){return f.processMove(r,seat,{i:'py-'+checks,n:r.logic._sequence[seat],m});}
function arrange(g,offset=0){g.ballInHand=0;for(let i=0;i<15;i++){const b=g.table.balls[i];b.position[0]=680;b.position[1]=250+i*75;b.aabbNeedsUpdate=true;}const b=g.table.balls[0];b.position[0]=125;b.position[1]=125+offset;b.aabbNeedsUpdate=true;g.table.cueBall.position[0]=200;g.table.cueBall.position[1]=200+offset;g.table.cueBall.aabbNeedsUpdate=true;g.updateTurnShootingFor();return b;}
for(const mode of [8,9]){
 const r=create(mode),g=r.logic;
 try{
  check(g.pyramid.mode===mode&&g.table.rails.length===18,'isolated Pyramid geometry');
  const before=g.table.balls.map(b=>Array.from(b.position)),cue=Array.from(g.table.cueBall.position);
  check(!move(r,1,{a:9,rank:1}).accepted,'opponent cannot choose cue');
  for(const rank of [-1,0,16,1.5])check(!move(r,0,{a:9,rank}).accepted,'invalid cue choice rejected');
  check(!move(r,0,{a:9,rank:1,winner:0}).accepted,'no extra cue fields');
  check(move(r,0,{a:9,rank:1}).accepted,'first cue choice');
  check(g.pyramid.ids[0]===1&&g.pyramid.ids[1]===0,'identity swaps without changing visual ball positions');
  assert.deepEqual(Array.from(g.table.cueBall.position),before[0]);checks++;
  assert.deepEqual(Array.from(g.table.balls[0].position),cue);checks++;
  check(!move(r,0,{a:9,rank:2}).accepted,'second cue choice forbidden');
  const snapshot=f.describeRoom(r,true).snapshot,copy=create(mode);
  try{f.deserialize(copy,snapshot);assert.deepEqual(JSON.parse(JSON.stringify(copy.logic.pyramid)),JSON.parse(JSON.stringify(g.pyramid)));checks++;check(!move(copy,0,{a:9,rank:2}).accepted,'reconnect never resets used quota');}finally{f.destroyRoom(copy);}
  check(move(r,0,{a:1,st:.4,an:-Math.PI/2,sp:[0,0]}).accepted,'selected cue participates in real physics');
  check(g.pyramid.canSelect,'new shot opportunity restores choice');
 }finally{f.destroyRoom(r);}
}
for(const mode of [8,9])for(const prior of [0,7]){
 const r=create(mode),g=r.logic;
 try{
  const target=arrange(g);g.pyramid.scores[0]=prior;g.pyramid.credited=Array.from({length:prior},(_,i)=>i+2);
  check(move(r,0,{a:1,st:.2,an:-Math.PI*.75,sp:[0,0]}).accepted,'straight object pocket attempt');
  check(g.pyramid.scores[0]===prior+(mode===8?1:0),'only Free Pyramid awards object ball');
  check(target.isPocketed()===(mode===8),'Scratch object returns to table');
  check(g.gameOver===(mode===8&&prior===7),'Free eighth object wins');
  if(g.gameOver)check(g.finishOrder[0][0]===0,'correct Free winner');
 }finally{f.destroyRoom(r);}
}
for(const mode of [8,9])for(const prior of [0,7]){
 const r=create(mode),g=r.logic;
 try{
  arrange(g);g.table.balls[0].position[0]=180;g.table.balls[0].position[1]=180;g.table.balls[0].aabbNeedsUpdate=true;
  g.table.cueBall.position[0]=125;g.table.cueBall.position[1]=125;g.table.cueBall.aabbNeedsUpdate=true;
  g.pyramid.scores[0]=prior;g.pyramid.credited=Array.from({length:prior},(_,i)=>i+2);
  check(move(r,0,{a:1,st:.3,an:Math.PI/4,sp:[0,-1]}).accepted,'physical draw shot scratches after object contact');
  check(g.pyramid.scores[0]===prior+1,'legal cue scratch awards point');check(g.gameOver===(prior===7),'eighth legal cue wins');
  if(prior===0){check(!g.table.cueBall.isPocketed(),'new active cue automatically promoted');check(g.pyramid.ids[0]!==0&&g.pyramid.credited.includes(0),'pocketed identity stays removed');}
 }finally{f.destroyRoom(r);}
}
for(const mode of [8,9]){
 const r=create(mode),g=r.logic;
 try{arrange(g);g.table.cueBall.position[0]=125;g.table.cueBall.position[1]=125;g.table.cueBall.aabbNeedsUpdate=true;g.table.balls[0].position[0]=680;g.table.balls[0].position[1]=200;g.table.balls[0].aabbNeedsUpdate=true;
  check(move(r,0,{a:1,st:.2,an:-Math.PI*.75,sp:[0,0]}).accepted,'no-contact scratch simulation');
  check(g.pyramid.scores[0]===0&&!g.table.cueBall.isPocketed(),'scratch without contact never scores and returns');check(g.turn[0]===1,'foul transfers turn');
 }finally{f.destroyRoom(r);}
}
const p=create(7),py=create(8);
try{const a=arrange(p.logic,10),b=arrange(py.logic,10);move(p,0,{a:1,st:.2,an:-Math.PI*.75,sp:[0,0]});move(py,0,{a:1,st:.2,an:-Math.PI*.75,sp:[0,0]});check(a.isPocketed()&&!b.isPocketed(),'Pyramid mouth rejects imprecise shot accepted by normal pool');check(p.logic.table.rails.length===6,'normal geometry unchanged');}finally{f.destroyRoom(p);f.destroyRoom(py);}
console.log(JSON.stringify({ok:true,checks,realPhysics:true,selectionQuota:true,scratchContactAndWins:true,tightMouths:true}));
