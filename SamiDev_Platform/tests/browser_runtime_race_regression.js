#!/usr/bin/env node
'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const crypto = require('crypto');

const root = path.resolve(__dirname, '..');
const browser = fs.readFileSync(path.join(root, 'game', 'browser-runtime.js'), 'utf8');
const main = fs.readFileSync(path.join(root, 'game', 'main.js'));
assert.strictEqual(
  crypto.createHash('sha256').update(main).digest('hex'),
  require('../game/samidev-integrity.json').games.carrom.sha256,
  'main.js must match the SamiDev integrity manifest'
);

// --- Surface startup + resize turn-race regression ---
const resizeStart = browser.indexOf('  function resize() {');
const resizeEnd = browser.indexOf('  function eventPoint(ev) {', resizeStart);
assert(resizeStart >= 0 && resizeEnd > resizeStart);
const resizeSource = browser.slice(resizeStart, resizeEnd);
let now = 0;
let rectCalls = 0;
let surfaceCalls = 0;
const logic = {_syncCalledFlag: false};
const canvas = {
  width: 0,
  height: 0,
  getBoundingClientRect() {
    rectCalls++;
    if (rectCalls <= 3) return {width: 1, height: 1};
    return {width: 640, height: 480};
  }
};
const state = {
  gameLogic: logic,
  network: {online: true, snapshotBusy: false},
  surface: {w:0,h:0,menuY:0,initialized:false},
  surfaceChanged() { surfaceCalls++; logic._syncCalledFlag = true; },
  frameRequested: false,
  performance: {},
};
const resizeCtx = {
  canvas,
  state,
  devicePixelRatio: 1,
  mobileDevice: false,
  isCarrom: false,
  runtimeDebug: false,
  console,
  performance: {now: () => now},
  requestAnimationFrame(cb) { now += 16; cb(); return 1; },
  Error,
  Promise,
};
vm.createContext(resizeCtx);
vm.runInContext(resizeSource + '\nthis.__resize=resize; this.__ensureInitialSurface=ensureInitialSurface;', resizeCtx);

(async () => {
  assert.strictEqual(resizeCtx.__resize(), false, 'collapsed canvas must be reported as unusable');
  assert.strictEqual(surfaceCalls, 0, 'collapsed canvas must not call surfaceChanged');
  await resizeCtx.__ensureInitialSurface();
  assert.strictEqual(state.surface.initialized, true, 'startup must wait until a valid surface exists');
  assert.strictEqual(surfaceCalls, 1, 'valid surface should initialize exactly once');
  assert.strictEqual(logic._syncCalledFlag, false, 'visual resize must not suppress pending turn transition');
  assert.strictEqual(resizeCtx.__resize(), true, 'duplicate valid resize is harmless');
  assert.strictEqual(surfaceCalls, 1, 'duplicate physical size must not resync game logic');

  // ResizeObserver can run before main.js registers surfaceChanged. A valid early
  // measurement must never poison the dedupe state and suppress the real first callback.
  state.surface = {w:0,h:0,menuY:0,initialized:false};
  state.surfaceChanged = null;
  rectCalls = 100;
  assert.strictEqual(resizeCtx.__resize(), false, 'valid surface before main.js handler must remain uninitialized');
  assert.strictEqual(state.surface.initialized, false, 'early observer measurement must not mark surface initialized');
  let lateSurfaceCalls = 0;
  state.surfaceChanged = () => { lateSurfaceCalls++; logic._syncCalledFlag = true; };
  logic._syncCalledFlag = false;
  assert.strictEqual(resizeCtx.__resize(), true, 'same valid size must initialize after handler registration');
  assert.strictEqual(lateSurfaceCalls, 1, 'first real surfaceChanged must not be deduplicated');
  assert.strictEqual(logic._syncCalledFlag, false, 'real visual initialization still preserves pending turn flag');

  // --- Authoritative turn/sequence/gameOver reconciliation regression ---
  const authStart = browser.indexOf('  const AUTHORITY_GRACE_MS=');
  const authEnd = browser.indexOf('  function installNetworkBridge(logic){', authStart);
  assert(authStart >= 0 && authEnd > authStart);
  const authSource = browser.slice(authStart, authEnd);
  let authNow = 0;
  const timers = [];
  const authState = {network:{authorityRevision:-1,authorityEpoch:null,pendingAuthority:null,authorityCheckTimer:null,snapshotBusy:false}};
  const authCtx = {
    state: authState,
    isPool: false,
    performance: {now: () => authNow},
    setTimeout(fn, ms) { timers.push({fn,ms}); return timers.length; },
    console: {warn(){}, info(){}, debug(){}},
    Object, Number, Array, Boolean, Math,
  };
  vm.createContext(authCtx);
  vm.runInContext(authSource + '\nthis.__authorityMismatch=authorityMismatch; this.__scheduleAuthorityCheck=scheduleAuthorityCheck; this.__evaluateAuthority=evaluateAuthority;', authCtx);

  const clientLogic = {
    _sequence:[2,0], turn:[0], gameOver:false, _localMoves:[], _awaitingResync:false,
    animator:{isAnimatingWorld(){return false;}}
  };
  const mismatch = Array.from(authCtx.__authorityMismatch(clientLogic,{sequence:[2,0],turn:[1],gameOver:false}));
  assert.deepStrictEqual(mismatch, ['turn'], 'same sequence with different turn must be detected');
  assert.deepStrictEqual(Array.from(authCtx.__authorityMismatch({...clientLogic,lastValidAnim:0},
    {sequence:[2,0],turn:[0],lastValidAnim:1})), ['animation'],
    'missed animation validation must recover even when turn and sequence match');

  let resyncs = 0;
  const net = {requestResync(){resyncs++; return true;}};
  authCtx.__scheduleAuthorityCheck(clientLogic,net,{authorityEpoch:1,revision:7,sequence:[2,0],turn:[1],gameOver:false},{ordered:true,source:'authority_state'});
  authNow = 950;
  authCtx.__evaluateAuthority(clientLogic,net);
  assert.strictEqual(resyncs, 1, 'persistent turn mismatch must request authoritative resync');

  // A stale revision must not replace a newer authority packet.
  authState.network.pendingAuthority = null;
  authState.network.authorityCheckTimer = null;
  authCtx.__scheduleAuthorityCheck(clientLogic,net,{authorityEpoch:1,revision:8,sequence:[2,0],turn:[1],gameOver:false},{ordered:true,source:'new'});
  const before = authState.network.pendingAuthority;
  authCtx.__scheduleAuthorityCheck(clientLogic,net,{authorityEpoch:1,revision:7,sequence:[2,0],turn:[0],gameOver:false},{ordered:true,source:'stale'});
  assert.strictEqual(authState.network.pendingAuthority, before, 'stale authority revision must be ignored');
  assert.strictEqual(authState.network.pendingAuthority.source, 'new');

  // Unsafe/animating state defers rather than drops the mismatch, then forces recovery.
  authState.network.authorityCheckTimer = null;
  authNow = 1000;
  clientLogic.animator.isAnimatingWorld = () => true;
  authCtx.__scheduleAuthorityCheck(clientLogic,net,{authorityEpoch:1,revision:9,sequence:[2,0],turn:[1],gameOver:false},{ordered:true,source:'animating'});
  authNow = 2200;
  authState.network.authorityCheckTimer = null;
  authCtx.__evaluateAuthority(clientLogic,net);
  assert(authState.network.pendingAuthority, 'mismatch must remain pending while animation is temporarily unsafe');
  const beforeForced = resyncs;
  authNow = 7001;
  authState.network.authorityCheckTimer = null;
  authCtx.__evaluateAuthority(clientLogic,net);
  assert.strictEqual(resyncs, beforeForced + 1, 'long-lived mismatch must recover even if animation never settles');

  // Periodic equal authority probes must not indefinitely reset a stuck pool's
  // reconciliation deadline; an older epoch must not rewind the expectation.
  authCtx.isPool = true;
  authState.network.pendingAuthority = null;
  authState.network.authorityCheckTimer = null;
  authNow = 10000;
  const probe = {authorityEpoch:1,revision:10,sequence:[2,0],turn:[1],gameOver:false};
  authCtx.__scheduleAuthorityCheck(clientLogic,net,probe,{source:'heartbeat'});
  for (authNow = 15000; authNow <= 30000; authNow += 5000)
    authCtx.__scheduleAuthorityCheck(clientLogic,net,probe,{source:'heartbeat'});
  assert.strictEqual(authState.network.pendingAuthority.receivedAt, 10000);
  const beforeProbeRecovery = resyncs;
  authNow = 31000;
  authCtx.__evaluateAuthority(clientLogic,net);
  assert.strictEqual(resyncs, beforeProbeRecovery+1, 'heartbeat probes must force recovery after bounded grace');

  console.log(JSON.stringify({
    ok:true,
    bundleIntegrityVerified:true,
    collapsedSurfaceRecovered:true,
    earlyObserverCannotPoisonSurface:true,
    visualResizePreservesTurnTimer:true,
    sameSequenceTurnMismatchDetected:true,
    staleRevisionRejected:true,
    animatingMismatchRetained:true,
  }, null, 2));
})().catch(err => { console.error(err); process.exitCode = 1; });
