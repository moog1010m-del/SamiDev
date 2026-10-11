'use strict';
const assert=require('node:assert/strict');
const path=require('node:path');
const {GameRuntimeFactory}=require('../gamehost/runtime');
const f=new GameRuntimeFactory(path.join(__dirname,'../game/games/crazy8'),{gameId:'crazy8'});
let checks=0, matches=0;
function check(v,msg){assert.ok(v,msg);checks++;}
function packet(r,s,m){return {i:`test-${checks}-${s}`,n:r.logic._sequence[s],m};}
function move(r,s,m){return f.processMove(r,s,packet(r,s,m));}
for(const seats of [0,1,2,3,4])for(const live of [0,1])for(const special of [0,1,2,3,4,5]){
 const cap=[2,3,4,6,4][seats],settings={gameId:'crazy8',seats,live,special};
 const r=f.createRoom('C8TEST',settings,cap,()=>{});
 try {
  const g=r.logic;
  check(g.started && g.server && g.hands.every(h=>h.length===8),'server deals eight cards');
  let full=f.describeRoom(r,true).snapshot;
  for(let seat=-1;seat<cap;seat++){
   const v=full._samidev_clientViews[String(seat)];
   check(v.d.stock.every(c=>c===-1),'stock remains private');
   check(!('kc' in v.d)&&!('_samidev_clientViews' in v),'server metadata absent');
   for(let s=0;s<cap;s++){
    const visible=seat===s || seats===4 && seat>=0 && seat%2===s%2;
    check(JSON.stringify(v.d.hands[s])===JSON.stringify(visible?g.hands[s]:g.hands[s].map(()=>-1)),'hand visibility matches seat/team');
   }
  }
  const turn=g.turn[0],other=(turn+1)%cap;
  for(const [seat,m] of [[other,{d:1}],[turn,{_debug:'win'}],[turn,{m:123}],[turn,{c:4,o:2.5}],[turn,{i:1,c:4}],[turn,{d:1,q:1}],[turn,{c:999}],[turn,{d:1,__auto:1}]])check(!move(r,seat,m).accepted,'invalid move rejected');
  const before=g.hands[turn].length,p=packet(r,turn,{d:1});
  const draw=f.processMove(r,turn,p);check(draw.accepted,'draw accepted');
  check(g.hands[turn].length===before+1,'draw adds one card');
  check(!f.processMove(r,turn,p).accepted,'duplicate sequence rejected');
  for(let s=0;s<cap;s++){
   const rev=draw.revealBySeat[String(s)]||{};
   const allowed=s===turn||seats===4&&s%2===turn%2;
   check(allowed || (!rev.d&&!rev.rd&&!rev.rda),'draw never reveals to opponent');
  }
  full=f.describeRoom(r,true).snapshot;
  const restored=f.createRoom('C8REST',settings,cap,()=>{});
  try{
   f.deserialize(restored,full);
   assert.deepEqual(JSON.parse(JSON.stringify(restored.logic.hands)),JSON.parse(JSON.stringify(g.hands)));checks++;
   assert.deepEqual(Array.from(restored.logic._sequence),Array.from(g._sequence));checks++;
   assert.deepEqual(Array.from(restored.logic.stock),Array.from(g.stock));checks++;
  }finally{f.destroyRoom(restored);}
  // Complete genuine matches through legal moves; exercise special cards and
  // recycled stock without substituting client-computed winners.
  let steps=0;
  while(!g.gameOver && steps++<2000){
   const s=g.turn[0],card=g.hands[s].find(c=>g.canPlayCard(s,c));
   const m=card===undefined?{d:1}:{c:card,...([8,14,15,16].includes(card>>2)?{o:steps%4}:{})};
   check(move(r,s,m).accepted,'legal native move accepted: '+JSON.stringify(m));
  }
  check(g.gameOver && Array.isArray(g.finishOrder)&&g.finishOrder.length>0,'match reaches authoritative result');matches++;
 }finally{f.destroyRoom(r);}
}
(async()=>{
 let emitted;
 const r=f.createRoom('ALARM',{gameId:'crazy8',seats:1,live:1,special:0},3,e=>{emitted=e;});
 try{
  const turn=r.logic.turn[0],before=r.logic.hands[turn].length,id=r.logic._nextAlarmId;
  f._scheduleAlarm(r,5,id);f.waitForClients(r);
  await new Promise(resolve=>setTimeout(resolve,30));
  check(!emitted&&r.logic.hands[turn].length===before,'clock frozen while browsers load');
  f.beginMatch(r);
  await new Promise(resolve=>setTimeout(resolve,30));
  check(emitted?.type==='authority_alarm','server alarm published after begin');
  check(r.logic.hands[turn].length===before+1 && r.logic._sequence[turn]===1,'AFK auto-draw is authoritative');
  for(let seat=0;seat<3;seat++)if(seat!==turn)check(!JSON.stringify(emitted.revealBySeat[String(seat)]).includes('\"d\":['),'AFK draw remains private');
 }finally{f.destroyRoom(r);}
 console.log(JSON.stringify({ok:true,checks,completedMatches:matches,seatModes:5,timerModes:2,specialModes:6,afkTimer:true,loadingGate:true}));
})().catch(e=>{console.error(e);process.exitCode=1;});
