'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),os=require('node:os'),path=require('node:path');
const {MatchRecorder}=require('../gamehost/match-recorder');
const {GameRuntimeFactory}=require('../gamehost/runtime');
const directory=fs.mkdtempSync(path.join(os.tmpdir(),'samidev-record-contract-'));
const f=new GameRuntimeFactory(path.join(__dirname,'../game/games/pool'),{gameId:'pool'});
const room=f.createRoom('ABCDEF',{gameId:'pool',gameType:7,live:1,break:0,trickShots:0},2,()=>{});
room.gameId='pool';room.factory=f;
function capture(recorder,seat,m){
 const packet={i:'secret-session-token-must-not-export',n:room.logic._sequence[seat],m};
 const result=f.processMove(room,seat,packet);
 recorder.command(room,seat,packet,f.describeRoom(room,true),{accepted:result.accepted,processingMs:1});
}
(async()=>{
 try{
  assert.throws(()=>new MatchRecorder().start(room),e=>e.code==='RECORDING_DISABLED');
  const recorder=new MatchRecorder(directory);const status=recorder.start(room);
  assert(status.active);assert.equal(recorder.start(room).recordingId,status.recordingId,'starting twice does not duplicate recording');
  await assert.rejects(recorder.download(status.recordingId),e=>e.code==='RECORDING_STILL_ACTIVE');
  capture(recorder,0,{__ready:1});
  recorder.command(room,0,{i:'private',n:1,m:{a:1,secret:'never-export'}},f.describeRoom(room,true),{accepted:false,processingMs:1,code:'REJECTED'});
  recorder.command(room,0,{__info:{secret:'never-export'}},f.describeRoom(room,true),{accepted:true,processingMs:1});
  const stopped=await recorder.stop(room.roomId,room);assert(stopped.complete&&!stopped.active);
  const data=await recorder.download(status.recordingId),raw=fs.readFileSync(data.file,'utf8'),rows=raw.trim().split('\n').map(JSON.parse);
  assert(!raw.includes('secret-session-token')&&!raw.includes('never-export')&&!raw.includes('ABCDEF'));
  assert.equal(rows[0].type,'header');assert.equal(rows[0].initialSnapshot.d.p.length,16);
  assert.equal(rows[1].type,'command');assert.deepEqual(rows[1].input,{__ready:1});
  assert.equal(rows[2].type,'rejected');assert.equal(rows[3].type,'end');assert.equal(rows[3].events,2);
  assert.equal(rows[3].complete,true);assert.deepEqual(rows[3].state.sequence,[...room.logic._sequence]);
  await assert.rejects(recorder.download('../secret'),e=>e.code==='BAD_RECORDING_ID');
  const limited=new MatchRecorder(directory,{maxEvents:1});limited.start(room);
  capture(limited,0,{a:4,st:0});capture(limited,0,{a:4,st:.1});
  const limit=await limited.stop(room.roomId,room);assert(!limit.complete,'limit must never produce a passing trace');
  const failure=new MatchRecorder(directory);const fail=failure.start(room);
  failure.byRoom.get(room.roomId).stream.destroy(Object.assign(new Error('injected disk failure'),{code:'EIO'}));
  const failed=await failure.stop(room.roomId,room);assert(!failed.complete);assert.equal(failed.error,'EIO');
  assert(f.processMove(room,0,{i:'still-playable',n:room.logic._sequence[0],m:{a:4,st:.2}}).accepted,'recording failure does not break gameplay');
  console.log(JSON.stringify({ok:true,checks:['disabled by default','single recording','no credentials/identities','ordered authoritative inputs','sealed export','path validation','budget overflow incomplete','disk failure does not break gameplay']}));
 }finally{f.destroyRoom(room);fs.rmSync(directory,{recursive:true,force:true});}
})().catch(error=>{console.error(error);process.exitCode=1;});
