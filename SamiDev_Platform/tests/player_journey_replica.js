'use strict';
// Client replicas, not a second authority. Input is exclusively seat-filtered
// WebSocket packets; policy sees its own hand. No internal server endpoint/key.
const path=require('node:path'),readline=require('node:readline');
const {GameRuntimeFactory}=require('../gamehost/runtime');
const f=new GameRuntimeFactory(path.join(__dirname,'../game/games/crazy8'),{gameId:'crazy8'});
const players=new Map();
function activate(p){f.context.SamiDev=p.host;}
function view(p){
 const g=p.logic;
 if(!g.gameOver&&g.hands.some((hand,seat)=>seat!==p.seat&&hand.some(card=>card!==-1)))throw new Error('opponent hand exposed before game over');
 if(g.stock.some(card=>card!==-1))throw new Error('stock exposed');
 if(g.hands[p.seat].some(card=>card<0))throw new Error('own hand contains unresolved cards');
 return {sequence:[...g._sequence],turn:[...g.turn],gameOver:!!g.gameOver,
   handCounts:g.hands.map(hand=>hand.length),ownHand:[...g.hands[p.seat]],
   finishOrder:g.finishOrder?JSON.parse(JSON.stringify(g.finishOrder)):null,paused:!!g.paused};
}
function command(c){
 if(c.op==='init'){
  if(c.snapshot?._samidev_clientViews||'kc' in (c.snapshot?.d||{}))throw new Error('private server snapshot supplied');
  const host=f._baseHostApi();host.ownerSeat=()=>c.seat;host.setTimer=()=>0;host.clearTimer=()=>{};host.alarm={set(){}};host.sendMove=()=>{};
  const p={host,seat:c.seat};activate(p);p.logic=new f.GameLogicCtor();
  p.logic.initialize(c.settings,c.seat);p.logic.onSetAlarm=()=>{};
  p.logic.deserialize(c.snapshot,c.seat);p.logic._initialSync=true;
  if(p.logic.server)throw new Error('replica must be in client mode');
  players.set(c.player,p);return view(p);
 }
 const p=players.get(c.player);if(!p)throw new Error('unknown replica');activate(p);
 const g=p.logic;
 if(c.op==='close'){players.delete(c.player);return true;}
 if(c.op==='event'){
  const m=c.message;
  if(m.type==='move'){
   if(m.packet.n>=g._sequence[m.seat]&&!g.move(m.seat,m.packet,m.reveal))throw new Error('native client rejected accepted move');
  }else if(m.type==='authority_alarm'){
   const expected=Number(g.nextAlarmId??g._nextAlarmId);
   if(m.alarmId>=expected&&!g.alarm(m.reveal,m.alarmId))throw new Error('native client rejected authority alarm');
  }else if(m.type==='resync_state'){
   if(m.snapshot?._samidev_clientViews||'kc' in (m.snapshot?.d||{}))throw new Error('private resync exposed');
   g.deserialize(m.snapshot,p.seat);g._initialSync=true;g._awaitingResync=false;
   for(const item of m.history||[])if(item.packet.n>=g._sequence[item.seat]&&!g.move(item.seat,item.packet,item.reveal))throw new Error('history replay rejected');
  }
  return view(p);
 }
 if(c.op==='state')return view(p);
 if(c.op==='choose'){
  if(g.gameOver||!g.turn.includes(p.seat))return null;
  const playable=g.hands[p.seat].filter(card=>g.canPlayCard(p.seat,card));
  const card=playable.sort((a,b)=>Number([8,14,15,16].includes(a>>2))-Number([8,14,15,16].includes(b>>2)))[0];
  const colors=[0,0,0,0];for(const own of g.hands[p.seat])colors[own&3]++;
  const color=colors.indexOf(Math.max(...colors));
  const move=card===undefined?{d:1}:{c:card,...([8,14,15,16].includes(card>>2)?{o:color}:{})};
  return {n:g._sequence[p.seat],m:move};
 }
 throw new Error('unsupported command');
}
const lines=readline.createInterface({input:process.stdin});
lines.on('line',line=>{
 let c;try{c=JSON.parse(line);const started=process.hrtime.bigint();const value=command(c);process.stdout.write(JSON.stringify({id:c.id,ok:true,value,processingMs:Number(process.hrtime.bigint()-started)/1e6})+'\n');}
 catch(error){process.stdout.write(JSON.stringify({id:c?.id,ok:false,error:error.message})+'\n');}
});
