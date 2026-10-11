'use strict';
const assert=require('assert'),vm=require('vm'),fs=require('fs'),path=require('path');
const {GameRuntimeFactory}=require('../gamehost/runtime');
const handlers={},gestures={},played=[];let muted=false;
class Context {
 constructor(){this.state='suspended';this.currentTime=10;this.destination={};}
 resume(){this.state='running';return Promise.resolve();}suspend(){this.state='suspended';return Promise.resolve();}
 decodeAudioData(buffer){return Promise.resolve(buffer);}
 createBufferSource(){const s={connect(){},disconnect(){},stop(){},start(time){played.push({clip:s.buffer,time});s.onended?.();}};return s;}
 createOscillator(){const s={frequency:{},connect(){},disconnect(){},start(time){played.push({tone:s.frequency.value,time});},stop(){s.onended?.();}};return s;}
 createGain(){return {gain:{setValueAtTime(){},linearRampToValueAtTime(){},exponentialRampToValueAtTime(){}},connect(){},disconnect(){}};}
}
const window={AudioContext:Context,SamiDevGames:{current:()=>({id:'crazy8'})},SamiDevNetwork:{on:(type,fn)=>handlers[type]=fn},SamiDevGameUI:{isMuted:()=>muted}};
const document={hidden:false,addEventListener:(type,fn)=>gestures[type]=fn};
vm.runInNewContext(fs.readFileSync('game/crazy8-audio.js','utf8'),{window,document,queueMicrotask,fetch:async url=>({ok:true,arrayBuffer:async()=>url})});
(async()=>{
 handlers.begin_match();assert.equal(played.length,0);await gestures.pointerdown();await new Promise(r=>setImmediate(r));assert.match(played[0].clip,/shuffle/);
 const f=new GameRuntimeFactory(path.resolve('game/games/crazy8'),{gameId:'crazy8'}),settings={seats:0,live:1,special:0};
 const room=f.createRoom('SOUNDS',settings,2,()=>{}),host=f._baseHostApi();host.ownerSeat=()=>1;host.sendMove=()=>{};
 f.context.SamiDev=host;const g=new f.GameLogicCtor();g.initialize(settings,1);g.onSetAlarm=()=>{};g._initialSync=true;
 const audio=window.SamiDevCardAudio;audio.bindLocal(g);
 const checkpoint=(defenderCards)=>{
  f._activate(room);const s=room.logic;s.hands=[[56,4],defenderCards];s.discard=[4];s.turn[0]=0;s.crank=0;s.lastPlay=-1;s.seatInactivity=[false,false];s._sequence=[0,0];
  const snap=f.describeRoom(room,true).snapshot._samidev_clientViews['1'];f.context.SamiDev=host;audio.setSyncing(true);g.deserialize(structuredClone(snap),1);audio.setSyncing(false);played.length=0;
 };
 const attack=()=>{
  const packet={i:'attack',n:0,m:{c:56,o:0}},result=f.processMove(room,0,structuredClone(packet));assert(result.accepted);
  f.context.SamiDev=host;assert(g.move(0,packet,structuredClone(result.revealBySeat['1'])));return packet;
 };
 try{
  checkpoint([4,8]);const packet=attack();await new Promise(r=>setImmediate(r));
  const draws=played.filter(x=>x.clip?.includes('draw'));assert.equal(draws.length,4,'native automatic +4 has four card sounds');assert(draws.every((x,i)=>i===0||x.time>draws[i-1].time),'draw sounds staggered');
  assert.equal(played.filter(x=>x.clip?.includes('special')).length,1);assert(!played.some(x=>x.tone));
  const count=played.length;g.move(0,packet,{});assert.equal(played.length,count,'echo/replay cannot duplicate effects');
  checkpoint([52,8]);attack();await new Promise(r=>setImmediate(r));assert.equal(played.filter(x=>x.clip?.includes('warning')).length,1,'defender hears one recorded-bell warning');assert(!played.some(x=>x.tone),'recorded effects only');assert(!played.some(x=>x.clip?.includes('draw')),'no draw when defender may stack');
  g.emitter.emit('turnChanged',g.turn);await new Promise(r=>setImmediate(r));assert.equal(played.filter(x=>x.clip?.includes('warning')).length,1,'same threat not repeated');
  played.length=0;g.emitter.emit('move','drawCards',1,8);assert.equal(played.length,8,'stacked draw count');g.emitter.emit('move','revealDraw',1,8);assert.equal(played.length,8,'private reveal replacement silent');
  played.length=0;g.emitter.emit('batchDraw',[0,1],2);assert.equal(played.length,4,'batch penalties audible');
  played.length=0;audio.setSyncing(true);g.emitter.emit('move','drawCards',1,4);assert.equal(played.length,0,'resync/history silent');audio.setSyncing(false);
  muted=true;g.emitter.emit('move','drawCards',1,4);assert.equal(played.length,0);muted=false;
  window.__SAMIDEV_AUDIO_SUSPENDED=true;g.emitter.emit('move','drawCards',1,4);assert.equal(played.length,0);window.__SAMIDEV_AUDIO_SUSPENDED=false;
  document.hidden=true;gestures.visibilitychange();g.emitter.emit('move','drawCards',1,4);assert.equal(played.length,0);
  console.log('PASS: native +4, stacking warning, 8-card burst, batch draw, duplicate/reveal suppression, resync silence, mute and background suspension');
 }finally{f.destroyRoom(room);}
})().catch(e=>{console.error(e);process.exitCode=1;});
