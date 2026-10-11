'use strict';

const path = require('path');
const { GameRuntimeFactory } = require('../gamehost/runtime');

const EXPECTED_SHA = require('../game/samidev-integrity.json').games.carrom.sha256;
const settings = { players: 0, gamemode: 0, live: 1, break: 0 };
const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

const factory = new GameRuntimeFactory(path.join(__dirname, '..', 'game'), { expectedSha256: EXPECTED_SHA });

function makeClient(seat) {
  const host = factory._baseHostApi();
  const timers = new Map();
  let nextTimer = 1;
  host.ownerSeat = () => seat;
  host.setTimer = (fn, ms, repeat = false) => {
    const id = nextTimer++;
    const fire = () => {
      if (!repeat) timers.delete(id);
      factory.context.SamiDev = host;
      fn();
    };
    const handle = repeat ? setInterval(fire, ms) : setTimeout(fire, ms);
    timers.set(id, { handle, repeat });
    return id;
  };
  host.clearTimer = (id) => {
    const item = timers.get(id);
    if (!item) return;
    item.repeat ? clearInterval(item.handle) : clearTimeout(item.handle);
    timers.delete(id);
  };
  const outbound = [];
  host.sendMove = packet => outbound.push(structuredClone(packet));
  factory.context.SamiDev = host;
  const logic = new factory.GameLogicCtor();
  logic.initialize(settings, seat);
  logic.onSetAlarm = () => {}; // online browser: server owns BaseLogic alarms
  for (let s = 0; s < 2; s++) logic.enter(s);
  logic._initialSync = true;
  return { seat, host, logic, timers, outbound };
}

function destroyClient(client) {
  for (const item of client.timers.values()) {
    item.repeat ? clearInterval(item.handle) : clearTimeout(item.handle);
  }
  client.timers.clear();
}

function activateClient(client) {
  factory.context.SamiDev = client.host;
}

function applyPacket(client, seat, packet, reveal) {
  activateClient(client);
  return client.logic.move(seat, structuredClone(packet), structuredClone(reveal));
}

function shootAndValidate(room, seat, label) {
  const packet = {
    i: label,
    m: { m: 5, i: [0, seat === 0 ? 50 : -50], ps: 0.5 },
    n: room.logic._sequence[seat],
  };
  const shot = factory.processMove(room, seat, packet);
  if (!shot.accepted) throw new Error(`shot rejected for seat ${seat}`);
  const idx = room.logic.noAnimations;
  const info = {
    a: -1,
    idx,
    logic: room.logic.getUpdatedGameStateAfterAnimationComplete(false),
    gameOver: false,
    pos: room.logic.getPositionsToValidate(),
    rot: room.logic.getRotationsToValidate(),
    extra: room.logic.getExtraValidationInfo(),
  };
  const a = factory.processMove(room, 0, { __info: structuredClone(info) });
  const b = factory.processMove(room, 1, { __info: structuredClone(info) });
  if (!a.accepted || !b.accepted) throw new Error('WorldState validation rejected');
}

async function expireCurrentTurn(room, events) {
  const id = Number(room.logic._nextAlarmId);
  const before = events.length;
  factory._scheduleAlarm(room, 5, id);
  for (let i = 0; i < 60; i++) {
    const event = events.slice(before).find(e => e.type === 'authority_alarm' && Number(e.alarmId) === id);
    if (event) return event;
    await sleep(10);
  }
  throw new Error(`authority_alarm ${id} did not fire`);
}

(async () => {
  const results = {};

  // A) The authoritative alarm must carry BaseLogic.autoMoves() reveal and both
  // client replicas must execute the same missed-turn path.
  const events = [];
  const room = factory.createRoom('TIMEOUT-REPL', settings, 2, e => events.push(structuredClone(e)));
  const c0 = makeClient(0);
  const c1 = makeClient(1);
  try {
    const start = { i: 'start', m: { m: 0 }, n: room.logic._sequence[0] };
    if (!factory.processMove(room, 0, structuredClone(start)).accepted) throw new Error('server start rejected');
    if (!applyPacket(c0, 0, start) || !applyPacket(c1, 0, start)) throw new Error('client start rejected');

    const alarm = await expireCurrentTurn(room, events);
    const auto0 = alarm.revealBySeat?.['0']?.__auto;
    const auto1 = alarm.revealBySeat?.['1']?.__auto;
    results.alarmContainsNativeAutoMove = Array.isArray(auto0) && Array.isArray(auto1)
      && auto0[0]?.d?.m === 3 && auto0[0]?.d?.__auto === 1 && auto0[0]?.s === 0;
    if (!results.alarmContainsNativeAutoMove) throw new Error('authority alarm is missing native __auto m:3');

    for (const client of [c0, c1]) {
      activateClient(client);
      const reveal = alarm.revealBySeat[String(client.seat)];
      if (!client.logic.alarm(structuredClone(reveal), alarm.alarmId)) throw new Error(`client ${client.seat} rejected authority alarm`);
    }

    await sleep(620); // native Carrom ON_TURN_MISSED = 500ms
    results.serverTurnAfterTimeout = room.logic.turn[0];
    results.client0TurnAfterTimeout = c0.logic.turn[0];
    results.client1TurnAfterTimeout = c1.logic.turn[0];
    results.sequenceMirrored = JSON.stringify(room.logic._sequence) === JSON.stringify(c0.logic._sequence)
      && JSON.stringify(room.logic._sequence) === JSON.stringify(c1.logic._sequence);
    results.timeoutReplicated = results.serverTurnAfterTimeout === 1
      && results.client0TurnAfterTimeout === 1
      && results.client1TurnAfterTimeout === 1
      && results.sequenceMirrored;
    if (!results.timeoutReplicated) throw new Error(`timeout did not replicate: ${JSON.stringify(results)}`);
  } finally {
    destroyClient(c0);
    destroyClient(c1);
    factory.destroyRoom(room);
  }

  // B) Use the same native timeout path three times for one seat, with a real
  // opponent shot between misses. main.js must perform the AFK resignation itself.
  const afkEvents = [];
  const afkRoom = factory.createRoom('AFK-NATIVE', settings, 2, e => afkEvents.push(structuredClone(e)));
  try {
    const start = { i: 'afk-start', m: { m: 0 }, n: afkRoom.logic._sequence[0] };
    if (!factory.processMove(afkRoom, 0, start).accepted) throw new Error('AFK start rejected');

    for (let miss = 1; miss <= 3; miss++) {
      if (afkRoom.logic.turn[0] !== 0) throw new Error(`expected seat 0 before miss ${miss}, got ${afkRoom.logic.turn}`);
      await expireCurrentTurn(afkRoom, afkEvents);
      if (miss < 3) {
        await sleep(560);
        if (afkRoom.logic.turn[0] !== 1) throw new Error(`timeout ${miss} did not pass turn to seat 1`);
        shootAndValidate(afkRoom, 1, `opponent-shot-${miss}`);
        if (afkRoom.logic.turn[0] !== 0) throw new Error(`opponent shot ${miss} did not return turn to seat 0`);
      }
    }

    results.maxAutoMovesPerSeat = afkRoom.logic.maxAutoMovesPerSeat;
    results.maxConsecutiveAutoMoves = afkRoom.logic.maxConsecutiveAutoMoves;
    results.autoMovesPerSeat = [...afkRoom.logic._autoMovesPerSeat];
    results.resignedSeats = [...afkRoom.logic.resignedSeats];
    results.gameOverAfterThirdMiss = !!afkRoom.logic.gameOver;
    results.gameOverMessage = afkRoom.lastGameOver?.[1] || null;
    results.nativeAfkForfeit = results.maxAutoMovesPerSeat === 3
      && results.maxConsecutiveAutoMoves === 4
      && results.autoMovesPerSeat[0] === 3
      && results.resignedSeats.includes(0)
      && results.gameOverAfterThirdMiss
      && Array.isArray(results.gameOverMessage)
      && results.gameOverMessage[0] === 'go_resigned_observer';
    if (!results.nativeAfkForfeit) throw new Error(`native AFK forfeit failed: ${JSON.stringify(results)}`);
  } finally {
    factory.destroyRoom(afkRoom);
  }

  results.ok = results.timeoutReplicated && results.nativeAfkForfeit;
  console.log(JSON.stringify(results, null, 2));
})().catch(err => {
  console.error(err.stack || err);
  process.exitCode = 1;
});
