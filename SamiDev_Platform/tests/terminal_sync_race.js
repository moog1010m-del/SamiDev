'use strict';
const assert=require('node:assert/strict'),fs=require('fs'),vm=require('vm');
const source=fs.readFileSync('game/browser-runtime.js','utf8');
const start=source.indexOf('  const AUTHORITY_GRACE_MS='),end=source.indexOf('  async function prepareAssetsAndLogic(){',start);
const handlers={},timers=[];let releaseReplay,resyncs=0,alarmCalls=0;
const state={network:{snapshotBusy:false,deferredMoves:[],queuedSnapshot:null,finished:false,authorityEpoch:null,authorityRevision:-1,authorityCheckTimer:null}};
const logic={localSeat:0,gameOver:false,turn:[0],_sequence:[0,0],_localMoves:[],pause(){this.paused=true;},resume(){this.paused=false;},deserialize(s){this.gameOver=s.over;this.turn=s.over?[]:[0];this._sequence=s.seq;},alarm(){alarmCalls++;return true;}};
const context={state,window:{SamiDevNetwork:{on:(n,f)=>handlers[n]=f,requestResync:()=>{resyncs++;return true;}}},document:{getElementById:()=>null},console:{warn(){},info(){}},performance:{now:()=>100},setTimeout:f=>{timers.push(f);return timers.length;},isPool:true,isCrazy8:false,isCarrom:false,
 cloneMove:structuredClone,applyCosmetics(){},refreshNativeAvatars(){},updateWebBadge(){},synchronizeClientView(){},applyDeferredMove(){return true;},waitUntilWorldSettles:async()=>true,replayHistory:()=>new Promise(r=>releaseReplay=r)};
vm.runInNewContext(source.slice(start,end)+'\nthis.install=installNetworkBridge;',context);context.install(logic);
(async()=>{
 const initial=handlers.resync_state({snapshot:{over:false,seq:[0,0]},history:[{}],turn:[0],sequence:[0,0],authorityEpoch:1,revision:1,gameOver:false});
 assert(state.network.snapshotBusy);
 handlers.authority_alarm({type:'authority_alarm',alarmId:2,reveal:{},turn:[1],sequence:[1,0],authorityEpoch:1,revision:2,gameOver:false});
 assert.equal(alarmCalls,0,'alarm cannot mutate a deserializing replica');
 await handlers.resync_state({snapshot:{over:true,seq:[1,1]},history:[],turn:[],sequence:[1,1],authorityEpoch:1,revision:3,gameOver:true});
 assert(state.network.queuedSnapshot.gameOver,'final checkpoint retained during replay');
 releaseReplay(true);await initial;
 assert(logic.gameOver&&state.network.finished,'final checkpoint applied without a move/refresh');assert.deepEqual(logic._sequence,[1,1]);assert.equal(logic.paused,false);
 await handlers.resync_state({snapshot:{over:false,seq:[0,0]},history:[],gameOver:false});assert(logic.gameOver,'late stale checkpoint cannot reopen finished match');
 // An alarm whose id is stale still carries a terminal invariant requiring recovery.
 state.network.finished=false;logic.gameOver=false;logic.turn=[0];logic._nextAlarmId=10;logic.paused=true;
 handlers.authority_alarm({alarmId:9,reveal:{},turn:[],sequence:[1,1],authorityEpoch:1,revision:4,gameOver:true});
 for(const fn of timers.splice(0))fn();assert(resyncs>0,'terminal alarm bypasses animation grace');
 console.log('PASS: queued final checkpoint, buffered alarm, stale snapshot rejection, immediate terminal recovery');
})().catch(e=>{console.error(e);process.exitCode=1;});
