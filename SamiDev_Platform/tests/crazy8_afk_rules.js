'use strict';
const assert=require('node:assert/strict'),path=require('node:path');
const {GameRuntimeFactory}=require('../gamehost/runtime');
const f=new GameRuntimeFactory(path.resolve('game/games/crazy8'),{gameId:'crazy8'});
const expire=async room=>{f._scheduleAlarm(room,1,room.logic._nextAlarmId);await new Promise(r=>setTimeout(r,35));};
(async()=>{
 for(const mode of ['both_inactive','one_inactive']){
  const events=[],r=f.createRoom(mode,{seats:0,live:1,special:0},2,e=>events.push(e)),g=r.logic;
  try{
   const inactive=g.turn[0];await expire(r);assert.equal(g.gameOver,false,'one timeout alone does not end match');
   if(mode==='one_inactive'){
    const active=g.turn[0];assert.notEqual(active,inactive);
    assert(f.processMove(r,active,{i:'played',n:g._sequence[active],m:{d:1}}).accepted);
    assert.equal(g.turn[0],inactive);
   }
   await expire(r);assert(g.gameOver,'native second inactivity condition ends match');
   assert(events.some(e=>e.gameOver),'terminal alarm published');
   if(mode==='both_inactive')assert.equal(g.won,-2,'both inactive: cancellation/draw');
   else assert.equal(g.won,1-inactive,'second missed own turn: opponent wins');
  }finally{f.destroyRoom(r);}
 }
 console.log('PASS: native two-player inactivity cancellation and two missed own turns forfeit; thresholds unchanged');
})().catch(e=>{console.error(e);process.exitCode=1;});
