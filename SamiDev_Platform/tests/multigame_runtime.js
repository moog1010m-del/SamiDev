'use strict';
const assert=require('node:assert/strict');
const path=require('node:path');
const {GameRuntimeFactory}=require('../gamehost/runtime');
const root=path.join(__dirname,'..','game');
const hashes=require('../game/samidev-integrity.json');
const factories={};
for(const id of ['carrom','tablesoccer'])factories[id]=new GameRuntimeFactory(id==='carrom'?root:path.join(root,'games',id),{gameId:id,expectedSha256:hashes.games[id].sha256});
let checks=0;const results=[];
function check(v,message){assert.ok(v,message);checks++;}
function move(f,r,s,m){return f.processMove(r,s,{i:'test-'+checks+'-'+r.logic._sequence[s],n:r.logic._sequence[s],m}).accepted;}
for(const players of [0,1])for(const live of [0,1]){
 const cap=players?4:2,f=factories.tablesoccer;
 const r=f.createRoom('SOCCER-'+players+'-'+live,{gameId:'tablesoccer',players,live,goalsToWin:0,passes:1},cap,()=>{});
 try{
 check(move(f,r,0,{a:5,team:'Red.c.h'}),'red selection');
 check(move(f,r,players?2:1,{a:5,team:'Blue.c.h'}),'blue selection');
 for(let s=0;s<cap;s++)check(move(f,r,s,{__ready:1}),'ready '+s);
 const g=r.logic,turn=g.turn[0],bad=Array.from({length:cap},(_,i)=>i).find(s=>!g.isTurn(s));
 const body=g.stadium.players.find(b=>g.stadium.getPlayerTeam(b)===g.getAssignedTeam(turn)+1);
 check(!move(f,r,turn,{a:0,id:body.id,impulse:['bad',0]}),'invalid impulse rejected');
 check(!move(f,r,turn,{a:live?1:0,id:body.id,impulse:[100,0],ci:{rid:body.id,rp:[0,0],bp:[0,0]}}),'client position override rejected');
 if(bad!==undefined)check(!move(f,r,bad,{a:4}),'opponent skip rejected');
 if(live===0)check(move(f,r,turn,{a:0,id:body.id,impulse:[100,0]}),'server physics shot');
 else {
  check(!move(f,r,turn,{a:0,id:body.id,impulse:[100,0]}),'tactical shot rejected in active mode');
  const turns=Array.from(g.turn);
  for(const seat of turns){
   const bodies=g.stadium.players.filter(b=>g.stadium.getPlayerTeam(b)===g.getAssignedTeam(seat)+1 && (!g.is2v2AllPlayMode()||b.id%2===seat%2));
   for(let j=0;j<g.getSTShootingTokens();j++)check(move(f,r,seat,{a:1,id:bodies[j].id,impulse:[100,0],...(players?{idx:g.stadium.players.indexOf(bodies[j]),dimp:[20,0]}:{})}),'active queued shot');
  }
 }
 const d=f.describeRoom(r,true);check(d.snapshotSafe && !!d.snapshot,'shot snapshot available');
 check(d.noAnimations===1,'one shot executed');
 const restored=f.createRoom('RESTORE-'+players+'-'+live,{gameId:'tablesoccer',players,live,goalsToWin:0,passes:1},cap,()=>{});
 try{
 f.deserialize(restored,structuredClone(d.snapshot));
 const next=f.describeRoom(restored,true);
 assert.deepEqual(next.sequence,d.sequence);checks++;
 assert.deepEqual(next.turn,d.turn);checks++;
 check(next.noAnimations===d.noAnimations,'restore animation counter');
 }finally{f.destroyRoom(restored);}
 const opponent=players?2:1;
 check(move(f,r,opponent,{a:3}),'resignation');
 if(players)check(move(f,r,3,{a:3}),'teammate resignation');
 check(g.gameOver,'resignation ends game');
 results.push({game:'tablesoccer',players:cap,live,teams:d.teams,finishOrder:g.finishOrder});
 }finally{f.destroyRoom(r);}
}
for(const players of [0,1]){
 const f=factories.carrom,r=f.createRoom('CARROM-'+players,{gameId:'carrom',players,live:1,gamemode:0,break:0},players?4:2,()=>{});
 try{
 check(move(f,r,0,{m:0}),'carrom start');
 const before=Array.from(r.logic.table.striker.position);
 check(!move(f,r,1,{m:5,ps:.2,i:[100,0]}),'carrom opponent shot rejected');
 assert.deepEqual(Array.from(r.logic.table.striker.position),before);checks++;
 check(!move(f,r,1,{m:3}),'carrom opponent skip rejected');
 check(!move(f,r,0,{m:6,ps:100}),'out of board rejected');
 check(!move(f,r,0,{m:5,ps:.5,i:['bad',0]}),'bad impulse rejected');
 check(move(f,r,0,{m:6,ps:.5}),'valid striker move');
 check(move(f,r,1,{m:4}),'carrom resign');
 if(players)check(move(f,r,3,{m:4}),'carrom teammate resign');
 check(r.logic.gameOver,'carrom ended');
 results.push({game:'carrom',players:players?4:2});
 }finally{f.destroyRoom(r);}
}
// Place a controlled scoring fixture; the accepted shot must use actual server
// collision/goal detection, update the score, and finish at the configured target.
{
 const f=factories.tablesoccer,r=f.createRoom('GOALS',{gameId:'tablesoccer',players:0,live:0,goalsToWin:0,passes:0},2,()=>{}),g=r.logic;
 try{
  check(move(f,r,0,{a:7,t:'Default'}),'default stadium accepted');
  check(move(f,r,0,{a:5,team:'Red.c.h'}),'goal fixture red team');
  check(move(f,r,1,{a:5,team:'Blue.c.h'}),'goal fixture blue team');
  for(const s of [0,1])check(move(f,r,s,{__ready:1}),'goal fixture ready');
  for(let i=0;i<2;i++){
   if(!g.isTurn(0))check(move(f,r,1,{a:4}),'goal fixture next turn');
   g._isNewKickOff=false;
   g.stadium.setBallPosition([525,100]);
   g.changeBodyPos(g.stadium.players.find(b=>b.id===100),[525,185],true);
   g.changeBodyPos(g.stadium.players.find(b=>b.id===150),[100,200],true);
   check(move(f,r,0,{a:0,id:100,impulse:[0,-800]}),'scoring shot accepted');
   check(g.score[0]===i+1,'goal detected by physics');
  }
  check(g.gameOver&&g.finishOrder[0][0]===0,'two goals finish game with correct winner');
  results.push({game:'tablesoccer',scoringGoals:g.score[0],gameOver:true});
 }finally{f.destroyRoom(r);}
}
console.log(JSON.stringify({ok:true,checks,results},null,2));
