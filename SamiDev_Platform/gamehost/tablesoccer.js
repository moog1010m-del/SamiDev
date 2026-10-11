'use strict';

// Bind the bundled rules to a server-only host. Browser scene callbacks are
// intentionally never installed in the authoritative process.
function installTableSoccerServer(logic) {
  const Animator = logic.constructor.SamiDevServerAnimator;
  if (typeof Animator !== 'function') throw new Error('SamiDev Table Soccer server animator missing');
  const animator = new Animator(logic, logic.gsMgr.MAX_ITERATIONS);
  logic.executeAnimation = () => animator.executeAnimation();
  logic.animateShot = () => logic.animateWorld();
  logic._ready = () => logic.setTurnDuration(logic._turnDuration);
  logic._selectTeam = function(seat, team) {
    const index = this.getAssignedTeam(seat);
    if (this.teamFlags[1 - index] !== team) this.teamFlags[index] = team;
  };
  // Execute physics on the server. Client world reports cannot decide scores,
  // positions or winners, and every accepted shot has a complete checkpoint.
  logic.worldAnimationMove = function(move) {
    const accepted = this._move(move.seat, {...move.data, __psValidationMove:true});
    if (accepted) this.lastState = this.noAnimations;
    return accepted;
  };
  const complete = logic._animationCompleted;
  logic._animationCompleted = function() {
    this.stadium.fixOutOfBoundsPosition(this.stadium.ball);
    return complete.call(this);
  };
  logic._turnExpire = function() {
    if (this.gameOver) return;
    if (!this.areTeamsSelected()) {
      for (let seat = 0; seat < this.seats; seat++) {
        if (this.isCaptain(seat) && this.teamFlags[this.getAssignedTeam(seat)] === -1) {
          const other = this.teamFlags[1-this.getAssignedTeam(seat)];
          const team = ['Red.c.h','Blue.c.h'].find(value=>value!==other);
          this.autoMoves([{seat, data:{a:this.GAME_ACTIONS.SELECT_TEAM, team}}]);
        }
      }
      return;
    }
    this.autoMoves([...this.turn].map(seat => ({seat, data:{a:this.GAME_ACTIONS.MISS_TURN}})));
  };
}

module.exports = {installTableSoccerServer};
