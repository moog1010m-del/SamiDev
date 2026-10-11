'use strict';
// Exercise the shipped UI adapter's handshake, not a duplicate implementation.
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync('game/browser-runtime.js','utf8');
const adapter=source.slice(source.indexOf('  async function resignOnlineMatch('),source.indexOf('  function resize()'));
(async()=>{
 for(const [game,move] of [['pool',{a:0}],['crazy8',{q:1}],['tablesoccer',{a:3}],['carrom',{m:4}]]){
  const handlers=new Map();let paused=0,cardStops=0;
  const net={on(name,fn){handlers.set(name,fn);return()=>handlers.delete(name);},sendMove(){throw Error('unexpected fallback');}};
  const logic={localSeat:1,gameOver:false,paused:false,_sequence:[0,2],localMove(value){
   assert.equal(JSON.stringify(value),JSON.stringify(move));
   queueMicrotask(()=>{
    handlers.get('move')({seat:0,packet:{m:move}});assert(handlers.has('move'),'opponent ACK must not confirm our exit');
    handlers.get('move')({seat:1,packet:{m:move},authority:{gameOver:true}});
   });return true;
  }};
  const hostBridge={game_preferences:{other:'preserved'},saveGamePreferences(value){this.game_preferences=value;}};
  const context={state:{gameLogic:logic,network:{online:true},menuButtons:[]},window:{SamiDevNetwork:net,SamiDevCardAudio:{stop(){cardStops++;}}},hostBridge,audios:new Map([[1,{pause(){paused++;}}]]),isPool:game==='pool',isCrazy8:game==='crazy8',isTableSoccer:game==='tablesoccer',performance,setTimeout,clearTimeout,runtimeDebug:false,console};
  vm.runInNewContext(adapter,context);const ui=context.window.SamiDevGameUI;
  const result=await ui.resignMatch();assert(result.ok&&result.gameOver,game+' ACK');assert.equal(handlers.size,0);
  assert.equal(ui.canHelp(),false);ui.toggleSound();assert(ui.isMuted());assert.equal(hostBridge.game_preferences.other,'preserved');assert.equal(paused,1);assert.equal(cardStops,1);ui.toggleSound();assert.equal(ui.isMuted(),false);
 }
 console.log('PASS: shared menu resignation ACKs for all four games, cross-seat isolation, listener cleanup and mute');
})().catch(error=>{console.error(error);process.exitCode=1;});
