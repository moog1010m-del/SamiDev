'use strict';
const path = require('path');
const { GameRuntimeFactory } = require('../gamehost/runtime');

const factory = new GameRuntimeFactory(path.join(__dirname, '..', 'game'), {
  expectedSha256: require('../game/samidev-integrity.json').games.carrom.sha256,
});

const emitted = [];
const room = factory.createRoom('ALARM-REGRESSION', { players: 0, gamemode: 0, live: 1, break: 0 }, 2, ev => emitted.push(ev));

function sleep(ms){ return new Promise(r=>setTimeout(r,ms)); }

(async()=>{
  try {
    // 1) A host timer whose id is no longer pending must never enter BaseLogic or reach clients.
    const expected = Number(room.logic._nextAlarmId || 0);
    const staleId = expected + 100;
    factory._scheduleAlarm(room, 5, staleId);
    await sleep(25);
    const staleBroadcast = emitted.some(e => e && e.type === 'authority_alarm' && Number(e.alarmId) === staleId);
    const staleIgnored = room.events.some(e => e.type === 'stale_alarm_ignored' && Number(e.id) === staleId);
    if (staleBroadcast) throw new Error('stale authority alarm was broadcast');
    if (!staleIgnored) throw new Error('stale authority alarm was not recorded as ignored');

    // 2) Replacing an alarm must cancel the older host timer immediately.
    room.logic._pendingAlarm = true;
    room.logic._nextAlarmId = 1001;
    factory._scheduleAlarm(room, 100, 1001);
    room.logic._nextAlarmId = 1002;
    factory._scheduleAlarm(room, 100, 1002);
    if (room.timers.has(1001)) throw new Error('superseded alarm timer remained registered');
    if (!room.timers.has(1002)) throw new Error('replacement alarm timer missing');
    const superseded = room.events.some(e => e.type === 'alarm_superseded' && Number(e.id) === 1001 && Number(e.by) === 1002);
    if (!superseded) throw new Error('superseded alarm was not recorded');

    console.log(JSON.stringify({
      ok: true,
      staleAlarmBroadcast: false,
      staleAlarmIgnored: true,
      supersededTimerCancelled: true,
      events: room.events.filter(e => ['stale_alarm_ignored','alarm_superseded'].includes(e.type)),
    }, null, 2));
  } finally {
    factory.destroyRoom(room);
  }
})().catch(e=>{ console.error(e.stack||e); process.exitCode=1; });
