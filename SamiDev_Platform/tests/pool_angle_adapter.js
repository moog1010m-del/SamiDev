'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../game/browser-runtime.js'),'utf8');
const adapter=source.slice(source.indexOf('  const poolAngleAdapters'),source.indexOf('  const hostBridge ='));
function bind(pool=true){return vm.runInNewContext(`const isPool=${pool};${adapter};bindPoolAngles`);}
const install=bind(),calls=[];
const logic={localMove(move,...args){calls.push({move,args,self:this});return 'native-result';}};
install(logic);const wrapped=logic.localMove;install(logic);assert.equal(logic.localMove,wrapped);
for(const an of [0,-0,Math.PI,-Math.PI,2*Math.PI,-2*Math.PI,NaN,Infinity,-Infinity,'7',null,undefined]){
 const move={a:3,an};assert.equal(logic.localMove(move,false),'native-result');assert.equal(calls.at(-1).move,move);
}
for(const a of [1,3])for(const an of [Math.PI*20+.25,-Math.PI*20-.25]){
 const move=Object.freeze({a,an,st:.3,sp:[0,0]});logic.localMove(move,false,'extra');
 const call=calls.at(-1);assert.equal(call.move.an,an%(2*Math.PI));assert.equal(move.an,an);
 assert.equal(call.move.sp,move.sp);assert.deepEqual(call.args,[false,'extra']);assert.equal(call.self,logic);
}
const other={a:4,an:99};logic.localMove(other);assert.equal(calls.at(-1).move,other);
const nonpool={localMove(){}};const original=nonpool.localMove;bind(false)(nonpool);assert.equal(nonpool.localMove,original);
// Feed the exact browser adapter into the actual authoritative native engine.
const {GameRuntimeFactory}=require('../gamehost/runtime');
const f=new GameRuntimeFactory(path.join(__dirname,'../game/games/pool'),{gameId:'pool'});
const room=f.createRoom('ANGLES',{gameType:0,break:0,live:1,trickShots:0},2,()=>{});
try{
 assert(f.processMove(room,0,{i:'ready',n:0,m:{__ready:1}}).accepted);
 const client={localMove(m){return f.processMove(room,0,{i:'angle',n:room.logic._sequence[0],m});}};install(client);
 for(const an of [Math.PI*20+.25,-Math.PI*20-.25])assert(client.localMove({a:3,an}).accepted);
 const seq=room.logic._sequence[0];
 for(const an of [Infinity,NaN,'7',Math.PI*20]){
  const result=f.processMove(room,0,{i:'invalid',n:seq,m:{a:3,an}});
  assert.equal(result.accepted,false);assert.equal(result.rejectionReason,'INVALID_AIM_ANGLE');assert.equal(room.logic._sequence[0],seq);
 }
 assert(client.localMove({a:1,st:.3,an:Math.PI*20-Math.PI/2,sp:[0,0]}).accepted);
 assert.equal(room.logic._sequence[0],seq+1);
 console.log('PASS angle adapter: identity/bounds/invalid values/immutable inputs/idempotency/non-pool; actual host accepts multi-turn aim and shot without consuming rejected sequences');
}finally{f.destroyRoom(room);}

const win=f.createRoom('ANGLEWIN',{gameType:7,break:0,live:1,trickShots:0},2,()=>{});
try{
 f.processMove(win,0,{i:'ready-win',n:0,m:{__ready:1}});
 const g=win.logic;g.ballInHand=0;
 for(let i=0;i<15;i++)g.table.balls[i].setPosition([680,250+i*75]);
 for(let rank=2;rank<=8;rank++)g.table.balls[rank-1].setPocketed();
 g.freePoolScores[0]=7;g.freePoolPocketed=[2,3,4,5,6,7,8];
 g.table.balls[0].setPosition([125,125]);g.table.cueBall.setPosition([200,200]);g.updateTurnShootingFor();
 const client={localMove(m){return f.processMove(win,0,{i:'last-ball',n:g._sequence[0],m});}};install(client);
 const an=-Math.PI*.75-Math.PI*20;
 assert(client.localMove({a:3,an}).accepted);
 assert(client.localMove({a:1,st:.2,an,sp:[0,0]}).accepted);
 assert(g.gameOver);assert.equal(g.freePoolScores[0],8);
 console.log('PASS multi-revolution aim and physical winning pot on the last ball');
}finally{f.destroyRoom(win);}
