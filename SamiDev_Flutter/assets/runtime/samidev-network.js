(() => {
  'use strict';

  const listeners = new Map();
  const state = {
    ws: null,
    connected: false,
    roomId: null,
    gameId: window.SamiDevGames.current().id,
    communityId: null,
    seat: null,
    token: null,
    capacity: 0,
    settings: null,
    roster: [],
    started: false,
    lastMoveIndex: -1,
    moveCount: 0,
    startData: null,
    reconnecting: false,
    intentionalClose: false,
    begun: false,
    spectator: false,
    chatHistory: [],
    // Coalesce resync requests so one transient mismatch cannot create a resync storm.
    resyncInFlight: false,
    resyncSentAt: 0,
  };

  let startResolve, startReject;
  let startPromise = new Promise((resolve, reject) => { startResolve = resolve; startReject = reject; });
  let inviteRequest = null;

  function emit(type, payload) {
    const list = listeners.get(type);
    if (!list) return;
    for (const fn of [...list]) {
      try { fn(payload); } catch (e) { console.error('[SamiDev Network] listener', type, e); }
    }
  }

  function on(type, fn) {
    if (!listeners.has(type)) listeners.set(type, []);
    listeners.get(type).push(fn);
    return () => off(type, fn);
  }

  function off(type, fn) {
    const list = listeners.get(type);
    if (!list) return;
    const i = list.indexOf(fn);
    if (i >= 0) list.splice(i, 1);
  }

  function socketUrl() {
    const base = window.__SAMIDEV_WS_URL || `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`;
    try {
      const q = new URLSearchParams(window.__SAMIDEV_QUERY ?? location.search);
      const ticket = q.get('ticket');
      if (!ticket) return base;
      const u = new URL(base, location.href);
      u.searchParams.set('ticket', ticket);
      return u.toString();
    } catch (_) { return base; }
  }

  function send(payload) {
    if (!state.ws || state.ws.readyState !== WebSocket.OPEN) return false;
    state.ws.send(JSON.stringify(payload));
    return true;
  }

  function updateUrlCredentials() {
    if (!state.roomId || (!state.token && !state.spectator)) return;
    try {
      sessionStorage.setItem('samidev_reconnect', JSON.stringify({
        roomId:state.roomId, token:state.token, communityId:state.communityId, gameId:state.gameId,
        spectator:!!state.spectator, ts:Date.now()
      }));
      if(state.communityId)sessionStorage.setItem('samidev_return_community',state.communityId);
    } catch (_) {}
    if(window.__SAMIDEV_QUERY !== undefined) return;
    const u = new URL(location.href);
    u.searchParams.set('online', '1');
    u.searchParams.set('action', state.spectator ? 'watch' : 'join');
    u.searchParams.set('room', state.roomId);
    if(state.communityId)u.searchParams.set('community',state.communityId);
    u.searchParams.delete('token');
    u.searchParams.delete('ticket');
    history.replaceState(null, '', u);
  }

  function handleMessage(msg) {
    if (['created','joined','watching'].includes(msg.type)) {
      state.gameId = msg.settings?.gameId || 'carrom';
      if (state.gameId !== window.SamiDevGames.current().id) {
        state.roomId=msg.roomId; state.token=msg.token; state.communityId=msg.communityId;
        state.spectator=msg.type==='watching';
        updateUrlCredentials(); state.intentionalClose=true; state.ws?.close();
        const q=new URLSearchParams({online:'1',action:state.spectator?'watch':'join',room:msg.roomId});
        if(msg.communityId)q.set('community',msg.communityId);
        location.replace(window.SamiDevGames.get(state.gameId).entry+'?'+q);
        return;
      }
    }
    switch (msg.type) {
      case 'created':
      case 'joined':
        state.spectator = false;
        state.roomId = msg.roomId;
        state.communityId = msg.communityId || state.communityId || new URLSearchParams(window.__SAMIDEV_QUERY ?? location.search).get('community') || null;
        try{if(state.communityId)sessionStorage.setItem('samidev_return_community',state.communityId);}catch(_){}
        state.seat = msg.seat;
        state.token = msg.token;
        state.capacity = msg.capacity;
        state.settings = msg.settings;
        state.roster = msg.roster || [];
        state.started = !!msg.started;
        state.begun = !!msg.begun;
        updateUrlCredentials();
        emit('assignment', msg);
        break;
      case 'watching':
        state.spectator = true;
        state.roomId = msg.roomId;
        state.communityId = msg.communityId || state.communityId || new URLSearchParams(window.__SAMIDEV_QUERY ?? location.search).get('community') || null;
        try{if(state.communityId)sessionStorage.setItem('samidev_return_community',state.communityId);}catch(_){}
        state.seat = -1;
        state.token = null;
        state.capacity = msg.capacity;
        state.settings = msg.settings;
        state.roster = msg.roster || [];
        state.started = true;
        state.begun = true;
        updateUrlCredentials();
        emit('assignment', msg);
        break;
      case 'invite_created':
        emit('invite_created', msg);
        if (inviteRequest) { const r = inviteRequest; inviteRequest = null; r.resolve(msg); }
        break;
      case 'room_state':
        if(msg.communityId)state.communityId=msg.communityId;
        state.roster = msg.roster || [];
        state.capacity = msg.capacity || state.capacity;
        state.settings = msg.settings || state.settings;
        state.started = !!msg.started;
        state.begun = !!msg.begun;
        if (Number.isInteger(msg.moveCount)) state.moveCount = Math.max(state.moveCount, msg.moveCount);
        emit('room_state', msg);
        break;
      case 'start':
        state.started = true;
        state.spectator = !!msg.spectator || state.spectator;
        state.startData = msg;
        state.settings = msg.settings;
        state.roster = msg.roster || [];
        state.moveCount = msg.moveCount || 0;
        startResolve(msg);
        emit('start', msg);
        break;
      case 'begin_match':
        state.begun = true;
        emit('begin_match', msg);
        break;
      case 'move':
        if (!msg.infoAck && Number.isInteger(msg.moveIndex)) {
          state.lastMoveIndex = Math.max(state.lastMoveIndex, msg.moveIndex);
          state.moveCount = Math.max(state.moveCount, msg.moveIndex + 1);
        }
        emit('move', msg);
        break;
      case 'desync':
        emit('desync', msg);
        break;
      case 'resync_state':
        // The server has answered the outstanding request. Browser runtime may now
        // apply the snapshot/history without another request being emitted in parallel.
        state.resyncInFlight = false;
        state.resyncSentAt = 0;
        emit('resync_state', msg);
        break;
      case 'authority_state':
        emit('authority_state', msg);
        break;
      case 'authority_alarm':
        emit('authority_alarm', msg);
        break;
      case 'spectator_resync':
        emit('spectator_resync', msg);
        break;
      case 'snapshot_ignored':
        emit('snapshot_ignored', msg);
        break;
      case 'chat_history':
        state.chatHistory = Array.isArray(msg.messages) ? msg.messages.slice(-30) : [];
        emit('chat_history', {messages: state.chatHistory});
        break;
      case 'chat_message':
        state.chatHistory.push(msg);
        if (state.chatHistory.length > 30) state.chatHistory.splice(0, state.chatHistory.length - 30);
        emit('chat_message', msg);
        break;
      case 'left_room':
        state.intentionalClose = true;
        state.roomId = null;
        state.seat = null;
        state.token = null;
        state.capacity = 0;
        state.settings = null;
        state.roster = [];
        state.started = false;
        state.begun = false;
        state.spectator = false;
        state.startData = null;
        try { sessionStorage.removeItem('samidev_reconnect'); } catch (_) {}
        emit('left_room', msg);
        break;
      case 'error':
        emit('error', msg);
        if (inviteRequest) { const r = inviteRequest; inviteRequest = null; r.reject(Object.assign(new Error(msg.message || msg.code || 'Invite error'), {code: msg.code, detail: msg})); }
        if (!state.started && startReject) startReject(new Error(msg.message || msg.code || 'Network error'));
        break;
      case 'pong':
        emit('pong', msg);
        break;
    }
  }

  async function connectFromLocation(progress) {
    const q = new URLSearchParams(window.__SAMIDEV_QUERY ?? location.search);
    const roomId = (q.get('room') || '').toUpperCase();
    const inviteToken = String(q.get('invite') || '').trim();
    let action = inviteToken ? 'invite' : (q.get('action') || (roomId ? 'join' : 'create'));
    const name = (q.get('name') || `Player ${Math.floor(Math.random() * 900 + 100)}`).slice(0, 24);
    let token = q.get('token') || '';
    if (!token && roomId) {
      try {
        const saved = JSON.parse(sessionStorage.getItem('samidev_reconnect') || 'null');
        if (saved && saved.roomId === roomId) {
          if (typeof saved.token === 'string') token = saved.token;
          if(saved.communityId)state.communityId=saved.communityId;
          if(saved.spectator && !q.get('action')) action='watch';
        }
      } catch (_) {}
    }
    const settings = window.SamiDevGames.settings(q);

    progress?.('الاتصال بـ SamiDev Game Server...');
    const ws = new WebSocket(socketUrl());
    state.ws = ws;

    await new Promise((resolve, reject) => {
      const timeout = setTimeout(() => reject(new Error('انتهت مهلة الاتصال بالسيرفر')), 8000);
      ws.addEventListener('open', () => {
        clearTimeout(timeout);
        state.connected = true;
        resolve();
      }, {once: true});
      ws.addEventListener('error', () => {
        clearTimeout(timeout);
        reject(new Error('تعذر الاتصال بـ SamiDev Game Server'));
      }, {once: true});
    });

    ws.addEventListener('message', ev => {
      try { handleMessage(JSON.parse(ev.data)); }
      catch (e) { console.warn('[SamiDev Network] bad message', e); }
    });
    ws.addEventListener('close', ev => {
      state.connected = false;
      state.resyncInFlight = false;
      state.resyncSentAt = 0;
      if(ev?.code===4003){state.intentionalClose=true;try{sessionStorage.removeItem('samidev_reconnect');}catch(_){}emit('error',{code:'AUTH_REQUIRED',message:'انتهت الجلسة، سجّل الدخول مجددًا'});}
      const replaced = ev?.code === 4001;
      if (replaced) state.intentionalClose = true;
      emit('disconnect', {code: ev?.code || 0, replaced});
      if (state.roomId && (state.token || state.spectator) && !state.reconnecting && !state.intentionalClose) {
        state.reconnecting = true;
        const delay = 600 + Math.floor(Math.random() * 900);
        setTimeout(() => {
          try { location.reload(); } catch (_) {}
        }, delay);
      }
    });

    // Progress listeners are only valid while waiting for the start packet. Keeping them
    // alive after start caused later room_state broadcasts (for example runtime_ready) to
    // re-show the "waiting for players" overlay on top of a running/initializing game.
    const offAssignment = on('assignment', a => {
      if (a?.spectator) progress?.(`مشاهدة المباراة ${a.roomId}...`);
      else if (!state.started) progress?.(`الغرفة ${a.roomId} — أنت Player ${a.seat + 1}. انتظار بقية اللاعبين...`);
    });
    const offRoomState = on('room_state', r => {
      if (state.started) return;
      const connected = (r.roster || []).filter(x => x && x.connected).length;
      progress?.(`الغرفة ${r.roomId} — متصل ${connected}/${r.capacity}. انتظار بقية اللاعبين...`);
    });

    if (action === 'create') {
      send({type: 'create_room', name, settings});
      progress?.('إنشاء غرفة SamiDev...');
    } else if (action === 'invite') {
      send({type: 'join_invite', inviteToken, name});
      progress?.('فتح دعوة المباراة...');
    } else if (action === 'watch') {
      send({type: 'watch_room', roomId, name});
      progress?.(`فتح مشاهدة المباراة ${roomId || '...'}...`);
    } else {
      send({type: 'join_room', roomId, token, name});
      progress?.(`الدخول إلى الغرفة ${roomId || '...'}...`);
    }

    try {
      return await startPromise;
    } finally {
      offAssignment();
      offRoomState();
    }
  }

  function sendMove(packet) {
    if (state.spectator) return false;
    return send({type: 'move', packet});
  }

  function runtimeReady() {
    if (state.spectator) return false;
    return send({type: 'runtime_ready'});
  }

  function sendSnapshot(snapshot, moveCount = state.moveCount) {
    if (!snapshot || typeof snapshot !== 'object') return false;
    return send({type: 'snapshot', state: snapshot, moveCount});
  }

  function requestResync() {
    const now = Date.now();
    // Allow a retry if a response was genuinely lost, but suppress duplicate requests
    // while the first one is still travelling through the socket/server.
    if (state.resyncInFlight && now - state.resyncSentAt < 1500) return false;
    const sent = send({type: 'resync'});
    if (sent) {
      state.resyncInFlight = true;
      state.resyncSentAt = now;
    }
    return sent;
  }

  function ping() {
    return send({type: 'ping', t: Date.now()});
  }

  function sendChat(text) {
    if (state.spectator) return false;
    const value = String(text || '').trim();
    if (!value) return false;
    const max = Number(window.__SAMIDEV_CLIENT_CONFIG?.chatMaxChars || 160);
    return send({type:'chat_send', text:value.slice(0, max)});
  }

  function requestChatHistory() {
    return send({type:'chat_history'});
  }

  async function createInvite() {
    if (!state.roomId || !state.ws || state.ws.readyState !== WebSocket.OPEN) throw new Error('لا يوجد اتصال بغرفة');
    if (state.started) throw Object.assign(new Error('المباراة اكتملت ولا يمكن إرسال دعوة جديدة'), {code:'MATCH_STARTED'});
    if (inviteRequest) return inviteRequest.promise;
    let resolveFn, rejectFn;
    const promise = new Promise((resolve, reject) => { resolveFn = resolve; rejectFn = reject; });
    const timer = setTimeout(() => {
      if (!inviteRequest) return;
      inviteRequest = null;
      rejectFn(Object.assign(new Error('انتهت مهلة إنشاء الدعوة'), {code:'INVITE_TIMEOUT'}));
    }, 4000);
    inviteRequest = {
      promise,
      resolve: v => { clearTimeout(timer); resolveFn(v); },
      reject: e => { clearTimeout(timer); rejectFn(e); },
    };
    if (!send({type:'create_invite'})) {
      const r = inviteRequest; inviteRequest = null; clearTimeout(timer); r.reject(new Error('تعذر إرسال طلب الدعوة'));
    }
    return promise;
  }

  async function leaveRoom({closeSocket=true}={}) {
    if (!state.roomId || !state.ws || state.ws.readyState !== WebSocket.OPEN) {
      state.intentionalClose = true;
      try { sessionStorage.removeItem('samidev_reconnect'); } catch (_) {}
      if (closeSocket && state.ws && state.ws.readyState < WebSocket.CLOSING) state.ws.close(1000, 'left room');
      return {ok: true, alreadyLeft: true};
    }
    state.intentionalClose = true;
    const result = await new Promise(resolve => {
      let done = false;
      const finish = value => { if (done) return; done = true; offLeft(); offError(); clearTimeout(timer); resolve(value); };
      const offLeft = on('left_room', msg => finish({ok: true, message: msg}));
      const offError = on('error', msg => finish({ok: false, error: msg}));
      const timer = setTimeout(() => finish({ok: false, timeout: true}), 2500);
      if (!send({type: 'leave_room'})) finish({ok: false, sendFailed: true});
    });
    try { sessionStorage.removeItem('samidev_reconnect'); } catch (_) {}
    if (closeSocket && state.ws && state.ws.readyState < WebSocket.CLOSING) state.ws.close(1000, 'left room');
    return result;
  }

  window.SamiDevNetwork = {
    state,
    on,
    off,
    send,
    connectFromLocation,
    sendMove,
    runtimeReady,
    sendSnapshot,
    requestResync,
    ping,
    sendChat,
    requestChatHistory,
    createInvite,
    leaveRoom,
  };
})();
