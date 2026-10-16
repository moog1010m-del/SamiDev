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
  let healthTimer = null;
  let lastServerMessageAt = 0;
  const pendingMoves = new Map();
  let runtimeIsReady = false;

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

  function socketUrl(ticketOverride) {
    // Always use this origin's gateway. Never send a game ticket to an override.
    const u = new URL('/ws', location.href);
    u.protocol = u.protocol === 'https:' ? 'wss:' : 'ws:';
    const q = new URLSearchParams(window.__SAMIDEV_QUERY ?? location.search);
    const ticket = ticketOverride ?? q.get('ticket');
    if (ticket) u.searchParams.set('ticket', ticket);
    return u.toString();
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
    lastServerMessageAt = Date.now();
    if (['created','joined','watching'].includes(msg.type)) {
      state.chatCorrelation=msg.chatCorrelation===true;state.chatStickers=msg.chatStickers===true;
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
        state.ownerSeat=msg.ownerSeat??state.ownerSeat??0;state.waitingExpiresAt=msg.waitingExpiresAt??state.waitingExpiresAt;
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
        state.ownerSeat=msg.ownerSeat??state.ownerSeat??0;state.waitingExpiresAt=msg.waitingExpiresAt??state.waitingExpiresAt;
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
        if (msg.seat === state.seat && msg.packet?.i) pendingMoves.delete(msg.packet.i);
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
        pendingMoves.clear();
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
      case 'sync_required':
        if (state.started) requestResync();
        if (!state.begun && state.roomId) send({type:'ping', t:Date.now(), waiting:true});
        emit('sync_required', msg);
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
      case 'match_reward':
        emit('match_reward', msg);
        break;
      case 'chat_message':
        if(msg.clientMessageId)state.chatHistory=state.chatHistory.filter(old=>!(old.pending&&old.seat===msg.seat&&old.clientMessageId===msg.clientMessageId));
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
        if(['ROOM_WAIT_EXPIRED','TABLE_CLOSED','TABLE_KICKED','COMMUNITY_BANNED','COMMUNITY_KICKED'].includes(msg.reason)&&!document.documentElement.hasAttribute('data-sd-native')){
          const cid=state.communityId||'majlis';location.assign('/platform/?community='+encodeURIComponent(cid)+'&notice='+encodeURIComponent(msg.reason));
        }
        break;
      case 'error':
        emit('error', msg);
        if (inviteRequest) { const r = inviteRequest; inviteRequest = null; r.reject(Object.assign(new Error(msg.message || msg.code || 'Invite error'), {code: msg.code, detail: msg})); }
        if (!state.started && startReject) startReject(new Error(msg.message || msg.code || 'Network error'));
        break;
      case 'pong':
        if (msg.authority && state.started) emit('authority_probe', msg.authority);
        if (msg.syncUnavailable) emit('sync_unavailable', msg);
        emit('pong', msg);
        break;
    }
  }

  function startHealthMonitor() {
    if (healthTimer !== null) clearInterval(healthTimer);
    lastServerMessageAt = Date.now();
    healthTimer = setInterval(() => {
      if (!state.connected || state.intentionalClose) return;
      if (Date.now() - lastServerMessageAt > 20000) {
        // Mobile networks can leave a socket OPEN even though nothing can reach it.
        state.ws?.close(4000, 'heartbeat timeout');
        return;
      }
      send({type:'ping', t:Date.now(), authority:state.started, waiting:!!state.roomId&&!state.begun});
      if (runtimeIsReady && state.started && !state.begun && !state.roster[state.seat]?.ready) runtimeReady();
      if (state.started && [...pendingMoves.values()].some(sentAt => Date.now()-sentAt > 8000)) requestResync();
    }, 5000 + Math.floor(Math.random() * 1000));
  }

  async function freshBrowserTicket(communityId) {
    // Flutter supplies its ticket through the native gateway; the web can renew
    // the single-use ticket with its secure session cookie after a failed attempt.
    if (window.__SAMIDEV_QUERY !== undefined) return undefined;
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 8000);
    try {
      const response = await fetch('/api/game-ticket', {method:'POST', credentials:'same-origin',
        headers:{'Content-Type':'application/json'}, body:JSON.stringify({communityId}), signal:controller.signal});
      if (response.status === 401) throw new Error('انتهت الجلسة، سجّل الدخول مجددًا');
      if (!response.ok) throw new Error('تعذر تجديد اتصال اللعبة');
      return (await response.json()).ticket;
    } finally { clearTimeout(timer); }
  }

  function openSocket(url) {
    return new Promise((resolve, reject) => {
      const ws = new WebSocket(url);
      let done = false;
      const finish = (error) => {
        if (done) return;
        done = true; clearTimeout(timer);
        ws.removeEventListener('open', opened); ws.removeEventListener('error', failed); ws.removeEventListener('close', failed);
        if (error) { try { ws.close(); } catch (_) {} reject(error); }
        else resolve(ws);
      };
      const opened = () => finish();
      const failed = () => finish(new Error('تعذر الاتصال بـ SamiDev Game Server'));
      const timer = setTimeout(() => finish(new Error('انتهت مهلة الاتصال بالسيرفر')), 8000);
      ws.addEventListener('open', opened);
      ws.addEventListener('error', failed);
      ws.addEventListener('close', failed);
    });
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
    let ws, lastError, renewedTicket;
    for (let attempt = 0; attempt < 3; attempt++) {
      try {
        if (attempt > 0) {
          progress?.('إعادة الاتصال بخادم اللعبة...');
          await new Promise(resolve => setTimeout(resolve, 500 * attempt + Math.floor(Math.random() * 500)));
          renewedTicket = await freshBrowserTicket(q.get('community') || 'majlis');
        }
        ws = await openSocket(socketUrl(renewedTicket));
        break;
      } catch (error) { lastError = error; }
    }
    if (!ws) throw lastError;
    state.ws = ws;
    state.connected = true;

    ws.addEventListener('message', ev => {
      try { handleMessage(JSON.parse(ev.data)); }
      catch (e) { console.warn('[SamiDev Network] bad message', e); }
    });
    ws.addEventListener('close', ev => {
      if (healthTimer !== null) { clearInterval(healthTimer); healthTimer = null; }
      state.connected = false;
      pendingMoves.clear();
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
    startHealthMonitor();

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

    if (action === 'quick') {
      send({type:'quick_play',preset:q.get('preset') || '',name});
      progress?.('البحث عن لاعب بنفس قواعد المباراة…');
    } else if (action === 'create') {
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
    const sent = send({type: 'move', packet});
    if (sent && packet?.i && !packet.__info) {
      if (pendingMoves.size >= 256) pendingMoves.delete(pendingMoves.keys().next().value);
      pendingMoves.set(packet.i, Date.now());
    }
    return sent;
  }

  function runtimeReady() {
    if (state.spectator) return false;
    runtimeIsReady = true;
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
    return sendChatPacket({text:value.slice(0,max)});
  }

  function sendChatPacket(fields){
    const nonce=globalThis.crypto?.randomUUID?.()||('chat_'+Date.now().toString(36)+'_'+Math.random().toString(36).slice(2));const sent=send({type:'chat_send',...fields,...(state.chatCorrelation?{clientMessageId:nonce}:{})});
    if(sent&&state.chatCorrelation){const pending={id:'pending_'+nonce,clientMessageId:nonce,seat:state.seat,text:'',...fields,stickerAsset:fields.previewAsset,pending:true,ts:Date.now()};emit('chat_message',pending);}
    if(sent)window.SamiDevCosmetics?.pop();return sent;
  }
  function sendSticker(id,asset){if(state.spectator||!state.chatStickers||typeof id!=='string')return false;return sendChatPacket({stickerId:id,previewAsset:asset});}

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
    sendChat,sendSticker,
    requestChatHistory,
    createInvite,
    leaveRoom,
  };
  if (typeof document !== 'undefined') document.addEventListener('visibilitychange', () => {
    if (document.visibilityState === 'visible' && state.connected && state.started) {
      // Give the foreground connection a new heartbeat window and reconcile the
      // state after mobile browsers throttle timers in the background.
      lastServerMessageAt = Date.now();
      send({type:'ping', t:Date.now(), authority:true});
      requestResync();
    }
  });
})();
