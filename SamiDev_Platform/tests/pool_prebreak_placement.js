'use strict';
// Regression: moving the cue ball within the kitchen before the first break
// must be accepted and propagated to both players, without weakening rules.
const assert=require('node:assert/strict');
const path=require('node:path');
const {GameRuntimeFactory}=require('../gamehost/runtime');
const factory=new GameRuntimeFactory(path.join(__dirname,'../game/games/pool'),{gameId:'pool',expectedSha256:require('../game/samidev-integrity.json').games.pool.sha256});
const room=factory.createRoom('PREBREAK',{gameType:0,break:0,live:1,trickShots:0},2,()=>{});
let checks=0;
const verify=(ok,message)=>{assert.ok(ok,message);checks++;};
const send=(seat,m)=>factory.processMove(room,seat,{i:'prebreak-'+checks,n:room.logic._sequence[seat],m});
try{
 const g=room.logic;
 verify(g.isBreaking()&&g.canMoveCueBall(0),'breaker can reposition before first shot');
 for(const [x,y] of [[412,1200],[360,1240],[465,1320]]){
   const result=send(0,{a:2,ps:[x,y]});
   verify(result.accepted,`valid kitchen position ${x},${y}`);
   verify(Math.abs(g.table.cueBall.position[0]-x)<.01&&Math.abs(g.table.cueBall.position[1]-y)<.01,'authoritative cue position updated');
   for(const seat of ['0','1'])verify(result.revealBySeat[seat]?.pool?.balls?.[0]?.[1]===x&&result.revealBySeat[seat]?.pool?.balls?.[0]?.[2]===y,`seat ${seat} receives position`);
 }
 // A delayed or replayed placement must never overwrite the latest cue position.
 const lastPosition=[...g.table.cueBall.position];
 const stalePacket={i:'prebreak-stale',n:Math.max(0,g._sequence[0]-1),m:{a:2,ps:[410,1210]}};
 const staleResult=factory.processMove(room,0,stalePacket);
 verify(!staleResult.accepted,'stale placement sequence rejected');
 verify(g.table.cueBall.position[0]===lastPosition[0]&&g.table.cueBall.position[1]===lastPosition[1],'stale placement does not move cue');
 verify(!send(1,{a:2,ps:[412,1200]}).accepted,'opponent cannot move cue');
 verify(!send(0,{a:2,ps:[412,1000]}).accepted,'cannot place beyond kitchen before break');
 verify(!send(0,{a:2,ps:[-1,1200]}).accepted,'cannot place off table');
 verify(send(0,{a:1,st:.8,an:-Math.PI/2,sp:[0,0]}).accepted,'break remains playable after reposition');
 console.log(JSON.stringify({ok:true,checks,scenario:'pre-break reposition and server sync'}));
}finally{factory.destroyRoom(room);}
