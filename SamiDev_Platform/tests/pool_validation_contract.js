'use strict';
const assert = require('node:assert/strict');
const {GameRuntimeFactory} = require('../gamehost/runtime');
const f = new GameRuntimeFactory(require('node:path').join(__dirname, '../game/games/pool'), {gameId:'pool'});
const copy = value => JSON.parse(JSON.stringify(value));
let cases = 0;
function fixture(mode, run) {
  const room = f.createRoom('VALIDATE', {gameType:mode, live:1, break:0, trickShots:0}, [2,4,4,2,4,4,3,2][mode], () => {});
  try {
    f.processMove(room, 0, {i:'ready', n:0, m:{__ready:1}});
    const snapshot = f.describeRoom(room, true).snapshot;
    const client = new f.GameLogicCtor();
    client.initialize(room.settings, 0);
    client.deserialize(copy(snapshot), 0);
    run(room, client, snapshot);
    cases++;
  } finally { f.destroyRoom(room); }
}

// Exercise native client validation, in either arrival order, without changing
// its sequence or replacing the detector. Only corrupt the state under test.
for (const serverFirst of [false, true]) {
  for (const field of ['freePoolScores', 'freePoolPocketed']) {
    fixture(7, (room, client, snapshot) => {
      const trusted = copy(room.logic.getExtraValidationInfo());
      const beforePositions = copy(client.getPositionsToValidate());
      if (field === 'freePoolScores') client.freePoolScores[0] = 1;
      else client.freePoolPocketed.push(8);
      const local = copy(client.getExtraValidationInfo());
      assert(!client.validateExtraInfo(trusted, local), `${field} drift must be detected`);
      const reveal = () => client.validateAnimationClient(true, 1, beforePositions, undefined, trusted);
      const finish = () => client.validateAnimationClient(false, 1, beforePositions, undefined, local);
      if (serverFirst) { reveal(); finish(); } else { finish(); reveal(); }
      assert(client._awaitingResync, 'native mismatch requests recovery');
      assert.deepEqual(copy(client.getPositionsToValidate()), beforePositions, 'positions did not cause the mismatch');
      client.deserialize(copy(snapshot), 0);
      assert(!client._awaitingResync);
      assert.deepEqual(copy(client.freePoolScores), copy(room.logic.freePoolScores));
      assert.deepEqual(copy(client.freePoolPocketed), copy(room.logic.freePoolPocketed));
      assert.deepEqual(copy(client._sequence), copy(room.logic._sequence), 'recovery uses native snapshot sequence');
    });
  }
}

fixture(7, (room, client) => {
  const trusted = copy(room.logic.getExtraValidationInfo());
  client.validateAnimationClient(true, 1, undefined, undefined, trusted);
  client.validateAnimationClient(false, 1, undefined, undefined, copy(client.getExtraValidationInfo()));
  assert(!client._awaitingResync, 'matching Game Pool state needs no recovery');
  const captured = client.getExtraValidationInfo();
  client.freePoolScores[0]++;
  client.freePoolPocketed.push(8);
  assert.deepEqual(copy(captured.freePoolScores), [0,0], 'validation captures an immutable score snapshot');
  assert.deepEqual(copy(captured.freePoolPocketed), [], 'validation captures an immutable credited-ball snapshot');
});

fixture(7, (room, client) => {
  room.logic.freePoolScores = [2,0]; client.freePoolScores = [2,0];
  room.logic.freePoolPocketed = [8,1]; client.freePoolPocketed = [1,8];
  const trusted = copy(room.logic.getExtraValidationInfo());
  assert(client.validateExtraInfo(trusted, client.getExtraValidationInfo()), 'credited-ball order is not a score difference');
  const missing = copy(trusted); delete missing.freePoolScores;
  assert(!client.validateExtraInfo(missing, trusted), 'missing score metadata must not silently validate');
});

for (let mode = 0; mode < 7; mode++) fixture(mode, (room, client) => {
  const extra = copy(room.logic.getExtraValidationInfo());
  assert(!Object.hasOwn(extra, 'freePoolScores'), 'standard modes preserve native metadata');
  client.validateAnimationClient(true, 1, undefined, undefined, extra);
  client.validateAnimationClient(false, 1, undefined, undefined, copy(client.getExtraValidationInfo()));
  assert(!client._awaitingResync, `mode ${mode} validates normally`);
});
console.log(JSON.stringify({ok:true, cases, contract:'native pool result validation and snapshot recovery'}));
