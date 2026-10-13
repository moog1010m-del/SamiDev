'use strict';
const assert=require('node:assert/strict');
const {GameRuntimeFactory}=require('../gamehost/runtime');
const f=new GameRuntimeFactory(require('node:path').join(__dirname,'../game/games/pool'),{gameId:'pool'});
const settings={gameType:0,break:0,live:1,trickShots:0};
function room(){const r=f.createRoom('ABCDEF',settings,2,()=>{});f.processMove(r,0,{i:'ready',n:0,m:{__ready:1}});return r;}
const r=room(),neighbor=room();
const neighborBefore=JSON.stringify(f.describeRoom(neighbor).pool);
try{
 const pre=f.describeRoom(r,true),seq=[...r.logic._sequence],random=[...r.logic.random.state],initialShot=JSON.stringify(r.logic.currentShot);
 r.logic.executingPM=true;
 const guarded=f.processMove(r,0,{i:'unsafe',n:seq[0],m:{a:1,st:.8,an:-Math.PI/2,sp:[0,0]}});
 assert(!guarded.accepted&&guarded.rejectionReason==='CHECKPOINT_UNAVAILABLE');
 assert.deepEqual([...r.logic._sequence],seq);r.logic.executingPM=false;
 r.logic.poolMaxSteps=1;
 const packet={i:'limited',n:seq[0],m:{a:1,st:.8,an:-Math.PI/2,sp:[0,0]}};
 assert.throws(()=>f.processMove(r,0,packet),e=>e.code==='PHYSICS_DID_NOT_SETTLE');
 assert.deepEqual(JSON.parse(JSON.stringify(f.describeRoom(r).pool)),JSON.parse(JSON.stringify(pre.pool)),'failed physics restores game state');
 assert.deepEqual([...r.logic._sequence],seq,'failed shot never consumes sequence');
 assert.deepEqual([...r.logic.random.state],random,'failed shot never consumes random state');
 assert.equal(r.logic.noAnimations,0);
 assert.equal(JSON.stringify(r.logic.currentShot),initialShot,'failed shot transient state discarded');
 assert.equal(JSON.stringify(f.describeRoom(neighbor).pool),neighborBefore,'other room unaffected');
 for(const b of [r.logic.table.cueBall,...r.logic.table.balls]){assert.deepEqual([...b.velocity],[0,0]);assert.equal(b.angularVelocity,0);}
 r.logic.poolMaxSteps=9000;
 const result=f.processMove(r,0,packet);assert(result.accepted,'same sequence can retry after rollback');
 const reveal=result.revealBySeat['0'];assert.equal(reveal.rid,0);assert(reveal.data['1'].p,'native final-position reveal retained');
 assert(!('frames' in reveal),'production does not send unused frame arrays');
 assert.equal(r.logic.poolFrames.length,0);
 assert.equal(r.logic.noAnimations,1);assert.equal(r.logic.lastValidAnim,1);
 const snapshot=f.describeRoom(r,true).snapshot,copy=room();
 try{f.deserialize(copy,snapshot);assert.deepEqual(JSON.parse(JSON.stringify(f.describeRoom(copy).pool)),JSON.parse(JSON.stringify(f.describeRoom(r).pool)));}finally{f.destroyRoom(copy);}
 console.log(JSON.stringify({ok:true,checks:['native animation/world reveal','no unused production frames','failed physics restores positions and velocities','sequence and RNG rollback','retry and snapshot restore'],revealBytes:Buffer.byteLength(JSON.stringify(reveal))}));
}finally{f.destroyRoom(r);f.destroyRoom(neighbor);}

// A failure after a physical pot/win must roll back scores and pocket collision flags too.
const win=f.createRoom('WINAAA',{...settings,gameType:7},2,()=>{});
try{
 f.processMove(win,0,{i:'ready-win',n:0,m:{__ready:1}});
 const g=win.logic;g.ballInHand=0;
 for(let i=0;i<15;i++){const b=g.table.balls[i];b.setPosition([680,250+i*75]);}
 for(let rank=2;rank<=8;rank++)g.table.balls[rank-1].setPocketed();
 g.freePoolScores[0]=7;g.freePoolPocketed=[2,3,4,5,6,7,8];
 g.table.balls[0].setPosition([125,125]);g.table.cueBall.setPosition([200,200]);g.updateTurnShootingFor();
 const before=JSON.stringify(f.describeRoom(win).pool),packet={i:'win-rollback',n:g._sequence[0],m:{a:1,st:.2,an:-Math.PI*.75,sp:[0,0]}};
 const complete=g.shotCompleted.bind(g);g.shotCompleted=function(){complete();throw Error('injected post-physics failure');};
 assert.throws(()=>f.processMove(win,0,structuredClone(packet)),/injected/);
 assert.equal(JSON.stringify(f.describeRoom(win).pool),before);
 assert(!win.logic.gameOver);assert.equal(win.lastGameOver,null);
 assert(f.processMove(win,0,packet).accepted);assert(win.logic.gameOver);assert.equal(win.logic.freePoolScores[0],8);
 console.log('PASS physical pot/win rollback and exact retry');
}finally{f.destroyRoom(win);}

const originalNow=Date.now;let clock=originalNow();Date.now=()=>clock;
const timed=room();
try{
 clock+=10000;
 const deadline=f._alarmInfo(timed,timed.logic._nextAlarmId);
 const saved=f.describeRoom(timed,true).snapshot;
 timed.logic.poolMaxSteps=1;
 assert.throws(()=>f.processMove(timed,0,{i:'timer-fail',n:timed.logic._sequence[0],m:{a:1,st:.8,an:-Math.PI/2,sp:[0,0]}}),e=>e.code==='PHYSICS_DID_NOT_SETTLE');
 assert.deepEqual(f._alarmInfo(timed,timed.logic._nextAlarmId),deadline,'rollback preserves external alarm and remaining turn budget');
 clock+=5000;
 const restored=room();
 try{f.deserialize(restored,saved);assert.deepEqual(f._alarmInfo(restored,restored.logic._nextAlarmId),[deadline[0]-5000,deadline[1]],'host restoration deducts checkpoint age');}
 finally{f.destroyRoom(restored);}
 console.log('PASS rollback retains original turn deadline; recovery deducts checkpoint age');
}finally{Date.now=originalNow;f.destroyRoom(timed);}

let pausedClock=originalNow();Date.now=()=>pausedClock;
const paused=room();
try{
 pausedClock+=10000;f.waitForClients(paused);
 const before=f._alarmInfo(paused,paused.logic._nextAlarmId),snapshot=f.describeRoom(paused,true).snapshot;
 pausedClock+=20000;
 const restored=room();f.waitForClients(restored);
 try{
  f.deserialize(restored,snapshot);assert.deepEqual(f._alarmInfo(restored,restored.logic._nextAlarmId),before,'paused waiting time must not consume the turn');
  f.beginMatch(restored);assert.deepEqual(f._alarmInfo(restored,restored.logic._nextAlarmId),before,'resume keeps original total duration');
 }finally{f.destroyRoom(restored);}
 console.log('PASS paused waiting checkpoint and timer resume');
}finally{Date.now=originalNow;f.destroyRoom(paused);}
(async()=>{
 const source=room(),events=[];
 const restored=f.createRoom('CLOCKB',settings,2,event=>events.push(event));
 try{
  const snapshot=f.describeRoom(source,true).snapshot;
  snapshot._samidev_alarm.expiresAt=Date.now()+40;
  f.deserialize(restored,snapshot);
  await new Promise(resolve=>setTimeout(resolve,100));
  assert(restored.events.some(e=>e.type==='alarm_fired'&&e.accepted),'restored platform scheduler actually invokes native alarm');
  assert(events.some(e=>e.type==='authority_alarm'&&e.alarmId===snapshot.a),'native alarm reveal reaches platform emitter after restoration');
  console.log('PASS restored external timer fires native alarm and publishes authoritative reveal');
 }finally{f.destroyRoom(source);f.destroyRoom(restored);}
})().catch(e=>{console.error(e);process.exitCode=1;});
