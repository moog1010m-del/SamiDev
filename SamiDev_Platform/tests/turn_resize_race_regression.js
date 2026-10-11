'use strict';

const path = require('path');
const crypto = require('crypto');
const fs = require('fs');
const { GameRuntimeFactory } = require('../gamehost/runtime');

const EXPECTED_SHA = require('../game/samidev-integrity.json').games.carrom.sha256;
const settings = { players: 0, gamemode: 0, live: 1, break: 0 };
const sleep = ms => new Promise(r => setTimeout(r, ms));
const factory = new GameRuntimeFactory(path.join(__dirname, '..', 'game'), { expectedSha256: EXPECTED_SHA });

const main = fs.readFileSync(path.join(__dirname, '..', 'game', 'main.js'));
if (crypto.createHash('sha256').update(main).digest('hex') !== EXPECTED_SHA) throw new Error('main.js changed');

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
    timers.set(id, {handle, repeat});
    return id;
  };
  host.clearTimer = id => {
    const item = timers.get(id); if (!item) return;
    item.repeat ? clearInterval(item.handle) : clearTimeout(item.handle);
    timers.delete(id);
  };
  host.sendMove = () => {};
  factory.context.SamiDev = host;
  const logic = new factory.GameLogicCtor();
  logic.initialize(settings, seat);
  logic.onSetAlarm = () => {};
  for (let s = 0; s < 2; s++) logic.enter(s);
  logic._initialSync = true;
  return {seat, host, logic, timers};
}

function activate(c) { factory.context.SamiDev = c.host; }
function destroy(c) {
  for (const item of c.timers.values()) item.repeat ? clearInterval(item.handle) : clearTimeout(item.handle);
  c.timers.clear();
}

async function nextAlarm(room, events) {
  const id = Number(room.logic._nextAlarmId);
  const before = events.length;
  factory._scheduleAlarm(room, 5, id);
  for (let i=0;i<80;i++) {
    const event = events.slice(before).find(e => e.type === 'authority_alarm' && Number(e.alarmId) === id);
    if (event) return event;
    await sleep(10);
  }
  throw new Error('authority alarm timeout');
}

(async () => {
  const events=[];
  const room=factory.createRoom('RESIZE-RACE',settings,2,e=>events.push(structuredClone(e)));
  const broken=makeClient(0);
  const fixed=makeClient(0);
  try {
    const start={i:'start',m:{m:0},n:0};
    if(!factory.processMove(room,0,structuredClone(start)).accepted) throw new Error('server start rejected');
    for(const c of [broken,fixed]) { activate(c); if(!c.logic.move(0,structuredClone(start))) throw new Error('client start rejected'); }

    const alarm=await nextAlarm(room,events);
    for(const c of [broken,fixed]) {
      activate(c);
      if(!c.logic.alarm(structuredClone(alarm.revealBySeat['0']),alarm.alarmId)) throw new Error('alarm rejected');
    }

    // Reproduce Game.surfaceChange()->Game.sync()->CarromLogic.onSync() inside the native
    // ON_TURN_MISSED=500ms window. The control client keeps the sync flag; the repaired path
    // restores the pre-resize false flag because a visual resize is not an authoritative sync.
    await sleep(100);
    activate(broken);
    broken.logic.onSync(broken.logic.localSeat);

    activate(fixed);
    const before = fixed.logic._syncCalledFlag;
    fixed.logic.onSync(fixed.logic.localSeat);
    if (before === false && fixed.logic._syncCalledFlag === true) fixed.logic._syncCalledFlag = false;

    await sleep(620);
    const report={
      ok: room.logic.turn[0]===1 && broken.logic.turn[0]===0 && fixed.logic.turn[0]===1,
      serverTurn: room.logic.turn[0],
      brokenClientTurn: broken.logic.turn[0],
      repairedClientTurn: fixed.logic.turn[0],
      sameSequenceBroken: JSON.stringify(room.logic._sequence)===JSON.stringify(broken.logic._sequence),
      sameSequenceRepaired: JSON.stringify(room.logic._sequence)===JSON.stringify(fixed.logic._sequence),
      bundleIntegrityVerified: true,
    };
    console.log(JSON.stringify(report,null,2));
    if(!report.ok) process.exitCode=2;
  } finally {
    destroy(broken); destroy(fixed); factory.destroyRoom(room);
  }
})().catch(e=>{console.error(e.stack||e);process.exitCode=1;});
