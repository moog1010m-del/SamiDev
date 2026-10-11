'use strict';
const path = require('path');
const { GameRuntimeFactory } = require('../gamehost/runtime');

const factory = new GameRuntimeFactory(path.join(__dirname, '..', 'game'), {
  expectedSha256: require('../game/samidev-integrity.json').games.carrom.sha256,
});

let passed = 0, failed = 0;
const failures = [];
function check(ok, label, detail) {
  if (ok) passed++; else { failed++; failures.push({ label, detail }); }
}

let idx = 0;
for (const players of [0, 1]) {
  for (const gamemode of [0, 1, 2, 3, 4]) {
    for (const live of [0, 1]) {
      for (const brk of [0, 1, 2]) {
        const settings = { players, gamemode, live, break: brk === 2 ? 0 : brk };
        const cap = players === 1 ? 4 : 2;
        const room = factory.createRoom(`M${idx++}`, settings, cap, () => {});
        try {
          check(room.logic.server === true, 'server mode', settings);
          const n0 = room.logic._sequence[0];
          const start = { i: `start-${idx}`, m: { m: 0 }, n: n0 };
          check(factory.move(room, 0, structuredClone(start)) === true, 'start accepted', settings);
          const turn = room.logic.turn[0];
          check(Number.isInteger(turn), 'turn selected', { settings, turn: room.logic.turn });
          const wrong = (turn + 1) % cap;
          const wrongPacket = { i: `wrong-${idx}`, m: { m: 6, ps: 0 }, n: room.logic._sequence[wrong] };
          check(factory.move(room, wrong, wrongPacket) === false, 'wrong turn rejected', { settings, turn, wrong });
          const dup = { i: `dup-${idx}`, m: { m: 6, ps: 0 }, n: n0 };
          check(factory.move(room, 0, dup) === false, 'duplicate sequence rejected', settings);
          const snap = factory.describeRoom(room, true).snapshot;
          check(snap && Array.isArray(snap.n) && snap.s === cap, 'server snapshot', settings);
        } catch (e) {
          check(false, 'exception', { settings, error: String(e.stack || e) });
        } finally {
          factory.destroyRoom(room);
        }
      }
    }
  }
}

// Server physics completes the shot; client WorldState is only acknowledged.
{
  const room = factory.createRoom('PHYSICS', { players: 0, gamemode: 0, live: 1, break: 0 }, 2, () => {});
  try {
    factory.move(room, 0, { i: 'physics-start', m: { m: 0 }, n: room.logic._sequence[0] });
    const seat = room.logic.turn[0];
    const shotEffects = factory.processMove(room, seat, {i:'physics-shot', n:room.logic._sequence[seat], m:{m:5,i:[10,0]}});
    check(shotEffects.accepted === true, 'server physics shot accepted');
    const animIdx = room.logic.noAnimations;
    const payload = {
      a: -1,
      idx: animIdx,
      logic: room.logic.getUpdatedGameStateAfterAnimationComplete(false),
      gameOver: false,
      pos: room.logic.getPositionsToValidate(),
      rot: room.logic.getRotationsToValidate(),
      extra: room.logic.getExtraValidationInfo(),
    };
    let finalEffects = null;
    for (let seat = 0; seat < 2; seat++) {
      const p = { __info: structuredClone(payload) };
      const result = factory.processMove(room, seat, p);
      finalEffects = result;
      check(result.accepted === true, `WorldState info seat ${seat}`);
      check(p.__info === 1, `WorldState ack seat ${seat}`);
    }
    check(room.logic.lastValidAnim === room.logic.noAnimations, 'server physics completed', { lastValidAnim: room.logic.lastValidAnim });
    check(shotEffects.revealBySeat['0'], 'authoritative reveal captured for seat 0');
    check(shotEffects.revealBySeat['1'], 'authoritative reveal captured for seat 1');
    check(shotEffects.revealBySeat['0']?.rid === 0, 'reveal payload keeps revelation id');
  } finally {
    factory.destroyRoom(room);
  }
}

const report = {
  ok: failed === 0,
  mainJsSha256: factory.sha256,
  settingsCombinations: 60,
  checksPassed: passed,
  checksFailed: failed,
  failures,
  memory: (()=>{try{return process.memoryUsage();}catch{return null;}})(),
};
console.log(JSON.stringify(report, null, 2));
process.exitCode = failed ? 1 : 0;
