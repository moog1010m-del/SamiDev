'use strict';
const assert=require('node:assert/strict'),{spawn}=require('node:child_process'),path=require('node:path'),readline=require('node:readline');
const {GameRuntimeFactory}=require('../gamehost/runtime');
const f=new GameRuntimeFactory(path.join(__dirname,'../game/games/crazy8'),{gameId:'crazy8'});
const child=spawn(process.execPath,[path.join(__dirname,'player_journey_replica.js')]);
let next=0;const pending=new Map();
readline.createInterface({input:child.stdout}).on('line',line=>{const r=JSON.parse(line),p=pending.get(r.id);pending.delete(r.id);r.ok?p.resolve(r.value):p.reject(new Error(r.error));});
function call(op,player,extra={}){const id=++next;return new Promise((resolve,reject)=>{pending.set(id,{resolve,reject});child.stdin.write(JSON.stringify({id,op,player,...extra})+'\n');});}
(async()=>{
 let completed=0,totalMoves=0;
 try{
  for(let match=0;match<10;match++){
   const settings={gameId:'crazy8',seats:0,live:1,special:0};
   const r=f.createRoom('POLICY',settings,2,()=>{});
   try{
    const snapshot=f.describeRoom(r,true).snapshot;
    for(let seat=0;seat<2;seat++)await call('init',seat,{seat,settings,snapshot:snapshot._samidev_clientViews[String(seat)]});
    let moves=0;
    while(!r.logic.gameOver&&moves++<2000){
     const seat=r.logic.turn[0],chosen=await call('choose',seat);assert(chosen);
     const packet={...chosen,i:'policy-'+moves};
     const result=f.processMove(r,seat,packet);assert(result.accepted,'native policy chooses legal moves');
     for(let other=0;other<2;other++){
      const state=await call('event',other,{message:{type:'move',seat,packet,reveal:result.revealBySeat[String(other)]}});
      assert.deepEqual(state.sequence,[...r.logic._sequence]);assert.deepEqual(state.turn,[...r.logic.turn]);
      assert.deepEqual(state.ownHand,[...r.logic.hands[other]]);assert.deepEqual(state.handCounts,Array.from(r.logic.hands,h=>h.length));
     }
    }
    assert(r.logic.gameOver,'full match finishes without resignation or injected winner');
    completed++;totalMoves+=moves;
    for(let seat=0;seat<2;seat++)await call('close',seat);
   }finally{f.destroyRoom(r);}
  }
  console.log(JSON.stringify({ok:true,completedMatches:completed,moves:totalMoves,clientMode:true,privateViewsOnly:true,naturalFinishes:true}));
 }finally{child.stdin.end();child.kill();}
})().catch(error=>{console.error(error);process.exitCode=1;});
