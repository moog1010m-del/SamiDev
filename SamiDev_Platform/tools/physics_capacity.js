'use strict';
// Measure actual synchronous server physics. This is CPU service time, not CCU capacity.
const path=require('node:path'),{performance}=require('node:perf_hooks');
const {GameRuntimeFactory}=require('../gamehost/runtime');
const count=Number(process.argv[2]||50);
if(!Number.isInteger(count)||count<1||count>500)throw new Error('shots must be 1..500');
const reports=[];
for(const game of ['carrom','pool']){
 const dir=game==='carrom'?path.join(__dirname,'../game'):path.join(__dirname,'../game/games/pool');
 const f=new GameRuntimeFactory(dir,{gameId:game});
 const times=[],cpuTimes=[],bytes=[];
 for(let i=0;i<count;i++){
  const r=f.createRoom('PHYSICS',{players:0,live:1,gamemode:0,break:0},2,()=>{});
  try{
   let n=0;
   if(game==='carrom')f.processMove(r,0,{n:n++,i:'start',m:{m:0}});
   else for(let seat=0;seat<2;seat++)f.processMove(r,seat,{n:r.logic._sequence[seat],i:'ready-'+seat,m:{__ready:1}});
   const seat=r.logic.turn[0];
   const packet={n:r.logic._sequence[seat],i:'shot',m:game==='pool'?{a:1,st:.55+(i%4)*.1,an:-Math.PI/2+(i%3)*.02,sp:[0,0]}:{m:5,i:[0,50+(i%5)*50],ps:.5}};
   const start=performance.now();
   const cpuStart=process.cpuUsage();
   const result=f.processMove(r,seat,packet);
   times.push(performance.now()-start);
   const cpu=process.cpuUsage(cpuStart);cpuTimes.push((cpu.user+cpu.system)/1000);
   if(!result.accepted)throw new Error(game+' shot rejected');
   bytes.push(Buffer.byteLength(JSON.stringify(result.revealBySeat)));
  }finally{f.destroyRoom(r);}
 }
 times.sort((a,b)=>a-b);cpuTimes.sort((a,b)=>a-b);bytes.sort((a,b)=>a-b);
 reports.push({game,shots:count,synchronousShotMs:{p50:times[Math.floor(count*.5)],p95:times[Math.floor(count*.95)],max:times.at(-1)},
  cpuMs:{mean:cpuTimes.reduce((a,b)=>a+b,0)/count,p50:cpuTimes[Math.floor(count*.5)],p95:cpuTimes[Math.floor(count*.95)],max:cpuTimes.at(-1)},
  revealBytes:{p50:bytes[Math.floor(count*.5)],p95:bytes[Math.floor(count*.95)]},
  scope:'original server physics; isolated first shots; excludes network, checkpoints, auth and production hardware'});
}
console.log(JSON.stringify({ok:true,reports},null,2));
