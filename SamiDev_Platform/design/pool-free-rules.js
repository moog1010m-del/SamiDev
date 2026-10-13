/* Shared original Game Pool rules, embedded in the client and authoritative engine. */
globalThis.SamiDevFreePoolRules = Object.freeze({
  finishShot(logic, outcome) {
    const seat = logic.turn[0];
    let added = 0;
    for (const ball of logic.table.getJustPocketed()) {
      const rank = ball.getRank();
      if (rank >= 1 && rank <= 15 && !logic.freePoolPocketed.includes(rank)) {
        logic.freePoolPocketed.push(rank);
        logic.freePoolScores[seat] += 1;
        added += 1;
      }
    }
    // The cue ball never counts. A scratch gives the next player ball in hand;
    // numbered balls still count, including the black eight, in this casual mode.
    const scratch = logic.table.cueBall.isPocketed();
    logic.solids = -1;
    logic.ballInHand = scratch ? 5 : 0;
    outcome.numberOfPocketed = added;
    outcome.pocketedBallsAreWrong = false;
    if (scratch) logic.table.setCueBallBIHPos(417, 758, true);
    if (logic.freePoolScores[seat] >= 8) logic.handleEndGame(seat);
    else logic.nextTurnAfterShotCompleted(false, added, false);
  },
});
