#!/usr/bin/env node
'use strict';

const assert = require('assert');
const fs = require('fs');
const path = require('path');
const vm = require('vm');
const crypto = require('crypto');

const root = path.resolve(__dirname, '..');
const browserPath = path.join(root, 'game', 'browser-runtime.js');
const networkPath = path.join(root, 'game', 'samidev-network.js');
const mainPath = path.join(root, 'game', 'main.js');
const browser = fs.readFileSync(browserPath, 'utf8');
const network = fs.readFileSync(networkPath, 'utf8');
const main = fs.readFileSync(mainPath);

// Game bundle / rules must stay byte-for-byte unchanged.
const mainSha = crypto.createHash('sha256').update(main).digest('hex');
assert.strictEqual(mainSha, require('../game/samidev-integrity.json').games.carrom.sha256);

// Client authority comparison must cover turn/sequence/gameOver and must not drop a
// mismatch merely because an optimistic move/animation was active when authority arrived.
assert(browser.includes("fields.push('sequence')"));
assert(browser.includes("fields.push('turn')"));
assert(browser.includes("fields.push('gameOver')"));
assert(browser.includes('const hasPendingLocal=Array.isArray(logic._localMoves)&&logic._localMoves.length>0;'));
assert(browser.includes('age<AUTHORITY_GRACE_MS || (unsafe && age<AUTHORITY_MAX_WAIT_MS)'));
assert(browser.includes("scheduleAuthorityCheck(logic,net,msg,{ordered:true,source:'authority_state'})"));

// Resync history must skip packets already represented by the authoritative snapshot,
// reject sequence gaps, and queue live socket moves until replay is complete.
assert(browser.includes('if(packetN<curSeq) continue;'));
assert(browser.includes("console.warn('[SamiDev Sync] replay gap'"));
assert(browser.includes('if(state.network.snapshotBusy){\n        state.network.deferredMoves.push(msg);'));
assert(browser.includes('const deferred=state.network.deferredMoves.splice(0);'));
assert(browser.includes('if(!state.network.snapshotBusy) net.requestResync();'));

// Tutorial NEXT remains wired through the untouched game bundle, while the web bridge
// still provides DOWN/UP touch events used by the Button drag recognizer.
const mainText = main.toString('utf8');
assert(mainText.includes('this.button.on("press",this.onButtonPress.bind(this))'));
assert(mainText.includes('async onButtonPress(){'));
assert(mainText.includes('i.within&&this.emit("press",this)') || mainText.includes('this.emit("press",this.buttonId)'));
assert(browser.includes("emitTouch(0,ev)"));
assert(browser.includes("emitTouch(1,ev)"));

// Execute the actual network module in a small VM and verify duplicate resync calls
// are coalesced instead of emitting repeated commands.
const sent = [];
const context = {
  window: { __SAMIDEV_CLIENT_CONFIG: {} },
  location: { protocol: 'http:', host: 'localhost', href: 'http://localhost/game/', search: '' },
  history: { replaceState() {} },
  sessionStorage: { getItem() { return null; }, setItem() {}, removeItem() {} },
  WebSocket: { OPEN: 1, CLOSING: 2 },
  URL,
  URLSearchParams,
  setTimeout,
  clearTimeout,
  Date,
  Math,
  Promise,
  console,
};
vm.createContext(context);
vm.runInContext(network, context, { filename: 'samidev-network.js' });
const net = context.window.SamiDevNetwork;
assert(net && net.state);
net.state.ws = { readyState: 1, send(raw) { sent.push(JSON.parse(raw)); } };
assert.strictEqual(net.requestResync(), true);
assert.strictEqual(net.requestResync(), false);
assert.strictEqual(sent.length, 1);
assert.deepStrictEqual(sent[0], { type: 'resync' });
assert.strictEqual(net.state.resyncInFlight, true);
net.state.resyncInFlight = false;
assert.strictEqual(net.requestResync(), true);
assert.strictEqual(sent.length, 2);


// Execute the exact replay/deferred helpers extracted from browser-runtime.js.
const helperStart = browser.indexOf('  async function replayHistory(logic, history){');
const helperEnd = browser.indexOf('  function installNetworkBridge(logic){', helperStart);
assert(helperStart >= 0 && helperEnd > helperStart);
const helperSource = browser.slice(helperStart, helperEnd);
const helperCtx = {
  console: { warn() {}, info() {} },
  state: { frameRequested: false },
  cloneMove: v => v == null ? v : JSON.parse(JSON.stringify(v)),
  waitUntilWorldSettles: async () => true,
};
vm.createContext(helperCtx);
vm.runInContext(helperSource + '\nthis.__replayHistory=replayHistory; this.__applyDeferredMove=applyDeferredMove;', helperCtx);

(async () => {
  let calls = 0;
  const logic = { _sequence: [2, 0], move(seat, packet) { calls++; this._sequence[seat]++; return true; } };
  assert.strictEqual(await helperCtx.__replayHistory(logic, [{seat:0, packet:{n:1,m:{m:0}}}]), true);
  assert.strictEqual(calls, 0, 'history already contained in snapshot must be skipped');
  assert.strictEqual(await helperCtx.__replayHistory(logic, [{seat:0, packet:{n:3,m:{m:0}}}]), false);
  assert.strictEqual(calls, 0, 'history gap must not be executed');
  assert.strictEqual(await helperCtx.__replayHistory(logic, [{seat:0, packet:{n:2,m:{m:0}}}]), true);
  assert.strictEqual(calls, 1, 'exact next history packet must execute once');

  const logic2 = { _sequence: [4, 0], move(seat, packet) { this._sequence[seat]++; return true; } };
  assert.strictEqual(helperCtx.__applyDeferredMove(logic2, {seat:0, packet:{n:3,m:{m:0}}}), true);
  assert.strictEqual(logic2._sequence[0], 4, 'stale deferred echo must be ignored');
  assert.strictEqual(helperCtx.__applyDeferredMove(logic2, {seat:0, packet:{n:4,m:{m:0}}}), true);
  assert.strictEqual(logic2._sequence[0], 5, 'next deferred move must execute exactly once');
  assert.strictEqual(helperCtx.__applyDeferredMove(logic2, {seat:0, packet:{n:6,m:{m:0}}}), false);

  helperCtx.waitUntilWorldSettles = async () => false;
  const logic3 = { _sequence: [0, 0], move(seat) { this._sequence[seat]++; return true; } };
  assert.strictEqual(await helperCtx.__replayHistory(logic3, [{seat:0, packet:{n:0,m:{m:0}}}]), false,
    'world-settle timeout must abort replay instead of pretending recovery succeeded');

  console.log('PASS client resync regression');
  console.log('main.js sha256:', mainSha);
  console.log('resync requests sent in coalescing test:', sent.length);
})().catch(err => { console.error(err); process.exitCode = 1; });
