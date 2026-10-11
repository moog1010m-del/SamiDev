'use strict';
const path = require('path');
const { GameRuntimeFactory } = require('../gamehost/runtime');
const EXPECTED_SHA = require('../game/samidev-integrity.json').games.carrom.sha256;
const settings = { players: 0, gamemode: 0, live: 1, break: 0 };
const factory = new GameRuntimeFactory(path.join(__dirname, '..', 'game'), { expectedSha256: EXPECTED_SHA });

function makeObserver() {
  const host = factory._baseHostApi();
  host.ownerSeat = () => -1;
  host.setTimer = () => 0;
  host.clearTimer = () => {};
  let outbound = 0;
  host.sendMove = () => { outbound += 1; };
  factory.context.SamiDev = host;
  const logic = new factory.GameLogicCtor();
  logic.initialize(settings, -1);
  logic.onSetAlarm = () => {};
  for (let seat = 0; seat < 2; seat++) logic.enter(seat);
  logic._initialSync = true;
  return { host, logic, outbound: () => outbound };
}

const room = factory.createRoom('OBSERVER-REG', settings, 2, () => {});
const observer = makeObserver();
const start = { i: 'observer-start', m: { m: 0 }, n: room.logic._sequence[0] };
const authoritative = factory.processMove(room, 0, structuredClone(start));
factory.context.SamiDev = observer.host;
const applied = observer.logic.move(0, structuredClone(start), structuredClone(authoritative.revealBySeat?.['0']));
const report = {
  observer: observer.logic.isLocalObserver?.() === true,
  localSeat: observer.logic.localSeat,
  server: observer.logic.server,
  moveApplied: applied === true,
  outboundMoves: observer.outbound(),
};
report.ok = report.observer && report.localSeat === -1 && report.server === false && report.moveApplied && report.outboundMoves === 0;
console.log(JSON.stringify(report, null, 2));
factory.destroyRoom(room);
if (!report.ok) process.exitCode = 2;
