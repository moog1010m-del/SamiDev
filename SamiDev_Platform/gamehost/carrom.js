'use strict';

// Clients may animate a shot locally, but only server physics determines its
// final positions, fouls, queen state, score and next turn.
function installCarromServer(logic) {
  logic.worldAnimationMove = function(move) {
    const accepted = this._move(move.seat, {...move.data, __psValidationMove:true});
    if (accepted) this.lastState = this.noAnimations;
    return accepted;
  };
  logic.animationCompleted = function(missed = false) {
    const result = this.getUpdatedGameStateAfterAnimationComplete(missed);
    this._bufferExitEnter = false;
    this.nextTurnAfterShotCompleted(result, missed);
  };
  logic.executeAnimation = function() {
    const world = this.world;
    world.resetAnimationTime();
    world.resetBodiesTimes();
    world.resetAnimationStepsCount();
    // Bound each simulation even if the physics engine fails to settle.
    const maxSteps = 12000;
    let steps = 0;
    do {
      this.onBeforeStep.emit();
      world.step(this.getFixedTimeStep());
      this.onAfterStep.emit();
      steps++;
    } while (!this.isAnimationFinished() && steps < maxSteps);
    // The native completion hook stops and rounds bodies. Never install the
    // browser's delayed completion callback in the authoritative process.
    this.onPreAnimationFinished.emit();
    this.finalizeAnimation();
    this.animationCompleted(false);
    world.resetAnimationStepsCount();
  };
}

module.exports = {installCarromServer};
