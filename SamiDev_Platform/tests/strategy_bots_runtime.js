'use strict';
const assert=require('node:assert/strict');const path=require('node:path');
const {GameRuntimeFactory}=require('../gamehost/runtime');const {decide}=require('../../experiments/pool-bots/native_planner.cjs');
let checks=0;
for(const gameId of ['crazy8','carrom']){
 const f=new GameRuntimeFactory(path.resolve(__dirname,gameId==='carrom'?'../game':'../game/games/crazy8'),{gameId});
 const r=f.createRoom('STRATEGY',{gameId,players:0,seats:0,live:0,special:0,gamemode:0,break:0},2,()=>{});
 try{
  for(let step=0;step<(gameId==='crazy8'?250:8)&&!r.logic.gameOver;step++){
   const seat=r.logic.turn[0]??0,full=f.describeRoom(r,true).snapshot;
   const snapshot=gameId==='crazy8'?full._samidev_clientViews[String(seat)]:full;
   const chosen=decide({gameId,snapshot,seat,skill:'medium'});
   assert(chosen.move,gameId+' planner must choose');
   const result=f.processMove(r,seat,{i:'strategy-'+step,n:r.logic._sequence[seat],m:chosen.move});
   assert(result.accepted,gameId+' legal strategy move '+JSON.stringify(chosen.move));checks++;
  }
  if(gameId==='crazy8')assert(r.logic.gameOver,'UNO strategy completes a real match');
 }finally{f.destroyRoom(r);}
}
console.log(JSON.stringify({ok:true,checks}));
