'use strict';
const assert=require('node:assert/strict');
const path=require('node:path');
const {GameRuntimeFactory}=require('../gamehost/runtime');
const f=new GameRuntimeFactory(path.join(__dirname,'../game/games/pool'),{gameId:'pool',expectedSha256:require('../game/samidev-integrity.json').games.pool.sha256});
const room=f.createRoom('REASONS',{gameType:0,break:0,live:1,trickShots:0},2,()=>{});
try {
 const cases=[
  [1,{a:1,st:.5,an:0,sp:[0,0]},'NOT_YOUR_TURN'],
  [0,{a:1,st:2,an:0,sp:[0,0]},'INVALID_SHOT_POWER'],
  [0,{a:1,st:.5,an:Infinity,sp:[0,0]},'INVALID_SHOT_ANGLE'],
  [0,{a:1,st:.5,an:0,sp:[1,1]},'INVALID_SHOT_SPIN'],
  [0,{a:2,ps:[400,400]},'CUE_BALL_OUT_OF_BOUNDS'],
 ];
 for(const [seat,m,reason] of cases){const r=f.processMove(room,seat,{i:'reason',n:room.logic._sequence[seat],m});assert.equal(r.accepted,false);assert.equal(r.rejectionReason,reason);}
 const {poolMoveRejectionReason}=require('../gamehost/pool');
 const base={i:'diagnostic',n:room.logic._sequence[0],m:{a:1,st:.5,an:0,sp:[0,0]}};
 const extras=[
   [{...base,n:base.n+1},'FUTURE_MOVE_SEQUENCE'],
   [{...base,m:{...base.m,cheat:1}},'UNEXPECTED_SHOT_FIELDS'],
   [{...base,m:{a:3,an:Infinity}},'INVALID_AIM_ANGLE'],
   [{...base,m:{a:4,st:2}},'INVALID_AIM_POWER'],
 ];
 for(const [packet,reason] of extras)assert.equal(poolMoveRejectionReason(room.logic,0,packet),reason);
 assert.equal(poolMoveRejectionReason(room.logic,-1,base),'INVALID_SEAT');
 assert.equal(poolMoveRejectionReason(room.logic,0,{...base,m:[]}), 'INVALID_PACKET');
 const originalSequence=room.logic._sequence[0];
 room.logic._sequence[0]=originalSequence+1;
 assert.equal(poolMoveRejectionReason(room.logic,0,base),'STALE_MOVE_SEQUENCE');
 room.logic._sequence[0]=originalSequence;
 console.log('pool rejection reason tests passed:',cases.length+extras.length+3);
} finally {f.destroyRoom(room);}
