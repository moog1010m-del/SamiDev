'use strict';
const path = require('path');
const { GameRuntimeFactory } = require('../gamehost/runtime');

const factory = new GameRuntimeFactory(path.join(__dirname, '..', 'game'), {
  expectedSha256: require('../game/samidev-integrity.json').games.carrom.sha256,
});

const room = factory.createRoom('TURN-REGRESSION', { players: 0, gamemode: 0, live: 1, break: 0 }, 2, () => {});

(async () => {
  try {
    // 1) Start game
    factory.move(room, 0, { i: 'start', m: { m: 0 }, n: room.logic._sequence[0] });
    if (room.logic.turn[0] !== 0) throw new Error(`expected turn 0 at start, got ${room.logic.turn}`);

    // 2) Seat 0 shoots
    const shot1 = { i: 's1', m: { m: 5, i: [0, 50], ps: 0.5 }, n: room.logic._sequence[0] };
    const shot1Res = factory.processMove(room, 0, shot1);
    if (!shot1Res.accepted) throw new Error('shot 1 was not accepted by server');

    // 3) Both seats send WorldState animation info
    const anim1 = room.logic.noAnimations;
    const info1 = {
      a: -1, idx: anim1,
      logic: { scores: [0, 0], queenState: 0, fouls: [], resetQueen: false, penalties: [], reason: -1 },
      pos: room.logic.getPositionsToValidate(), rot: room.logic.getRotationsToValidate(), extra: room.logic.getExtraValidationInfo(),
    };
    factory.processMove(room, 0, { __info: structuredClone(info1) });
    factory.processMove(room, 1, { __info: structuredClone(info1) });
    if (!shot1Res.revealBySeat || !shot1Res.revealBySeat['0'] || !shot1Res.revealBySeat['1']) {
      throw new Error('revealBySeat missing from server physics result');
    }

    // 4) Authoritative turn must now be Seat 1
    if (room.logic.turn[0] !== 1) throw new Error(`expected turn 1 after shot 1, got ${room.logic.turn}`);
    if (!room.logic.canShoot(1)) throw new Error('canShoot(1) is false on server after turn change');

    // 5) Seat 1 takes the second shot
    const shot2 = { i: 's2', m: { m: 5, i: [0, -50], ps: 0.5 }, n: room.logic._sequence[1] };
    const shot2Res = factory.processMove(room, 1, shot2);
    if (!shot2Res.accepted) throw new Error('shot 2 from seat 1 was not accepted by server');

    // 6) Both seats send WorldState animation info for shot 2
    const anim2 = room.logic.noAnimations;
    const info2 = {
      a: -1, idx: anim2,
      logic: { scores: [0, 0], queenState: 0, fouls: [], resetQueen: false, penalties: [], reason: -1 },
      pos: room.logic.getPositionsToValidate(), rot: room.logic.getRotationsToValidate(), extra: room.logic.getExtraValidationInfo(),
    };
    factory.processMove(room, 0, { __info: structuredClone(info2) });
    factory.processMove(room, 1, { __info: structuredClone(info2) });

    // 7) Authoritative turn must now be Seat 0
    if (room.logic.turn[0] !== 0) throw new Error(`expected turn 0 after shot 2, got ${room.logic.turn}`);
    if (!room.logic.canShoot(0)) throw new Error('canShoot(0) is false on server after turn change');

    console.log(JSON.stringify({
      ok: true,
      turnTransitionVerified: true,
      seat0ShotAccepted: true,
      turnPassedToSeat1: true,
      seat1ShotAccepted: true,
      turnPassedBackToSeat0: true,
    }, null, 2));
  } finally {
    factory.destroyRoom(room);
  }
})().catch(e => {
  console.error(e.stack || e);
  process.exitCode = 1;
});
