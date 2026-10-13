/* Original shared Pyramid rules; same implementation in browser and authority. */
globalThis.SamiDevPyramidRules = Object.freeze({
  create(mode) {
    return mode === 8 || mode === 9 ? {mode, scores:[0,0], ids:Array.from({length:16},(_,i)=>i), credited:[], canSelect:true, lastSelection:null} : null;
  },
  serialize(logic) { return logic.pyramid ? JSON.parse(JSON.stringify(logic.pyramid)) : null; },
  canSelect(logic, seat, rank) {
    return !!logic.pyramid && logic.pyramid.canSelect && !logic.gameOver && logic.started && logic.isTurn(seat)
      && logic.canShoot(seat) && Number.isInteger(rank) && rank >= 1 && rank <= 15
      && !logic.table.balls[rank-1].isPocketed() && !logic.table.cueBall.isSinking();
  },
  selectCue(logic, seat, rank, automatic=false) {
    const state=logic.pyramid;
    if (!state) return false;
    // Optimistic client confirmation repeats the same action without swapping again.
    if (!automatic && !state.canSelect && state.lastSelection?.seat===seat && state.lastSelection?.rank===rank) return true;
    if (!automatic && !this.canSelect(logic,seat,rank)) return false;
    const cue=logic.table.cueBall,other=logic.table.balls[rank-1];
    if (!other || other.isPocketed()) return false;
    const oldCuePocketed=cue.isPocketed(),oldPosition=Array.from(cue.position),nextPosition=Array.from(other.position);
    [state.ids[0],state.ids[rank]]=[state.ids[rank],state.ids[0]];
    cue.sinking=undefined;cue.setCollidingWithBallsAndRails(true);cue.setPosition(nextPosition);cue.wakeUp();
    if (oldCuePocketed) other.setPocketed();
    else {other.setPosition(oldPosition);other.wakeUp();}
    for (const body of [cue,other]) {body.velocity[0]=body.velocity[1]=0;body.angularVelocity=0;body.setZeroForce();body.aabbNeedsUpdate=true;}
    if (!automatic) {state.canSelect=false;state.lastSelection={seat,rank};}
    logic.ballInHand=0;
    logic.onSynchronize?.emit?.();
    return true;
  },
  restore(logic,body) {
    body.sinking=undefined;body.setCollidingWithBallsAndRails(true);
    body.velocity[0]=body.velocity[1]=0;body.angularVelocity=0;body.setZeroForce();
    logic.table.spotBall(body,417,418,false,true);body.aabbNeedsUpdate=true;body.wakeUp();
  },
  finishShot(logic,outcome) {
    const state=logic.pyramid,seat=logic.turn[0],cue=logic.table.cueBall;
    const legal=cue.getFirstContact()>=1&&cue.getFirstContact()<=15;
    const cueSunk=cue.isPocketed(),objects=logic.table.getJustPocketed().slice();
    const candidates=state.mode===9?(cueSunk?[cue]:[]):[...objects,...(cueSunk?[cue]:[])];
    let added=0;
    if (legal) for (const body of candidates) {
      const id=state.ids[body.getRank()];
      if (!state.credited.includes(id)) {state.credited.push(id);state.scores[seat]++;added++;}
    }
    // In Scratch Pyramid, object balls never score and return to the foot spot.
    for (const body of objects)if (!legal||state.mode===9)this.restore(logic,body);
    if (cueSunk && !legal)this.restore(logic,cue);
    state.canSelect=true;state.lastSelection=null;
    logic.solids=-1;logic.ballInHand=0;
    outcome.numberOfPocketed=added;outcome.pocketedBallsAreWrong=false;
    if (state.scores[seat]>=8) {logic.handleEndGame(seat);return;}
    if (cue.isPocketed()) {
      const next=logic.table.balls.find(ball=>!ball.isPocketed());
      if (next)this.selectCue(logic,seat,next.getRank(),true);
    }
    logic.nextTurnAfterShotCompleted(false,added,false);
  },
});
