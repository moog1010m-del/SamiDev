const path=require('node:path');const readline=require('node:readline');
const {GameRuntimeFactory}=require('../../SamiDev_Platform/gamehost/runtime');
const root=path.resolve(__dirname,'../../SamiDev_Platform/game');
const factories={};
function decide({gameId,snapshot,seat,skill='medium'}){
 skill=({expert:'hard',beginner:'easy'})[skill]||skill;
 const f=factories[gameId] ||= new GameRuntimeFactory(gameId==='carrom'?root:path.join(root,'games',gameId),{gameId});
 const cap=snapshot.s;const settings=gameId==='carrom'?{gameId,players:cap===4?1:0,live:1,gamemode:0,break:0}:{gameId,seats:({2:0,3:1,4:2,6:3})[cap],live:1,special:snapshot.d.special||0};
 const r=f.createRoom('PLAN',settings,cap,()=>{});
 try{f.deserialize(r,snapshot);const g=r.logic;const result={turn:Array.from(g.turn),sequence:Array.from(g._sequence),gameOver:!!g.gameOver,move:null};
 if(gameId==='carrom'&&(!g.started||g.turn.length===0)&&seat===0){result.turn=[0];result.move={m:0};return result;}
 if(g.gameOver||!g.turn.includes(seat))return result;
 if(gameId==='crazy8'){
  const hand=g.hands[seat],cards=hand.filter(c=>c>=0&&g.canPlayCard(seat,c));
  const counts=[0,0,0,0];for(const c of hand)if(c>=0&&![8,14,15,16].includes(c>>2))counts[c&3]++;
  const color=counts.indexOf(Math.max(...counts));let next=g.incrementTurn(seat,g.dir),danger=g.hands[next]?.length<=2;
  const score=c=>{let rank=c>>2;return (counts[c&3]||0)*3+([11,12,13,14].includes(rank)?(danger?45:12):0)+(rank>=11?8:rank)-([8,14,15,16].includes(rank)?20:0);};
  cards.sort((a,b)=>score(b)-score(a));const c=cards[skill==='easy'?Math.floor(Math.random()*cards.length):0];
  result.move=c===undefined?{d:1}:{c,...([8,14,15,16].includes(c>>2)?{o:color}:{})};return result;
 }
 // Evaluate real native physics for legal carrom shots. Only public board positions are used.
 if(!g.started){result.move={m:0};return result;}
 const baseline=structuredClone(snapshot),candidates=[];
 const positions=skill==='hard'?[.12,.3,.5,.7,.88]:[.25,.5,.75];
 for(const ps of positions){f.deserialize(r,structuredClone(baseline));g.table.setStrikerPos(ps);const start=Array.from(g.table.striker.position);
  const targets=g.table.world.bodies.filter(b=>b!==g.table.striker&&b.mass>0&&b.position[0]>60&&b.position[0]<1020&&b.position[1]>60&&b.position[1]<1020);
  for(const target of targets){for(const pocket of g.table.pockets){const x=target.position[0]-pocket.position[0],y=target.position[1]-pocket.position[1],len=Math.hypot(x,y)||1;
   const tx=target.position[0]+x/len*40,ty=target.position[1]+y/len*40,dx=tx-start[0],dy=ty-start[1],d=Math.hypot(dx,dy)||1;
   const cut=(dx*(-x)+dy*(-y))/(d*len);if(cut<.65)continue;
   candidates.push({m:5,ps,i:[dx/d*1700,dy/d*1700],quality:cut-d/6000});
  }}
 }
 candidates.sort((a,b)=>b.quality-a.quality);let best=null,bestScore=-Infinity;
 for(const candidate of candidates.slice(0,skill==='hard'?32:skill==='easy'?4:16)){
  f.deserialize(r,structuredClone(baseline));const before=g.table.world.bodies.filter(b=>b.mass>0).length;
  const move={m:5,ps:candidate.ps,i:candidate.i};const accepted=f.processMove(r,seat,{i:'plan',n:g._sequence[seat],m:move}).accepted;if(!accepted)continue;
  const after=g.table.world.bodies.filter(b=>b.mass>0).length;const score=(g.gameOver?10000:0)+(before-after)*50+(g.turn.includes(seat)?20:0)+candidate.quality;
  if(score>bestScore){bestScore=score;best=move;}
 }
 result.move=best||{m:5,ps:.5,i:[0,seat===0?-1600:1600]};return result;
 }finally{f.destroyRoom(r);}
}
module.exports={decide};
if(require.main===module)readline.createInterface({input:process.stdin}).on('line',line=>{try{console.log(JSON.stringify({ok:true,...decide(JSON.parse(line))}));}catch(e){console.log(JSON.stringify({ok:false,error:e.message}));}});
