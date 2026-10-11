'use strict';
const path=require('path');
const {GameRuntimeFactory}=require('../gamehost/runtime');
const factory=new GameRuntimeFactory(path.join(__dirname,'..','game'),{expectedSha256:require('../game/samidev-integrity.json').games.carrom.sha256});
const settings={players:0,gamemode:0,live:1,break:0};
const room=factory.createRoom('STATE-FIX',settings,2,()=>{});
const state=()=>({noAnimations:room.logic.noAnimations,lastState:room.logic.lastState,lastValidAnim:room.logic.lastValidAnim,pending:Object.keys(room.logic.animValidation||{}).length});
const result={};
try {
  factory.processMove(room,0,{i:'start',m:{m:0},n:0});
  factory._activate(room);
  room.logic.worldAnimationMove({seat:room.logic.turn[0],data:{m:5,i:[10,0]}},true);
  const before=state();
  const immediate=factory.describeRoom(room,true);
  const after=state();
  result.shotCheckpointImmediate=immediate.snapshotSafe===true && !!immediate.snapshot;
  result.serverStateUnchanged=JSON.stringify(before)===JSON.stringify(after);

  const idx=room.logic.noAnimations;
  const world={a:-1,idx,logic:room.logic.getUpdatedGameStateAfterAnimationComplete(false),gameOver:false,pos:room.logic.getPositionsToValidate(),rot:room.logic.getRotationsToValidate(),extra:room.logic.getExtraValidationInfo()};
  factory.processMove(room,0,{__info:structuredClone(world)});
  const mid=factory.describeRoom(room,true);
  result.clientReportCannotDeferCheckpoint=mid.snapshotSafe===true && JSON.stringify(state())===JSON.stringify(before);
  factory.processMove(room,1,{__info:structuredClone(world)});
  const stableBefore=state();
  const stable=factory.describeRoom(room,true);
  const stableAfter=state();
  result.stableSnapshotProduced=!!stable.snapshot && stable.snapshotDeferred!==true;
  result.stableSerializePure=JSON.stringify(stableBefore)===JSON.stringify(stableAfter);
  result.finalState=stableAfter;
  result.ok=Object.entries(result).filter(([k])=>k!=='finalState'&&k!=='ok').every(([,v])=>v===true);
  console.log(JSON.stringify(result,null,2));
  process.exitCode=result.ok?0:2;
} finally { factory.destroyRoom(room); }
process.exit(process.exitCode||0);
