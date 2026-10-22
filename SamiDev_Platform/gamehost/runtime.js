'use strict';

const fs = require('fs');
const path = require('path');
const vm = require('vm');
const crypto = require('crypto');
const {installTableSoccerServer} = require('./tablesoccer');
const {installCarromServer} = require('./carrom');
const {installPoolServer,poolView} = require('./pool');
const {validatePacket} = require('./validation');
const {poolMoveRejectionReason} = require('./pool');

const HOST_GLOBAL = 'SamiDev';
const HOST_PLAYER_ID_METHOD = 'getSamiDevID';

function cloneJson(value) {
  if (value === undefined) return undefined;
  return structuredClone(value);
}

function mergeReveal(base, incoming) {
  if (incoming === undefined) return base;
  if (base === undefined) return cloneJson(incoming);
  if (
    base && incoming &&
    typeof base === 'object' && typeof incoming === 'object' &&
    !Array.isArray(base) && !Array.isArray(incoming)
  ) {
    const out = cloneJson(base);
    for (const [key, value] of Object.entries(incoming)) {
      out[key] = mergeReveal(out[key], value);
    }
    return out;
  }
  return cloneJson(incoming);
}

class GameRuntimeFactory {
  constructor(gameDir, options = {}) {
    this.gameId = options.gameId || 'carrom';
    this.gameDir = path.resolve(gameDir);
    this.mainPath = path.join(this.gameDir, 'main.js');
    this.source = fs.readFileSync(this.mainPath, 'utf8');
    this.sha256 = crypto.createHash('sha256').update(this.source).digest('hex');
    this.expectedSha256 = options.expectedSha256 || null;
    if (this.expectedSha256 && this.sha256 !== this.expectedSha256) {
      throw new Error(`main.js hash mismatch: expected ${this.expectedSha256}, got ${this.sha256}`);
    }

    // Compile/load the bundle once. Each room gets a fresh GameLogic instance from the
    // exact constructor registered by main.js. This keeps rules/state isolated while
    // sharing immutable code, which is dramatically cheaper than one VM per room.
    this.script = new vm.Script(this.source, { filename: this.mainPath });
    this.context = this._createSharedContext();
    this.bootstrapLogic = null;
    this.context[HOST_GLOBAL] = this._makeBootstrapHostApi();
    this.script.runInContext(this.context, { timeout: 5000 });
    if (!this.bootstrapLogic) throw new Error('main.js did not register GameLogic');
    this.GameLogicCtor = this.bootstrapLogic.constructor;
  }

  _universal() {
    const f = function () { return 0; };
    f.valueOf = () => 0;
    f.toString = () => '0';
    return f;
  }

  _norm(u) {
    return String(u || '').replace(/^~\//, '').replace(/^(?:carrom|tablesoccer|crazy8|pool)\//, '');
  }

  _loadFileAsString(uri) {
    const base = path.resolve(this.gameDir);
    const p = path.resolve(base, this._norm(uri));
    const rel = path.relative(base, p);
    if (rel.startsWith('..') || path.isAbsolute(rel)) return '{}';
    try { return fs.readFileSync(p, 'utf8'); }
    catch { return '{}'; }
  }

  _createSharedContext() {
    const universal = this._universal();
    const sandbox = {
      console: { log: () => {}, warn: () => {}, error: () => {}, debug: () => {} },
      GL: new Proxy({}, { get: () => universal }),
      AudioController: new Proxy(universal, { get: () => universal, construct: () => ({}) }),
      audio: new Proxy(universal, { get: () => universal, construct: () => ({}) }),
      pmath: { sin: Math.sin, cos: Math.cos, atan2: Math.atan2, acos: Math.acos, pow: Math.pow },
      document: new Proxy({}, { get: () => universal }),
      setTimeout, clearTimeout, setInterval, clearInterval,
      Promise,
    };
    sandbox.window = sandbox;
    sandbox.global = sandbox;
    sandbox.globalThis = sandbox;
    return vm.createContext(sandbox, { name: 'SamiDevSharedGameLogic' });
  }

  _baseHostApi() {
    return {
      is_develop: false,
      is_server: true,
      version: 30,
      dpi: 96,
      language: 'en',
      os: 'linux',
      globals: {},
      saved_local_state: {},
      game_preferences: {},
      hrtime: () => Number(process.hrtime.bigint()),
      translate: (a) => Array.isArray(a) ? String(a[0] ?? '') : String(a ?? ''),
      loadFileAsString: (uri) => this._loadFileAsString(uri),
      log: () => {},
      ownerSeat: () => 0,
      getInventory: () => [],
      [HOST_PLAYER_ID_METHOD]: (seat) => `samidev-seat-${seat}`,
      isRTL: () => false,
      haptic: { isVibrationSupported: () => false, vibrate: () => {}, vibratePattern: () => {} },
      shop: { getCatalog: () => Promise.resolve([]) },
      net: { onMessage: () => {}, sendMessage: () => {} },
      alarm: { set: () => {} },
      session: { changeTurn: () => {}, gameOver: () => {} },
      setGameLogic: () => {},
      setOnSurfaceCreatedListener: () => {},
      setOnSurfaceChangedListener: () => {},
      setOnDrawFrameListener: () => {},
      setOnTouchListener: () => {},
      setOnMouseListener: () => {},
      setOnAvatarsReadyListener: () => {},
      setOnMenuButtonClickedListener: () => {},
      setTimer: () => 0,
      clearTimer: () => {},
      requestRender: () => {},
      addMenuButton: () => {},
      requestKeyboard: () => {},
      showGameOver: () => {},
      showItemPurchase: () => {},
      showProfile: () => {},
      track: () => {},
      saveLocalState: () => {},
      saveGamePreferences: () => {},
      fetchAudio: (uri, ok) => ok?.(uri, { audio_id: 0 }),
      fetchTexture: (uri, ok) => ok?.(uri, { texture_id: 0, width: 1, height: 1 }),
      streamMusic: (uri, cb) => cb?.(uri, 0),
      sendMove: () => {},
      resetSynchronizationStream: () => {},
    };
  }

  _makeBootstrapHostApi() {
    const p = this._baseHostApi();
    p.setGameLogic = (logic) => { this.bootstrapLogic = logic; };
    return p;
  }

  _activate(room) {
    this.context[HOST_GLOBAL] = room.hostApi;
  }

  _record(room, type, payload = {}) {
    room.events.push({ type, ...payload });
    if (room.events.length > 100) room.events.splice(0, room.events.length - 100);
  }

  _beginEffects(room, source, meta = {}) {
    if (room.activeEffects) throw new Error(`nested authoritative operation: ${source}`);
    room.activeEffects = { source, meta: cloneJson(meta), revealBySeat: {} };
  }

  _endEffects(room) {
    const effects = room.activeEffects || { source: 'unknown', meta: {}, revealBySeat: {} };
    room.activeEffects = null;
    return effects;
  }

  _captureReveal(room, seats, data) {
    const normalized = Array.isArray(seats) ? seats.map(Number).filter(Number.isInteger) : [];
    const payload = cloneJson(data);
    this._record(room, 'reveal', { seats: normalized, data: payload });
    const target = room.activeEffects;
    if (!target) {
      room.orphanReveals.push({ seats: normalized, data: payload });
      if (room.orphanReveals.length > 50) room.orphanReveals.shift();
      return;
    }
    for (const seat of normalized) {
      const key = String(seat);
      target.revealBySeat[key] = mergeReveal(target.revealBySeat[key], payload);
    }
  }

  _setHostTimer(room, fn, ms, repeat = false) {
    if (typeof fn !== 'function') return 0;
    const id = room.nextHostTimerId++;
    const delay = Math.max(0, Number(ms) || 0);
    const fire = () => {
      if (!repeat) room.hostTimers.delete(id);
      if (room.destroyed) return;
      const before = {
        turn: Array.isArray(room.logic?.turn) ? [...room.logic.turn] : [],
        sequence: Array.isArray(room.logic?._sequence) ? [...room.logic._sequence] : [],
        gameOver: !!room.logic?.gameOver,
        nextAlarmId: Number(room.logic?._nextAlarmId || 0),
      };
      try {
        this._activate(room);
        fn();
        this._record(room, 'host_timer_fired', { id, ms: delay, repeat: !!repeat });
      } catch (e) {
        this._record(room, 'host_timer_error', { id, error: String(e.stack || e) });
        return;
      }
      const after = {
        turn: Array.isArray(room.logic?.turn) ? [...room.logic.turn] : [],
        sequence: Array.isArray(room.logic?._sequence) ? [...room.logic._sequence] : [],
        gameOver: !!room.logic?.gameOver,
        nextAlarmId: Number(room.logic?._nextAlarmId || 0),
      };
      if (JSON.stringify(before) !== JSON.stringify(after)) {
        try {
          room.emitAsync?.({
            type: 'authority_state',
            roomId: room.roomId,
            reason: 'host_timer',
            ...this.describeRoom(room, true),
          });
        } catch (e) {
          this._record(room, 'emit_error', { error: String(e.message || e) });
        }
      }
    };
    const handle = repeat ? setInterval(fire, delay) : setTimeout(fire, delay);
    room.hostTimers.set(id, { handle, repeat: !!repeat });
    this._record(room, 'host_timer_set', { id, ms: delay, repeat: !!repeat });
    return id;
  }

  _clearHostTimer(room, id) {
    const key = Number(id);
    const item = room.hostTimers.get(key);
    if (!item) return;
    try { item.repeat ? clearInterval(item.handle) : clearTimeout(item.handle); } catch (_) {}
    room.hostTimers.delete(key);
    this._record(room, 'host_timer_cleared', { id: key });
  }

  _alarmInfo(room, id) {
    const item = room.timers.get(Number(id));
    if (!item) return undefined;
    const remaining = room.waitingForClients ? item.remaining : Math.max(0, item.expiresAt - Date.now());
    return [remaining, item.duration];
  }

  waitForClients(room) {
    room.waitingForClients = true;
    for (const item of room.timers.values()) {
      clearTimeout(item.handle);
      item.remaining = Math.max(0, item.expiresAt - Date.now());
    }
  }

  beginMatch(room) {
    if (!room.waitingForClients) return;
    room.waitingForClients = false;
    for (const [id, item] of [...room.timers]) {
      this._scheduleAlarm(room, item.remaining, id);
      const resumed=room.timers.get(id);
      resumed.duration=item.duration;resumed.startedAt=resumed.expiresAt-item.duration;
    }
  }

  _pruneStaleAlarms(room) {
    const expected = Number(room.logic?._nextAlarmId);
    const pending = !!room.logic?._pendingAlarm;
    for (const [id, item] of room.timers.entries()) {
      if (!pending || id !== expected) {
        try { clearTimeout(item.handle); } catch (_) {}
        room.timers.delete(id);
        this._record(room, 'alarm_pruned', { id, expected, pending });
      }
    }
  }

  _scheduleAlarm(room, ms, id) {
    const alarmId = Number(id);
    const isPhys = Boolean(room.logic?.IsPhysicsAlarm?.(alarmId));
    // BaseLogic only has one authoritative pending alarm at a time.
    // Cancel older host timers immediately when a newer alarm of the same category replaces them.
    for (const [otherId, item] of room.timers.entries()) {
      if (otherId !== alarmId) {
        const otherIsPhys = Boolean(room.logic?.IsPhysicsAlarm?.(otherId));
        if (isPhys === otherIsPhys) {
          try { clearTimeout(item.handle); } catch (_) {}
          room.timers.delete(otherId);
          this._record(room, 'alarm_superseded', { id: otherId, by: alarmId });
        }
      }
    }
    const old = room.timers.get(alarmId);
    if (old) clearTimeout(old.handle);
    const delay = Math.max(0, Number(ms) || 0);
    const handle = setTimeout(() => {
      room.timers.delete(alarmId);
      if (room.destroyed) return;
      // Critical: a cancelled/replaced host timer may still fire. Never inject it into
      // BaseLogic and never broadcast it if it is no longer the pending alarm.
      // Physics alarms (0xFFFFFF03 etc) are handled by PhysicsLogic.alarm() and are not tracked by _pendingAlarm.
      if (!isPhys && (!room.logic?._pendingAlarm || Number(room.logic?._nextAlarmId) !== alarmId)) {
        this._record(room, 'stale_alarm_ignored', {
          id: alarmId,
          expected: Number(room.logic?._nextAlarmId),
          pending: !!room.logic?._pendingAlarm,
        });
        return;
      }
      let effects = null;
      let accepted = false;
      try {
        this._activate(room);
        this._beginEffects(room, 'alarm', { id: alarmId });
        accepted = room.logic.alarm(null, alarmId);
        effects = this._endEffects(room);
        this._record(room, 'alarm_fired', { id: alarmId, accepted });
      } catch (e) {
        if (room.activeEffects) effects = this._endEffects(room);
        this._record(room, 'alarm_error', { id: alarmId, error: String(e.stack || e) });
        return;
      }
      // Rejected alarms are stale/protocol-invalid by definition. Broadcasting them causes
      // clients to call BaseLogic.alarm(undefined/old-id), which intentionally triggers resync.
      if (!accepted) {
        this._record(room, 'rejected_alarm_suppressed', { id: alarmId });
        return;
      }
      const revealBySeat = effects?.revealBySeat || {};
      if (Object.keys(revealBySeat).length === 0) {
        this._record(room, 'alarm_without_reveal_suppressed', { id: alarmId });
        return;
      }
      try {
        room.emitAsync?.({
          type: 'authority_alarm',
          roomId: room.roomId,
          alarmId,
          revealBySeat,
          ...this.describeRoom(room, true),
        });
      } catch (e) {
        this._record(room, 'emit_error', { error: String(e.message || e) });
      }
    }, delay);
    room.timers.set(alarmId, {
      handle,
      duration: delay,
      startedAt: Date.now(),
      expiresAt: Date.now() + delay,
    });
    if(room.waitingForClients){clearTimeout(handle);room.timers.get(alarmId).remaining=delay;}
    this._record(room, 'alarm_set', { ms: delay, id: alarmId });
  }

  _makeRoomHostApi(room) {
    const p = this._baseHostApi();
    p.log = (message, level) => this._record(room, 'log', { message: String(message), level });
    p.alarm = { set: (ms, id) => this._scheduleAlarm(room, ms, id) };
    p.session = {
      changeTurn: (turn, message) => {
        room.lastTurn = Array.isArray(turn) ? [...turn] : [];
        this._record(room, 'host_change_turn', { turn: room.lastTurn, message });
      },
      gameOver: (...args) => {
        room.lastGameOver = args;
        this._record(room, 'host_game_over', { args });
      },
    };
    p.track = (...args) => this._record(room, 'track', { args });
    // Generic SamiDev timers are distinct from BaseLogic authoritative alarms.
    // Carrom's native animationCompleted(true) uses this path to finish a missed turn.
    p.setTimer = (fn, ms, repeat = false) => this._setHostTimer(room, fn, ms, repeat);
    p.clearTimer = (id) => this._clearHostTimer(room, id);
    p.sendMove = (packet) => this._record(room, 'host_send_move', { packet });
    p.resetSynchronizationStream = () => this._record(room, 'host_resync');
    return p;
  }

  createRoom(roomId, settings, capacity, emitAsync) {
    const room = {
      roomId,
      settings: structuredClone(settings),
      capacity,
      logic: null,
      hostApi: null,
      timers: new Map(),
      hostTimers: new Map(),
      nextHostTimerId: 1,
      events: [],
      activeEffects: null,
      orphanReveals: [],
      emitAsync,
      destroyed: false,
      lastGameOver: null,
      lastTurn: [],
      lastAlert: null,
    };
    room.hostApi = this._makeRoomHostApi(room);
    return this._initializeRoomLogic(room);
  }

  _initializeRoomLogic(room) {
    this._activate(room);
    room.logic = new this.GameLogicCtor();
    const g = room.logic;
    if (this.gameId === 'tablesoccer') installTableSoccerServer(g);
    if (this.gameId === 'carrom') installCarromServer(g);
    if (this.gameId === 'pool') installPoolServer(g);
    g.onSetAlarm = (ms, id) => this._scheduleAlarm(room, ms, id);
    g.onGetAlarm = (id) => this._alarmInfo(room, id);
    g.onReveal = (seats, data) => this._captureReveal(room, seats, data);
    g.onTurnChanged = (turn, message) => {
      room.lastTurn = Array.isArray(turn) ? [...turn] : [];
      this._record(room, 'turn_changed', { turn: room.lastTurn, message });
    };
    g.onGameOver = (...args) => {
      room.lastGameOver = args;
      this._record(room, 'game_over', { args });
    };
    g.onReportSeatState = (seat, state) => this._record(room, 'seat_state', { seat, state });
    g.onAlert = (seats, message) => {
      room.lastAlert = { seats, message };
      this._record(room, 'alert', { seats, message });
    };
    // The shipped Carrom bundle leaves BaseLogic._turnExpire() empty and expects the
    // platform to provide the auto-move. Use BaseLogic.autoMoves() itself so the exact
    // main.js AFK counters, resign rules and per-seat __auto reveal are preserved.
    if (this.gameId === 'carrom') g._turnExpire = () => {
      const seat = Array.isArray(g.turn) ? Number(g.turn[0]) : -1;
      if (!Number.isInteger(seat) || seat < 0 || g.gameOver) return;
      if (typeof g.autoMoves !== 'function') throw new Error('main.js autoMoves() unavailable');
      this._record(room, 'turn_expire_auto_move', { seat, sequence: Number(g._sequence?.[seat] || 0) });
      g.autoMoves([{ seat, data: { m: 3 } }]);
    };
    const nativeSettings = structuredClone(room.settings);
    delete nativeSettings.gameId;
    delete nativeSettings.largeTable;
    const seats = g.initialize(nativeSettings, undefined);
    if (seats !== room.capacity) throw new Error(`GameLogic seat mismatch: ${seats} != ${room.capacity}`);
    for (let s = 0; s < seats; s++) g.enter(s);
    if (g.server !== true || g.localSeat !== undefined) throw new Error('GameLogic did not enter authoritative server mode');
    this._record(room, 'room_initialized', { seats, server: g.server });
    return room;
  }

  move(room, seat, packet) {
    this._activate(room);
    return room.logic.move(seat, packet) === true;
  }

  processMove(room, seat, packet) {
    this._activate(room);
    if (!validatePacket(this.gameId, room.logic, seat, packet)) {
      if (this.gameId === 'pool' && process.env.POOL_MOVE_DEBUG === '1') console.warn('[pool] move validation rejected', {action:packet?.m?.a, seat, turn:room.logic.turn, sequence:room.logic._sequence?.[seat], packetSequence:packet?.n, canShoot:room.logic.canShoot?.(seat), canMoveCueBall:room.logic.canMoveCueBall?.(seat), ballInHand:room.logic.ballInHand, breaking:room.logic.isBreaking()});
      return {accepted:false,revealBySeat:{},rejectionReason:this.gameId === 'pool' ? poolMoveRejectionReason(room.logic,seat,packet) : undefined};
    }
    if (['carrom','tablesoccer'].includes(this.gameId) && packet.__info?.a === -1) {
      // Keep the legacy animation acknowledgement compatible, but never pass
      // client scores or world state into the rules engine or event history.
      packet.__info = 1;
      return {accepted:true,revealBySeat:{}};
    }
    // Capture the pre-move diagnosis: GameLogic.move may mutate turn/sequence even
    // when rejecting, making a post-move diagnosis misleading.
    const preMovePoolReason = this.gameId === 'pool'
      ? poolMoveRejectionReason(room.logic, seat, packet) : undefined;
    if (this.gameId === 'pool') {room.logic.poolFrames=[];room.logic.poolSounds=[];}
    const poolCheckpoint=this.gameId==='pool'&&packet.m?.a===1?this.describeRoom(room,true).snapshot:null;
    if(this.gameId==='pool'&&packet.m?.a===1&&!poolCheckpoint){
      return {accepted:false,revealBySeat:{},rejectionReason:'CHECKPOINT_UNAVAILABLE'};
    }
    this._beginEffects(room, 'move', { seat });
    let accepted;
    try {
      accepted = room.logic.move(seat, packet) === true;
      if (accepted && this.gameId === "pool") room.logic.revealData(room.logic.createSeatList(), {pool:poolView(room.logic),...(room.logic.poolFrames.length?{frames:room.logic.poolFrames}:{}),soundEvents:room.logic.poolSounds});
    } catch (e) {
      this._endEffects(room);
      if(poolCheckpoint){
        // Rebuild the native runtime, not only serialized coordinates: currentShot,
        // contact caches, collision masks and sinking state are not all serialized.
        this.destroyRoom(room);
        room.destroyed=false;
        room.lastGameOver=null;room.lastAlert=null;
        this._initializeRoomLogic(room);
        this.deserialize(room,poolCheckpoint);
        room.logic.stopBodies();
      }
      throw e;
    }
    const effects = this._endEffects(room);
    if (!accepted && this.gameId === 'pool' && process.env.POOL_MOVE_DEBUG === '1') console.warn('[pool] rules engine rejected move', {action:packet?.m?.a, seat, turn:room.logic.turn, sequence:room.logic._sequence?.[seat], packetSequence:packet?.n, canShoot:room.logic.canShoot?.(seat), awaitingReady:room.logic.awaitingReady});
    return { accepted, revealBySeat: effects.revealBySeat, rejectionReason: !accepted && this.gameId === 'pool' ? (preMovePoolReason && preMovePoolReason !== 'VALID' ? preMovePoolReason : 'RULES_ENGINE_REJECTED') : undefined };
  }

  deserialize(room, snapshot) {
    this._activate(room);
    const result=room.logic.deserialize(structuredClone(snapshot), undefined);
    this._pruneStaleAlarms(room);
    // The SDK restores alarm identifiers/state, but the platform owns its scheduler.
    // Recreate that scheduler on both host recovery and transactional rollback.
    if(snapshot.p===1&&room.logic._pendingAlarm){
      const meta=snapshot._samidev_alarm;
      const absolute=meta&&meta.id===snapshot.a&&Number.isFinite(meta.expiresAt)&&Number.isFinite(meta.duration);
      const remaining=absolute?(meta.paused?meta.remaining:Math.max(0,meta.expiresAt-Date.now())):snapshot.x;
      const duration=absolute?meta.duration:snapshot.z;
      if(Number.isFinite(remaining)&&remaining>=0){
        this._scheduleAlarm(room,remaining,snapshot.a);
        const alarm=room.timers.get(snapshot.a);
        if(alarm&&Number.isFinite(duration)&&duration>=0){
          if(absolute&&!meta.paused)alarm.expiresAt=meta.expiresAt;
          alarm.duration=duration;alarm.startedAt=alarm.expiresAt-duration;
        }
      }
    }
    return result;
  }

  _snapshotSafe(room) {
    const g = room.logic;
    // PhysicsLogic.serialize() is NOT a pure getter. With
    // ExecForSerialization.AllButLatest it can call validateOrExecute(true) and
    // advance/clear pending ServerTrust animation validation. Never serialize an
    // authoritative room while an animation is still awaiting validation.
    const pending = g.animValidation && typeof g.animValidation === 'object'
      ? Object.keys(g.animValidation).length
      : 0;
    const noAnimations = Number.isFinite(g.noAnimations) ? Number(g.noAnimations) : 0;
    const lastValidAnim = Number.isFinite(g.lastValidAnim) ? Number(g.lastValidAnim) : noAnimations;
    return !g.executingPM && !g.isExecutingQueuedAnimations && pending === 0 && lastValidAnim >= noAnimations;
  }

  describeRoom(room, includeSnapshot = false) {
    this._activate(room);
    const g = room.logic;
    const snapshotSafe = this._snapshotSafe(room);
    const out = {
      ...(this.gameId === 'pool' ? {pool:poolView(g)} : {}),
      server: g.server === true,
      seats: g.seats,
      started: !!g.started,
      gameOver: !!g.gameOver,
      finishOrder: Array.isArray(g.finishOrder) ? structuredClone(g.finishOrder) : null,
      teams: Array.isArray(g.teams) ? structuredClone(g.teams) : null,
      turn: Array.isArray(g.turn) ? [...g.turn] : [],
      sequence: Array.isArray(g._sequence) ? [...g._sequence] : [],
      pendingAlarm: !!g._pendingAlarm,
      nextAlarmId: Number(g._nextAlarmId || 0),
      alarmState: Number(g._alarmState || 0),
      lastValidAnim: Number.isFinite(g.lastValidAnim) ? g.lastValidAnim : null,
      noAnimations: Number.isFinite(g.noAnimations) ? g.noAnimations : null,
      pendingAnimationValidation: g.animValidation && typeof g.animValidation === 'object' ? Object.keys(g.animValidation).length : 0,
      snapshotSafe,
      ...(this.gameId === 'crazy8' ? {waitingForClients: !!room.waitingForClients} : {}),
    };
    if (includeSnapshot && snapshotSafe) {
      const before = {
        noAnimations: g.noAnimations,
        lastValidAnim: g.lastValidAnim,
        lastState: g.lastState,
        pending: g.animValidation && typeof g.animValidation === 'object' ? Object.keys(g.animValidation).length : 0,
      };
      const snapshot = structuredClone(g.serialize());
      const after = {
        noAnimations: g.noAnimations,
        lastValidAnim: g.lastValidAnim,
        lastState: g.lastState,
        pending: g.animValidation && typeof g.animValidation === 'object' ? Object.keys(g.animValidation).length : 0,
      };
      if (JSON.stringify(before) !== JSON.stringify(after)) {
        throw new Error(`unsafe serialize side effect detected: before=${JSON.stringify(before)} after=${JSON.stringify(after)}`);
      }
      if (snapshot && snapshot.p === 1) {
        const alarm = this._alarmInfo(room, snapshot.a);
        if (alarm) {
          snapshot.x = alarm[0];
          snapshot.z = alarm[1];
          const timer=room.timers.get(snapshot.a);
          if(timer)snapshot._samidev_alarm={id:snapshot.a,expiresAt:timer.expiresAt,duration:timer.duration,paused:!!room.waitingForClients,remaining:alarm[0]};
        }
      }
      if (this.gameId === "pool") snapshot.pool=poolView(g);
      out.snapshot = snapshot;
      if (this.gameId === 'crazy8') {
        // Keep the full checkpoint inside the trusted services only. Persist native
        // seat views with it so reconnects remain private even during a host outage.
        snapshot._samidev_clientViews = {};
        for (let seat = -1; seat < room.capacity; seat++) {
          snapshot._samidev_clientViews[String(seat)] = structuredClone(g.serialize(seat));
        }
      }
    } else if (includeSnapshot) {
      out.snapshotDeferred = true;
    }
    return out;
  }

  destroyRoom(room) {
    room.destroyed = true;
    for (const item of room.timers.values()) clearTimeout(item.handle);
    room.timers.clear();
    for (const item of room.hostTimers.values()) {
      try { item.repeat ? clearInterval(item.handle) : clearTimeout(item.handle); } catch (_) {}
    }
    room.hostTimers.clear();
  }
}

module.exports = { GameRuntimeFactory };
