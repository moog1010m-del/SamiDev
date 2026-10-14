'use strict';
const assert=require('node:assert/strict'),path=require('node:path');
const {GameRuntimeFactory}=require('../gamehost/runtime');
const f=new GameRuntimeFactory(path.join(__dirname,'../game/games/pool'),{gameId:'pool'});
let checks=0;
const check=(value,message)=>{assert(value,message);checks++;};
function room(mode){const r=f.createRoom('M'+mode,{gameType:mode,live:1,break:0,trickShots:0},[2,4,4,2,4,4,3,2][mode],()=>{});f.processMove(r,0,{i:'ready',n:r.logic._sequence[0],m:{__ready:1}});return r;}
const move=(r,seat,m)=>f.processMove(r,seat,{i:'mode-'+checks,n:r.logic._sequence[seat],m});
for(let mode=0;mode<=7;mode++){
 const r=room(mode),g=r.logic;
 try{
  check(g.seats===[2,4,4,2,4,4,3,2][mode],'mode seat capacity');
  check(g.table.balls.length===(mode>=3&&mode<=5?9:15),'mode rack size');
  check(g.freePool===(mode===7),'only Game Pool uses casual rules');
  check(!move(r,1,{a:1,st:.8,an:-Math.PI/2,sp:[0,0]}).accepted,'wrong player cannot shoot');
  check(move(r,0,{a:1,st:.8,an:-Math.PI/2,sp:[0,0]}).accepted,'real physics break works for mode');
 }finally{f.destroyRoom(r);}
}
for(const [rank,prior] of [[8,0],[8,7],[15,7],[1,7]]){
 const r=room(7),g=r.logic;
 try{
  g.ballInHand=0;
  const previous=g.table.balls.filter(b=>b.rank!==rank).slice(0,prior);
  for(const ball of previous)ball.setPocketed();
  g.freePoolScores[0]=prior;g.freePoolPocketed=previous.map(b=>b.rank);
  const target=g.table.balls[rank-1];target.position[0]=125;target.position[1]=125;target.aabbNeedsUpdate=true;target.wakeUp();
  g.table.cueBall.position[0]=200;g.table.cueBall.position[1]=200;g.table.cueBall.aabbNeedsUpdate=true;g.updateTurnShootingFor();
  const packet={i:'finish-'+rank+'-'+prior,n:g._sequence[0],m:{a:1,st:.2,an:-Math.PI*.75,sp:[0,0]}};
  const result=f.processMove(r,0,structuredClone(packet));check(result.accepted,'legal object-ball shot');
  check(target.isPocketed(),'physics sinks target');check(g.freePoolScores[0]===prior+1,'one numbered ball counts once');
  check(g.gameOver===(prior===7),'only eighth point wins');
  const extra=result.revealBySeat['0'].data[String(g.noAnimations)].e;
  check(JSON.stringify(extra.freePoolScores)===JSON.stringify(g.freePoolScores),'native reveal carries server scores');
  check(JSON.stringify(extra.freePoolPocketed)===JSON.stringify([...g.freePoolPocketed].sort((a,b)=>a-b)),'native reveal carries credited ranks');
  if(prior===7)check(g.finishOrder[0][0]===0,'shooter wins regardless of ball group or black');
  else check(g.freePoolScores[1]===0,'opponent score unaffected');
  const scores=JSON.stringify(g.freePoolScores);check(!f.processMove(r,0,packet).accepted,'replayed shot rejected');check(JSON.stringify(g.freePoolScores)===scores,'replay never duplicates score');
  const snap=f.describeRoom(r,true).snapshot,copy=room(7);
  try{f.deserialize(copy,snap);check(copy.logic.freePool,'snapshot preserves custom mode');check(JSON.stringify(copy.logic.freePoolScores)===scores,'snapshot preserves scores');check(JSON.stringify(copy.logic.freePoolPocketed)===JSON.stringify(g.freePoolPocketed),'snapshot preserves credited ranks');}finally{f.destroyRoom(copy);}
 }finally{f.destroyRoom(r);}
}
const scratch=room(7);
try{
 const g=scratch.logic;g.ballInHand=0;g.table.cueBall.position[0]=120;g.table.cueBall.position[1]=120;g.table.cueBall.aabbNeedsUpdate=true;
 check(move(scratch,0,{a:1,st:.2,an:-Math.PI*.75,sp:[0,0]}).accepted,'scratch shot accepted');
 check(g.freePoolScores.every(score=>score===0),'cue ball never counts');check(g.turn[0]===1&&g.ballInHand===5,'scratch passes turn with ball in hand');
 check(!move(scratch,1,{a:1,st:.5,an:0,sp:[0,0],scores:[8,0]}).accepted,'player cannot submit scores');
}finally{f.destroyRoom(scratch);}
console.log(JSON.stringify({ok:true,checks,modes:8,physicalPocketCases:4,snapshotAndReplay:true}));
