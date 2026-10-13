'use strict';
process.env.SAMIDEV_POOL_DIAGNOSTIC_FRAMES='1';
const assert=require('node:assert/strict'),path=require('node:path');
const {GameRuntimeFactory}=require('../gamehost/runtime');
const f=new GameRuntimeFactory(path.join(__dirname,'../game/games/pool'),{gameId:'pool',expectedSha256:require('../game/samidev-integrity.json').games.pool.sha256});
const settings={gameType:0,break:0,live:1,trickShots:0};let checks=0;
const check=(v,m)=>{assert.ok(v,m);checks++;};
const move=(r,s,m)=>f.processMove(r,s,{i:'test-'+checks,n:r.logic._sequence[s],m});
const stable=g=>JSON.stringify({balls:g.table.balls.map(b=>[...b.position]),cue:[...g.table.cueBall.position],turn:g.turn,seq:g._sequence,gameOver:g.gameOver,solids:g.solids});
const r=f.createRoom('POOL',settings,2,()=>{}),g=r.logic;
try{
 check(g.turn[0]===0,'breaking turn');check(move(r,0,{__ready:1}).accepted,'ready');
 const before=stable(g);
 for(const bad of [{a:1,st:10,an:0,sp:[0,0]},{a:1,st:.5,an:Infinity,sp:[0,0]},{a:1,st:.5,an:0,sp:[1,1]},{a:1,st:.5,an:0,sp:[0,0],__psValidationMove:true},{a:7},{a:8,al:'yes'},{a:3,an:Infinity},{a:4,st:2},{a:2,ps:[-999,999]},{a:1,st:.5,an:0,sp:[0,0],winner:0}])check(!move(r,0,bad).accepted,'malicious payload rejected');
 check(!move(r,1,{a:1,st:.8,an:0,sp:[0,0]}).accepted,'wrong turn');
 check(!f.processMove(r,0,{__info:{a:-1,idx:1,logic:{winner:0}}}).accepted,'client result rejected');
 check(stable(g)===before,'rejected moves have no side effects');
 check(move(r,0,{a:8,al:false}).accepted,'native aim-line preference');check(move(r,0,{a:3,an:0}).accepted,'native cue direction');check(move(r,0,{a:4,st:.5}).accepted,'native power preview');
 const packet={i:'shot',n:g._sequence[0],m:{a:1,st:.8,an:-Math.PI/2,sp:[0,0]}};
 const t=performance.now(),shot=f.processMove(r,0,structuredClone(packet)),elapsed=performance.now()-t;
 check(shot.accepted,'native break shot');check(g.poolFrames.length>2,'actual physics trajectory');check(!g.isBreaking(),'valid break completed');check(g.turn[0]===1,'turn passes');
 check(!f.processMove(r,0,packet).accepted,'replay rejected');check(!!shot.revealBySeat['0'].pool&&!!shot.revealBySeat['1'].pool,'both seats receive authoritative state');
 const snap=f.describeRoom(r,true);check(snap.snapshotSafe&&!!snap.snapshot.pool,'pool checkpoint');const restored=f.createRoom('RESTORE',settings,2,()=>{});
 try{f.deserialize(restored,snap.snapshot);check(stable(restored.logic)===stable(g),'restart restores physics and rules');}finally{f.destroyRoom(restored);}
 // Move cue ball only with ball-in-hand; negative status restricts placement to kitchen.
 g.ballInHand=0;check(!move(r,1,{a:2,ps:[412,1200]}).accepted,'placement forbidden without ball in hand');
 g.ballInHand=-1;check(!move(r,1,{a:2,ps:[400,400]}).accepted,'kitchen restriction');check(move(r,1,{a:2,ps:[412,1200]}).accepted,'legal cue placement');
 check(move(r,0,{a:0}).accepted&&g.gameOver,'resign');check(!move(r,1,{a:1,st:.5,an:0,sp:[0,0]}).accepted,'postgame shot rejected');
 console.log(JSON.stringify({case:'rules and security',checks,localBreakMs:elapsed,frames:shot.revealBySeat['0'].frames.length}));
}finally{f.destroyRoom(r);}
// Legitimate eight-ball finish using the actual supplied collision/pocket rules.
for(const cleared of [true,false]){
 const r=f.createRoom('FINISH',settings,2,()=>{}),g=r.logic;
 try{move(r,0,{__ready:1});g.ballInHand=0;g.solids=0;
 if(cleared)for(const b of g.table.balls)if(b.rank<8)b.setPocketed();
 const eight=g.table.getKeyBall();eight.position[0]=125;eight.position[1]=125;eight.aabbNeedsUpdate=true;eight.wakeUp();
 g.table.cueBall.position[0]=200;g.table.cueBall.position[1]=200;g.table.cueBall.aabbNeedsUpdate=true;g.updateTurnShootingFor();
 check(move(r,0,{a:1,st:.2,an:-Math.PI*.75,sp:[0,0]}).accepted,'eight-ball shot');check(g.gameOver&&eight.isPocketed(),'pocket determines finish');check(g.poolSounds.some(e=>e.kind==='pocket'),'pocket sound follows actual sink');check(g.finishOrder[0][0]===(cleared?0:1),'legal win / early-eight loss');
 }finally{f.destroyRoom(r);}
}
console.log(JSON.stringify({ok:true,checks,nativeLegalWinAndEarlyEightLoss:true}));
