'use strict';

const fs = require('fs');
const path = require('path');
const { GameRuntimeFactory } = require('../gamehost/runtime');

const ROOT = path.join(__dirname, '..');
const EXPECTED_SHA = require('../game/samidev-integrity.json').games.carrom.sha256;
const browserRuntime = fs.readFileSync(path.join(ROOT, 'game', 'browser-runtime.js'), 'utf8');
const factory = new GameRuntimeFactory(path.join(ROOT, 'game'), { expectedSha256: EXPECTED_SHA });
const room = factory.createRoom('STRIKER-MOVE', { players: 0, gamemode: 0, live: 1, break: 0 }, 2, () => {});

function strikerPosition() {
  return Array.isArray(room.logic.table?.striker?.position) ? [...room.logic.table.striker.position] : null;
}

function changed(a, b) {
  return Array.isArray(a) && Array.isArray(b) && (Math.abs(a[0] - b[0]) > 1e-6 || Math.abs(a[1] - b[1]) > 1e-6);
}

function validateShot(seat) {
  const shot = {
    i: `shot-${seat}`,
    m: { m: 5, i: [0, seat === 0 ? 50 : -50], ps: room.logic._strikerLastPos ?? 0.5 },
    n: room.logic._sequence[seat],
  };
  if (!factory.processMove(room, seat, shot).accepted) throw new Error(`shot ${seat} rejected`);
  const info = {
    a: -1,
    idx: room.logic.noAnimations,
    logic: room.logic.getUpdatedGameStateAfterAnimationComplete(false),
    gameOver: false,
    pos: room.logic.getPositionsToValidate(),
    rot: room.logic.getRotationsToValidate(),
    extra: room.logic.getExtraValidationInfo(),
  };
  if (!factory.processMove(room, 0, { __info: structuredClone(info) }).accepted) throw new Error('WorldState 0 rejected');
  if (!factory.processMove(room, 1, { __info: structuredClone(info) }).accepted) throw new Error('WorldState 1 rejected');
}

try {
  const start = { i: 'start', m: { m: 0 }, n: room.logic._sequence[0] };
  if (!factory.processMove(room, 0, start).accepted) throw new Error('start rejected');

  const before0 = strikerPosition();
  const move0 = factory.processMove(room, 0, {
    i: 'move-seat0', m: { m: 6, ps: 0.2 }, n: room.logic._sequence[0],
  });
  const after0 = strikerPosition();
  if (!move0.accepted || !changed(before0, after0)) throw new Error('seat 0 m:6 did not physically move striker');

  validateShot(0);
  if (room.logic.turn[0] !== 1) throw new Error('turn did not pass to seat 1');

  const before1 = strikerPosition();
  const move1 = factory.processMove(room, 1, {
    i: 'move-seat1', m: { m: 6, ps: 0.8 }, n: room.logic._sequence[1],
  });
  const after1 = strikerPosition();
  if (!move1.accepted || !changed(before1, after1)) throw new Error('seat 1 m:6 did not physically move striker');

  // Browser bridge regression: a bare mouse hover must not become a SamiDev touch MOVE;
  // only an active/down pointer is forwarded to the original main.js gesture system.
  const hoverGuard = browserRuntime.includes("state.activePointers.has(pointerId)")
    && browserRuntime.includes("if(dragging) emitTouch(2,ev)")
    && browserRuntime.includes("Array.from(state.activePointers.values(),q=>({id:q.id,x:q.x,y:q.y}))");
  if (!hoverGuard) throw new Error('browser pointer drag guard/clone missing');

  // DOM pointer Y is top-origin, while SamiDev touch events are bottom-origin.
  // main.js InputManager performs the inverse conversion, so the browser bridge
  // must flip touch Y exactly once while leaving MouseManager coordinates unchanged.
  const touchOriginGuard = browserRuntime.includes('function touchPoint(ev)')
    && browserRuntime.includes('y:canvas.height-p.y')
    && browserRuntime.includes('const p=touchPoint(ev)')
    && browserRuntime.includes("function emitMouse(mask, ev) {\n    if(!state.mouse) return;\n    const p=eventPoint(ev);");
  if (!touchOriginGuard) throw new Error('browser SamiDev touch Y-origin conversion missing');

  console.log(JSON.stringify({
    ok: true,
    bundleIntegrityVerified: factory.sha256 === EXPECTED_SHA,
    seat0MoveAccepted: move0.accepted,
    seat0StrikerMoved: changed(before0, after0),
    seat1MoveAccepted: move1.accepted,
    seat1StrikerMoved: changed(before1, after1),
    browserHoverDoesNotEmitTouchMove: hoverGuard,
    browserTouchUsesSamiDevBottomOrigin: touchOriginGuard,
    browserMouseKeepsDomTopOrigin: touchOriginGuard,
    before0, after0, before1, after1,
  }, null, 2));
} finally {
  factory.destroyRoom(room);
}
