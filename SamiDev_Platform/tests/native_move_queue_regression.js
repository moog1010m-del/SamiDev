'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {GameRuntimeFactory}=require('../gamehost/runtime');
const source=fs.readFileSync(path.join(__dirname,'../game/browser-runtime.js'),'utf8');
const helper=source.slice(source.indexOf('  function nextIncomingSequence('),source.indexOf('  async function replayHistory('));
for(const id of ['carrom','pool','crazy8','tablesoccer']){
 const dir=id==='carrom'?path.join(__dirname,'../game'):path.join(__dirname,'../game/games',id);
 const f=new GameRuntimeFactory(dir,{gameId:id});
 const host=f._baseHostApi();host.ownerSeat=()=>1;host.setTimer=()=>0;host.clearTimer=()=>{};
 f.context.SamiDev=host;
 const g=new f.GameLogicCtor();
 g.initialize(id==='crazy8'?{seats:0,live:1,special:0}:{players:0,gamemode:0,live:1,break:0},1);
 g._initialSync=true;g.pause();
 const m=id==='carrom'?{m:0}:id==='pool'?{a:3,an:.5}:id==='crazy8'?{d:1}:{__ready:1};
 assert(g.move(0,{n:0,i:'queued-a',m},{}),id+' first packet queued');
 assert(g.move(0,{n:1,i:'queued-b',m},{}),id+' second packet queued');
 assert.equal(g._sequence[0],0,id+' paused engine has not consumed packets');
 const ctx={Number};vm.createContext(ctx);vm.runInContext(helper+'\nthis.next=nextIncomingSequence;',ctx);
 assert.equal(ctx.next(g,0),2,id+' bridge counts real native queue');
 assert.equal(ctx.next(g,1),0,id+' other seat sequence stays independent');
 g._queue.push({type:0,data:[0,{n:4,i:'real-gap',m},{}]});
 assert.equal(ctx.next(g,0),2,id+' actual gap remains detectable');
 console.log('PASS '+id+' native paused move queue');
}
