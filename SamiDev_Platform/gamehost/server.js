'use strict';

const http = require('http');
const path = require('path');
const crypto = require('crypto');
const fs = require('fs');
const {monitorEventLoopDelay, performance} = require('perf_hooks');
const { URL } = require('url');
const { GameRuntimeFactory } = require('./runtime');

const PORT = Number(process.env.SAMIDEV_GAMEHOST_PORT || 8091);
const PRODUCTION = process.env.SAMIDEV_PRODUCTION === '1' || process.env.NODE_ENV === 'production';
const HOST = process.env.SAMIDEV_GAMEHOST_HOST || (PRODUCTION ? '0.0.0.0' : '127.0.0.1');
const GAME_DIR = path.resolve(process.env.SAMIDEV_GAME_DIR || path.join(__dirname, '..', 'game'));
const integrity = JSON.parse(fs.readFileSync(path.join(GAME_DIR, 'samidev-integrity.json'), 'utf8'));
const gameDirs = {pool:path.join(GAME_DIR,'games','pool'), carrom: GAME_DIR, tablesoccer: path.join(GAME_DIR, 'games', 'tablesoccer'), crazy8: path.join(GAME_DIR, 'games', 'crazy8')};
const MAX_BODY = Number(process.env.SAMIDEV_GAMEHOST_MAX_BODY || 262144);
const ROOM_IDLE_MS = Number(process.env.SAMIDEV_GAMEHOST_ROOM_IDLE_MS || 21600000);
const SERVICE_KEY = process.env.SAMIDEV_GAMEHOST_SERVICE_KEY || 'samidev-local-development-key-change-me';
if ((PRODUCTION || !['127.0.0.1','::1','localhost'].includes(HOST)) &&
    (SERVICE_KEY.length < 32 || ['samidev-local-development-key-change-me','CHANGE_ME_TO_A_LONG_RANDOM_SECRET'].includes(SERVICE_KEY))) {
  throw new Error('A private SAMIDEV_GAMEHOST_SERVICE_KEY of at least 32 characters is required for production or non-loopback binding');
}
const ROOM_RE = /^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{6}$/;

const factories = new Map(Object.entries(gameDirs).map(([id, dir]) => [id, new GameRuntimeFactory(dir, {gameId:id, expectedSha256: (id === 'carrom' && process.env.SAMIDEV_MAINJS_SHA256) || integrity.games[id].sha256})]));
const gameHashes = Object.fromEntries([...factories].map(([id,f]) => [id,f.sha256]));
const rooms = new Map();
const sseClients = new Set();
const metrics = { requests: 0, moves: 0, accepted: 0, rejected: 0, roomsCreated: 0, events: 0, errors: 0 };
const eventLoopDelay = monitorEventLoopDelay({resolution:20});
eventLoopDelay.enable();
const moveDurations = [];

function json(res, status, data) {
  const raw = JSON.stringify(data);
  res.writeHead(status, {
    'Content-Type': 'application/json; charset=utf-8',
    'Content-Length': Buffer.byteLength(raw),
    'X-Content-Type-Options': 'nosniff',
    'Cache-Control': 'no-store',
  });
  res.end(raw);
}

function authorized(req) {
  const got = String(req.headers['x-samidev-service-key'] || '');
  const a = Buffer.from(got);
  const b = Buffer.from(SERVICE_KEY);
  return a.length === b.length && a.length > 0 && crypto.timingSafeEqual(a, b);
}

function requireInternalAuth(req, res) {
  if (authorized(req)) return true;
  json(res, 401, { ok: false, code: 'SERVICE_AUTH_REQUIRED', message: 'internal service authentication required' });
  return false;
}

function emitEvent(event) {
  metrics.events++;
  const raw = `data: ${JSON.stringify(event)}\n\n`;
  for (const res of [...sseClients]) {
    // A disconnected/slow gateway must reconnect and reconcile instead of buffering
    // an unbounded stream of physics checkpoints in the Node process.
    try { res.write(raw); if (res.writableLength > 2 * 1024 * 1024) { sseClients.delete(res); res.destroy(); } }
    catch { sseClients.delete(res); res.destroy(); }
  }
}

function emitRoomEvent(room, event) {
  room.authorityRevision = Number(room.authorityRevision || 0) + 1;
  emitEvent({
    ...event,
    roomId: room.roomId,
    authorityEpoch: room.authorityEpoch,
    revision: room.authorityRevision,
  });
}

function roomSummary(room, snapshot = true) {
  return {
    roomId: room.roomId,
    authorityEpoch: room.authorityEpoch,
    authorityRevision: room.authorityRevision,
    ...room.factory.describeRoom(room, snapshot),
    gameId: room.gameId,
    mainJsSha256: room.factory.sha256,
  };
}

async function readBody(req) {
  let total = 0;
  const chunks = [];
  for await (const chunk of req) {
    total += chunk.length;
    if (total > MAX_BODY) throw Object.assign(new Error('body too large'), { statusCode: 413 });
    chunks.push(chunk);
  }
  if (!chunks.length) return {};
  const parsed = JSON.parse(Buffer.concat(chunks).toString('utf8'));
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) throw Object.assign(new Error('body must be an object'), { statusCode: 400 });
  return parsed;
}

function normalizeRoomId(value) {
  const roomId = String(value || '').trim().toUpperCase();
  if (!ROOM_RE.test(roomId)) throw Object.assign(new Error('invalid roomId'), { statusCode: 400, code: 'BAD_ROOM_ID' });
  return roomId;
}

function normalizeEpoch(value, fallback = 1) {
  const n = Number(value ?? fallback);
  if (!Number.isInteger(n) || n < 1) throw Object.assign(new Error('invalid authority epoch'), { statusCode: 400, code: 'BAD_AUTHORITY_EPOCH' });
  return n;
}

function applyConnectionEpochs(room, values) {
  if (!Array.isArray(values)) return;
  for (let i = 0; i < room.capacity && i < values.length; i++) {
    const n = Number(values[i]);
    if (Number.isInteger(n) && n >= 0) room.connectionEpochs[i] = Math.max(room.connectionEpochs[i] || 0, n);
  }
}

function ensureRoom(body) {
  const roomId = normalizeRoomId(body.roomId);
  const gameId = String(body.settings?.gameId || body.gameId || 'carrom');
  const factory = factories.get(gameId);
  if (!factory) throw Object.assign(new Error('unsupported game'), {statusCode:400, code:'UNKNOWN_GAME'});
  const requestedEpoch = normalizeEpoch(body.authorityEpoch, 1);
  let room = rooms.get(roomId);
  if (room && room.gameId !== gameId) throw Object.assign(new Error('room game cannot change'), {statusCode:409,code:'GAME_MISMATCH'});

  if (room && requestedEpoch < room.authorityEpoch) {
    throw Object.assign(new Error('stale authority epoch'), { statusCode: 409, code: 'STALE_AUTHORITY' });
  }
  if (room && requestedEpoch > room.authorityEpoch) {
    room.factory.destroyRoom(room);
    rooms.delete(roomId);
    room = null;
  }

  if (!room) {
    const settings = body.settings;
    const capacity = Number(body.capacity);
    const capacities = gameId === 'crazy8' ? [2, 3, 4, 6] : [2, 4];
    if (!settings || typeof settings !== 'object' || !capacities.includes(capacity)) {
      throw Object.assign(new Error('settings/capacity required'), { statusCode: 400 });
    }
    let createdRoom;
    const roomEmitter = (event) => emitRoomEvent(createdRoom, event);
    createdRoom = factory.createRoom(roomId, settings, capacity, roomEmitter);
    room = createdRoom;
    room.factory = factory;
    room.gameId = gameId;
    room.authorityEpoch = requestedEpoch;
    room.authorityRevision = 0;
    room.connectionEpochs = Array(capacity).fill(0);
    applyConnectionEpochs(room, body.connectionEpochs);
    room.lastUsed = Date.now();
    rooms.set(roomId, room);
    metrics.roomsCreated++;
    if (body.snapshot && typeof body.snapshot === 'object') {
      factory.deserialize(room, body.snapshot);
    }
    if (['crazy8','pool'].includes(gameId) && body.begun !== true) factory.waitForClients(room);
  } else {
    applyConnectionEpochs(room, body.connectionEpochs);
  }
  if (['crazy8','pool'].includes(gameId) && body.begun === true) factory.beginMatch(room);
  room.lastUsed = Date.now();
  return room;
}

async function handler(req, res) {
  metrics.requests++;
  try {
    const u = new URL(req.url, `http://${req.headers.host || 'localhost'}`);
    if (req.method === 'GET' && u.pathname === '/health') {
      return json(res, 200, { ok: true, service: 'SamiDev Authoritative Game Host', rooms: rooms.size, games: gameHashes });
    }

    if (u.pathname === '/events' || u.pathname.startsWith('/v1/')) {
      if (!requireInternalAuth(req, res)) return;
    }
    if (req.method === 'GET' && u.pathname === '/v1/metrics') {
      const sorted = [...moveDurations].sort((a,b)=>a-b);
      return json(res, 200, {ok:true, ...metrics, rooms:rooms.size, memory:process.memoryUsage(),
        eventLoopDelayMs:{mean:eventLoopDelay.mean/1e6,p95:eventLoopDelay.percentile(95)/1e6,max:eventLoopDelay.max/1e6},
        recentMoveMs:{count:sorted.length,p50:sorted[Math.floor(sorted.length*.5)]||0,p95:sorted[Math.floor(sorted.length*.95)]||0,max:sorted.at(-1)||0}});
    }

    if (req.method === 'GET' && u.pathname === '/events') {
      res.writeHead(200, {
        'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', Connection: 'keep-alive',
        'X-Accel-Buffering': 'no', 'X-Content-Type-Options': 'nosniff',
      });
      res.write(`data: ${JSON.stringify({ type: 'hello', games: gameHashes })}\n\n`);
      sseClients.add(res);
      req.on('close', () => sseClients.delete(res));
      return;
    }
    if (req.method === 'GET' && u.pathname.startsWith('/v1/room/')) {
      const authorityOnly = u.pathname.endsWith('/authority');
      const roomId = normalizeRoomId(decodeURIComponent(u.pathname.slice('/v1/room/'.length).replace(/\/authority$/, '')));
      const room = rooms.get(roomId);
      if (!room) return json(res, 404, { ok: false, code: 'ROOM_NOT_LOADED' });
      room.lastUsed = Date.now();
      if (authorityOnly) return json(res, 200, {ok:true, roomId,
        authorityEpoch:room.authorityEpoch, revision:room.authorityRevision,
        turn:[...room.logic.turn], sequence:[...room.logic._sequence],
        lastValidAnim:Number.isFinite(room.logic.lastValidAnim)?room.logic.lastValidAnim:null,
        gameOver:!!room.logic.gameOver, nextAlarmId:Number(room.logic._nextAlarmId || 0)});
      return json(res, 200, { ok: true, ...roomSummary(room, true) });
    }
    if (req.method === 'DELETE' && u.pathname.startsWith('/v1/room/')) {
      const roomId = normalizeRoomId(decodeURIComponent(u.pathname.slice('/v1/room/'.length)));
      const room = rooms.get(roomId);
      if (room) room.factory.destroyRoom(room);
      rooms.delete(roomId);
      return json(res, 200, { ok: true });
    }
    if (req.method !== 'POST') return json(res, 404, { ok: false, code: 'NOT_FOUND' });

    const body = await readBody(req);
    if (u.pathname === '/v1/room/init') {
      const room = ensureRoom(body);
      return json(res, 200, { ok: true, ...roomSummary(room, true) });
    }
    if (u.pathname === '/v1/room/claim-connection') {
      const roomId = normalizeRoomId(body.roomId);
      const room = rooms.get(roomId);
      if (!room) return json(res, 404, { ok: false, code: 'ROOM_NOT_LOADED' });
      const authorityEpoch = normalizeEpoch(body.authorityEpoch, room.authorityEpoch);
      if (authorityEpoch !== room.authorityEpoch) return json(res, 409, { ok: false, code: 'STALE_AUTHORITY' });
      const seat = Number(body.seat);
      const connectionEpoch = Number(body.connectionEpoch);
      if (!Number.isInteger(seat) || seat < 0 || seat >= room.capacity || !Number.isInteger(connectionEpoch) || connectionEpoch < 1) {
        return json(res, 400, { ok: false, code: 'BAD_CONNECTION_CLAIM' });
      }
      room.connectionEpochs[seat] = Math.max(room.connectionEpochs[seat] || 0, connectionEpoch);
      room.lastUsed = Date.now();
      return json(res, 200, { ok: true, roomId, seat, connectionEpoch: room.connectionEpochs[seat], authorityEpoch: room.authorityEpoch });
    }
    if (u.pathname === '/v1/room/move') {
      metrics.moves++;
      const roomId = normalizeRoomId(body.roomId);
      let room = rooms.get(roomId);
      if (!room) {
        if (!body.settings || !body.capacity) return json(res, 404, { ok: false, code: 'ROOM_NOT_LOADED' });
        room = ensureRoom(body);
      }
      const authorityEpoch = normalizeEpoch(body.authorityEpoch, room.authorityEpoch);
      if (authorityEpoch !== room.authorityEpoch) return json(res, 409, { ok: false, code: 'STALE_AUTHORITY' });

      const seat = Number(body.seat);
      const connectionEpoch = Number(body.connectionEpoch);
      const packet = structuredClone(body.packet);
      if (!Number.isInteger(seat) || seat < 0 || seat >= room.capacity || !packet || typeof packet !== 'object') {
        return json(res, 400, { ok: false, code: 'BAD_MOVE' });
      }
      if (!Number.isInteger(connectionEpoch) || connectionEpoch < 1 || connectionEpoch !== Number(room.connectionEpochs[seat] || 0)) {
        return json(res, 409, { ok: false, code: 'STALE_CONNECTION', message: 'connection epoch is no longer current' });
      }

      const beforeSeq = Array.isArray(room.logic._sequence) ? room.logic._sequence[seat] : null;
      let accepted = false;
      let revealBySeat = {};
      let rejectionReason;
      let error = false;
      const moveStart = performance.now();
      try {
        room.opDepth++;
        const result = room.factory.processMove(room, seat, packet);
        accepted = result.accepted;
        if (accepted) room.authorityRevision++;
        revealBySeat = result.revealBySeat || {};
        rejectionReason = result.rejectionReason;
      } catch (e) {
        error = true;
        console.error('[SamiDev GameHost] GAMELOGIC_EXCEPTION', roomId, String(e.stack || e));
      } finally {
        room.opDepth--;
        moveDurations.push(performance.now()-moveStart);
        if(moveDurations.length>2048) moveDurations.shift();
      }
      room.lastUsed = Date.now();
      const desc = room.factory.describeRoom(room, true);
      if (accepted) metrics.accepted++; else metrics.rejected++;
      return json(res, 200, {
        ok: !error,
        accepted,
        code: error ? 'GAMELOGIC_EXCEPTION' : (accepted ? 'ACCEPTED' : 'REJECTED_BY_GAMELOGIC'),
        rejectionReason: !accepted && !error && room.gameId === 'pool' ? (rejectionReason || 'UNKNOWN') : undefined,
        rejectionContext: !accepted && !error && room.gameId === 'pool' ? {turn: Array.isArray(room.logic.turn) ? [...room.logic.turn] : [], ballInHand: room.logic.ballInHand, gameOver: !!room.logic.gameOver, moveAction: packet?.m?.a ?? null, packetSequence: Number.isSafeInteger(packet?.n) ? packet.n : null, expectedSequence: beforeSeq} : undefined,
        error: error ? 'GameLogic execution failed' : null,
        roomId: room.roomId,
        authorityEpoch: room.authorityEpoch,
        authorityRevision: room.authorityRevision,
        seat,
        packet,
        revealBySeat,
        expectedBefore: beforeSeq,
        ...desc,
      });
    }
    return json(res, 404, { ok: false, code: 'NOT_FOUND' });
  } catch (e) {
    metrics.errors++;
    const status = e.statusCode || 500;
    const code = e.code || (status === 500 ? 'GAMEHOST_ERROR' : 'BAD_REQUEST');
    if (status >= 500) console.error('[SamiDev GameHost] internal error', String(e.stack || e));
    return json(res, status, { ok: false, code, message: status >= 500 ? 'internal GameHost error' : String(e.message || e) });
  }
}

const server = http.createServer(handler);
server.keepAliveTimeout = 65000;
server.headersTimeout = 66000;
server.listen(PORT, HOST, () => {
  console.log(`[SamiDev GameHost] http://${HOST}:${PORT} games=${Object.keys(gameHashes).join(',')} rooms=0`);
});

const sweep = setInterval(() => {
  const cutoff = Date.now() - ROOM_IDLE_MS;
  for (const [id, room] of rooms) {
    if ((room.lastUsed || 0) < cutoff) {
      room.factory.destroyRoom(room);
      rooms.delete(id);
    }
  }
}, 60000);
sweep.unref();
const streamHeartbeat = setInterval(() => {
  for (const res of [...sseClients]) {
    try { res.write(': heartbeat\n\n'); if (res.writableLength > 2 * 1024 * 1024) { sseClients.delete(res); res.destroy(); } }
    catch { sseClients.delete(res); res.destroy(); }
  }
}, 10000);
streamHeartbeat.unref();

function shutdown() {
  clearInterval(sweep);
  clearInterval(streamHeartbeat);
  for (const res of sseClients) res.end();
  for (const room of rooms.values()) room.factory.destroyRoom(room);
  server.close(() => process.exit(0));
  setTimeout(() => process.exit(1), 3000).unref();
}
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
