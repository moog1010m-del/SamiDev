'use strict';
const finite=Number.isFinite;
function balls(g){return [g.table.cueBall,...g.table.balls].map(b=>[b.rank||0,Math.round(b.position[0]*100)/100,Math.round(b.position[1]*100)/100,b.isPocketed()?1:0]);}
function poolView(g){return {balls:balls(g),turn:[...g.turn],sequence:[...g._sequence],freePool:!!g.freePool,freePoolScores:(g.freePoolScores||[]).slice(),solids:g.solids,ballInHand:g.ballInHand,breaking:g.isBreaking(),gameOver:g.gameOver,finishOrder:g.finishOrder,reason:g.getGameOverReason(),awaitingReady:!!g.awaitingReady,turnSeconds:Math.round(g.turnDuration/1000),pockets:g.table.pockets.map(p=>[...p.position])};}
function validatePoolMove(g,seat,m){
  if(!Number.isInteger(seat)||seat<0||seat>=g.seats||g.gameOver||g.isResigned(seat))return false;
  const keys=Object.keys(m),only=(...names)=>keys.every(k=>names.includes(k));
  if(m.__ready===1)return keys.length===1;
  if(m.a===0)return only('a')&&g.canResign(seat);
  if(m.a===8)return only('a','al')&&typeof m.al==='boolean';
  if(!g.isTurn(seat))return false;
  if(m.a===3)return only('a','an')&&finite(m.an)&&Math.abs(m.an)<=Math.PI*2;
  if(m.a===4)return only('a','st')&&finite(m.st)&&m.st>=0&&m.st<=1;
  if(m.a===1)return only('a','st','an','sp')&&finite(m.st)&&m.st>=.01&&m.st<=1&&finite(m.an)&&Math.abs(m.an)<=Math.PI*2&&Array.isArray(m.sp)&&m.sp.length===2&&m.sp.every(x=>finite(x)&&Math.abs(x)<=1)&&Math.hypot(...m.sp)<=1.001&&g.canShoot(seat);
  if(m.a===2){
    if(!only('a','ps')||!g.canMoveCueBall(seat)||!Array.isArray(m.ps)||m.ps.length!==2||!m.ps.every(finite))return false;
    const [x,y]=m.ps;
    return (g.ballInHand>=0 || y>=1119) && x>=70&&x<=764&&y>=70&&y<=1446 && !g.table.balls.some(b=>!b.isPocketed()&&Math.hypot(x-b.position[0],y-b.position[1])<41) && !g.table.pockets.some(p=>Math.hypot(x-p.position[0],y-p.position[1])<55);
  }
  return false;
}
function poolMoveRejectionReason(g,seat,packet){
  if(!packet || typeof packet!=='object' || Array.isArray(packet) || !packet.m || typeof packet.m!=='object' || Array.isArray(packet.m))return 'INVALID_PACKET';
  if(!Number.isSafeInteger(packet.n) || packet.n<0 || typeof packet.i!=='string' || !packet.i.length || packet.i.length>160)return 'INVALID_PACKET_METADATA';
  if(Object.keys(packet).some(k=>!['i','n','m'].includes(k)))return 'INVALID_PACKET_FIELDS';
  if(!Number.isInteger(seat)||seat<0||seat>=g.seats)return 'INVALID_SEAT';
  if(Array.isArray(g._sequence) && Number.isSafeInteger(g._sequence[seat]) && packet.n!==g._sequence[seat])return packet.n<g._sequence[seat]?'STALE_MOVE_SEQUENCE':'FUTURE_MOVE_SEQUENCE';
  if(g.gameOver)return 'GAME_OVER';
  if(g.isResigned(seat))return 'PLAYER_RESIGNED';
  const m=packet.m;
  const keys=Object.keys(m);
  const allowed=(...names)=>keys.every(k=>names.includes(k));
  if(m.a===1 && !allowed('a','st','an','sp'))return 'UNEXPECTED_SHOT_FIELDS';
  if(m.a===2 && !allowed('a','ps'))return 'UNEXPECTED_CUE_POSITION_FIELDS';
  if(m.a===3 && !allowed('a','an'))return 'UNEXPECTED_AIM_FIELDS';
  if(m.a===4 && !allowed('a','st'))return 'UNEXPECTED_POWER_FIELDS';
  if(m.a===3 && (!Number.isFinite(m.an)||Math.abs(m.an)>Math.PI*2))return 'INVALID_AIM_ANGLE';
  if(m.a===4 && (!Number.isFinite(m.st)||m.st<0||m.st>1))return 'INVALID_AIM_POWER';
  if(m.a===1){
    if(!g.isTurn(seat))return 'NOT_YOUR_TURN';
    if(!Number.isFinite(m.st)||m.st<.01||m.st>1)return 'INVALID_SHOT_POWER';
    if(!Number.isFinite(m.an)||Math.abs(m.an)>Math.PI*2)return 'INVALID_SHOT_ANGLE';
    if(!Array.isArray(m.sp)||m.sp.length!==2||!m.sp.every(Number.isFinite)||m.sp.some(v=>Math.abs(v)>1)||Math.hypot(...m.sp)>1.001)return 'INVALID_SHOT_SPIN';
    if(!g.canShoot(seat))return 'SHOT_NOT_READY';
  }
  if(m.a===2){
    if(!g.isTurn(seat))return 'NOT_YOUR_TURN';
    if(!g.canMoveCueBall(seat))return 'CUE_BALL_MOVE_NOT_ALLOWED';
    if(!Array.isArray(m.ps)||m.ps.length!==2||!m.ps.every(Number.isFinite))return 'INVALID_CUE_BALL_POSITION';
    const [x,y]=m.ps;
    if(x<70||x>764||y<70||y>1446||(g.ballInHand<0&&y<1119))return 'CUE_BALL_OUT_OF_BOUNDS';
    if(g.table.balls.some(b=>!b.isPocketed()&&Math.hypot(x-b.position[0],y-b.position[1])<41))return 'CUE_BALL_OVERLAPS_BALL';
    if(g.table.pockets.some(p=>Math.hypot(x-p.position[0],y-p.position[1])<55))return 'CUE_BALL_OVERLAPS_POCKET';
  }
  return validatePoolMove(g,seat,m)?'VALID':'INVALID_MOVE_PAYLOAD';
}
function installPoolServer(g){
  // Use the supplied rules/physics implementation, without its browser scene.
  const rules=Object.getPrototypeOf(Object.getPrototypeOf(g));
  g.shoot=function(...args){return rules.shoot.apply(this,args);};
  g.poolFrames=[];g.poolSounds=[];
  const recordFrames=process.env.SAMIDEV_POOL_DIAGNOSTIC_FRAMES==='1';
  g.poolMaxSteps=9000;
  let recording=false,step=0,events=[],lastContact=new Map();
  const emit=(kind,strength)=>{if(recording&&events.length<120)events.push({t:step,kind,strength:Math.min(1,Math.max(.05,strength))});};
  g.world.on('beginContact',e=>{
    if(!recording)return;
    const a=e.bodyA,b=e.bodyB,all=[g.table.cueBall,...g.table.balls];
    const ab=all.includes(a),bb=all.includes(b);
    const kind=ab&&bb?'ball':((ab&&g.table.rails.includes(b))||(bb&&g.table.rails.includes(a)))?'rail':null;
    if(!kind)return;
    const key=[a.id,b.id].sort((x,y)=>x-y).join(':');
    if(step-(lastContact.get(key)??-100)<4)return;
    const speed=Math.hypot(a.velocity[0]-b.velocity[0],a.velocity[1]-b.velocity[1]);
    if(speed<20)return;lastContact.set(key,step);emit(kind,speed/1800);
  });
  g.worldAnimationMove=function(move){const ok=this._move(move.seat,{...move.data,__psValidationMove:true});if(ok)this.lastState=this.noAnimations;return ok;};
  g.executeAnimation=function(){
    this.poolFrames=recordFrames?[balls(this)]:[];let steps=0;
    step=0;events=[];lastContact.clear();recording=true;
    emit('cue',Math.hypot(...this.table.cueBall.velocity)/2500);
    const live=[this.table.cueBall,...this.table.balls],pocketed=new Set(live.filter(b=>b.isPocketed()));
    this.world.resetAnimationTime();this.world.resetBodiesTimes();this.world.resetAnimationStepsCount();
    do{this.onBeforeStep.emit();this.world.step(this.getFixedTimeStep());this.onAfterStep.emit();steps++;step=steps;for(const b of live)if(b.isPocketed()&&!pocketed.has(b)){pocketed.add(b);emit('pocket',.65);}if(recordFrames&&steps%5===0)this.poolFrames.push(balls(this));}while(!this.isAnimationFinished()&&steps<this.poolMaxSteps);
    if(!this.isAnimationFinished()){
      recording=false;
      throw Object.assign(new Error('Pool physics did not settle; shot rolled back'),{code:'PHYSICS_DID_NOT_SETTLE',statusCode:503});
    }
    recording=false;this.poolSounds=events.map(e=>({...e,t:e.t/Math.max(1,steps)}));
    this.onPreAnimationFinished.emit();this.shotCompleted();this.onAnimationFinished.emit();
    if(recordFrames)this.poolFrames.push(balls(this));
    if(this.poolFrames.length>240){const frames=this.poolFrames;this.poolFrames=Array.from({length:240},(_,i)=>frames[Math.round(i*(frames.length-1)/239)]);}
    this.world.resetAnimationStepsCount();
  };
  g._turnExpire=function(){if(!this.gameOver&&this.turn.length)this.autoMoves([{seat:this.turn[0],data:{a:5}}]);};
}
module.exports={installPoolServer,poolView,validatePoolMove,poolMoveRejectionReason};
