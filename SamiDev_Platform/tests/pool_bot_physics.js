'use strict';
const assert=require('node:assert/strict'),path=require('node:path'),{spawn}=require('node:child_process'),readline=require('node:readline');
const {GameRuntimeFactory}=require('../gamehost/runtime');
const python=spawn(process.env.SAMIDEV_TEST_PYTHON||(process.platform==='win32'?'python':'python3'),[path.resolve(__dirname,'../../experiments/pool-bots/planner.py')],{stdio:['pipe','pipe','inherit']});
const lines=readline.createInterface({input:python.stdout});
function plan(view,seat,skill,seed){return new Promise((resolve,reject)=>{lines.once('line',line=>{try{resolve(JSON.parse(line))}catch(e){reject(e)}});python.stdin.write(JSON.stringify({view,seat,skill,seed})+'\n');});}
const f=new GameRuntimeFactory(path.join(__dirname,'../game/games/pool'),{gameId:'pool'});
let serial=0;
function move(r,m){const seat=r.logic.turn[0];const result=f.processMove(r,seat,{i:'agent-physics-'+serial++,n:r.logic._sequence[seat],m});assert(result.accepted,JSON.stringify({m,reason:result.rejectionReason}));}
(async()=>{
 const trials=[];
 try{
  for(const skill of ['beginner','medium','expert']){
   let potted=0,attempts=0;
   for(let trial=0;trial<30;trial++){
    const r=f.createRoom('FIXTURE'+serial++,{gameType:0,break:0,live:1},2,()=>{}),g=r.logic;
    try{
     move(r,{__ready:1});g.ballInHand=0;g.solids=0;
     for(const b of g.table.balls)if(b.rank!==8)b.setPocketed();
     const eight=g.table.getKeyBall();eight.position[0]=360+(trial%3)*25;eight.position[1]=360+(trial%3)*25;eight.aabbNeedsUpdate=true;eight.wakeUp();
     g.table.cueBall.position[0]=650;g.table.cueBall.position[1]=650;g.table.cueBall.aabbNeedsUpdate=true;g.updateTurnShootingFor();
     const view=f.describeRoom(r).pool,p=await plan(view,0,skill,trial);
     assert.equal(p.target,8);assert(p.thinkSeconds>=2.3);
     for(const step of p.steps)move(r,step.move);
     attempts++;if(eight.isPocketed())potted++;
    }finally{f.destroyRoom(r)}
   }
   trials.push({skill,attempts,potted});
  }
  assert(trials[2].potted>trials[0].potted,'expert should outperform beginner on identical real-physics fixtures');
  // Whole unmodified 8-ball games, including breaks, fouls, placement and final result.
  const games=[];
  for(let game=0;game<3;game++){
   const mode=game===2?7:0;
   const r=f.createRoom('GAME'+serial++,{gameType:mode,break:0,live:1},2,()=>{}),g=r.logic;let shots=0;
   try{
    while(!g.gameOver&&shots<220){
     const seat=g.turn[0];if(g.awaitingReady)move(r,{__ready:1});
     const p=await plan(f.describeRoom(r).pool,seat,'expert',game*1000+shots);
     assert(p);if(p.placement)move(r,{a:2,ps:p.placement});
     for(const step of p.steps)move(r,step.move);
     shots++;
    }
    assert(g.gameOver,'agent game must reach a result, not only random motion');games.push({mode,shots,winner:g.finishOrder[0][0],reason:g.getGameOverReason()});
   }finally{f.destroyRoom(r)}
  }
  console.log(JSON.stringify({ok:true,fixtures:trials,realGames:games,engineUnmodified:true}));
 }finally{python.stdin.end();python.kill();lines.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
