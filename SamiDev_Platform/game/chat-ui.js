(() => {
  'use strict';

  let root, list, form, input, errorBox, launcher, unreadBadge, closeBtn, backdrop;
  let visible = false;
  let mobileOpen = false;
  let unread = 0;
  const seen = new Set();
  const messages = [];
  let renderedRows=new Map();

  const net = () => window.SamiDevNetwork;
  const platform = () => window.SamiDevPlatform;
  const mobileQuery = window.matchMedia('(max-width: 820px), (hover: none) and (pointer: coarse)');
  const isMobileLayout = () => !!mobileQuery.matches;

  function playerForSeat(seat) {
    const roster = net()?.state?.roster || [];
    return roster.find(p => p && Number(p.seat) === Number(seat)) || null;
  }

  function initials(name) {
    const parts = String(name || 'P').trim().split(/\s+/).filter(Boolean);
    return (parts.slice(0, 2).map(x => x[0] || '').join('') || 'P').toUpperCase();
  }

  const DEFAULT_AVATAR_URL = '/images/default-avatar.png';
  function avatarFor(player) {
    const wrap = document.createElement('div');
    wrap.className = 'sd-chat-avatar';
    const img = document.createElement('img');
    const accountId = String(player?.accountId || '').trim();
    img.alt = '';
    img.src = accountId ? `/api/avatar/${encodeURIComponent(accountId)}` : DEFAULT_AVATAR_URL;
    img.onerror = () => { if (!img.src.endsWith(DEFAULT_AVATAR_URL)) img.src = DEFAULT_AVATAR_URL; };
    wrap.appendChild(img);
    return wrap;
  }

  function render() {
    if (!list) return;
    const recent = messages.slice(-30);
    const nearBottom=list.scrollHeight-list.scrollTop-list.clientHeight<70,nextRows=new Map(),nodes=[];
    for (const [index,msg] of recent.entries()) {
      const player = playerForSeat(msg.seat);
      const key=String(msg.id||JSON.stringify([msg.seat,msg.text,index]));
      const signature=JSON.stringify([msg,player?.accountId,player?.name,net()?.state?.seat]);
      const cached=renderedRows.get(key);
      if(cached?.signature===signature){nextRows.set(key,cached);nodes.push(cached.row);continue;}
      const row = document.createElement('div');
      row.className = 'sd-chat-message' + (msg.seat != null && net()?.state?.seat != null && Number(net()?.state?.seat)>=0 && Number(msg.seat) === Number(net()?.state?.seat) ? ' me' : '');
      const av = avatarFor(player);
      row.appendChild(av);

      const body = document.createElement('div');
      body.className = 'sd-chat-message-body';
      const name = document.createElement('span');
      name.className = 'sd-chat-name';
      name.textContent = String(player?.name || `Player ${Number(msg.seat) + 1}`);
      const text = document.createElement('span');
      text.className = 'sd-chat-text';
      text.textContent = String(msg.text || '');
      body.append(name,text);
      row.appendChild(body);

      const openSenderProfile = (e) => {
        e.preventDefault();
        e.stopPropagation();
        if (msg.seat !== undefined && msg.seat !== null) {
          if (isMobileLayout() && mobileOpen) closeMobileChat();
          if (window.SamiDev?.showProfile) {
            window.SamiDev.showProfile(msg.seat);
          } else if (window.SamiDevPlayerProfileUI?.openSeat) {
            window.SamiDevPlayerProfileUI.openSeat(msg.seat);
          }
        }
      };
      av.style.cursor = 'pointer';
      av.title = `الملف الشخصي: ${player?.name || ''}`;
      av.addEventListener('click', openSenderProfile);
      name.style.cursor = 'pointer';
      name.title = `الملف الشخصي: ${player?.name || ''}`;
      name.addEventListener('click', openSenderProfile);

      nextRows.set(key,{signature,row});nodes.push(row);
    }
    const keep=new Set(nodes);for(const child of [...list.children])if(!keep.has(child))child.remove();
    nodes.forEach((row,i)=>{if(list.children[i]!==row)list.insertBefore(row,list.children[i]||null);});
    renderedRows=nextRows;
    if(nearBottom)list.scrollTop = list.scrollHeight;
  }

  function updateUnread() {
    if (!unreadBadge) return;
    unreadBadge.textContent = unread > 99 ? '99+' : String(unread);
    unreadBadge.hidden = unread <= 0;
  }

  function addMessage(msg) {
    if (!msg || typeof msg !== 'object') return;
    const id = String(msg.id || '');
    if (id && seen.has(id)) return;
    if (id) seen.add(id);
    messages.push(msg);
    if (messages.length > 30) messages.splice(0, messages.length - 30);

    if (visible && isMobileLayout() && !mobileOpen && Number(msg.seat) !== Number(net()?.state?.seat)) {
      unread += 1;
      updateUnread();
    }
    render();
  }

  function setHistory(items) {
    messages.length = 0;
    seen.clear();
    for (const item of Array.isArray(items) ? items.slice(-30) : []) {
      const id = String(item?.id || '');
      if (id && seen.has(id)) continue;
      if (id) seen.add(id);
      if (item && typeof item === 'object') messages.push(item);
    }
    render();
  }

  function showError(text) {
    if (!errorBox) return;
    errorBox.textContent = String(text || '');
    errorBox.classList.add('show');
    clearTimeout(showError.timer);
    showError.timer = setTimeout(() => errorBox?.classList.remove('show'), 2200);
  }

  function sendCurrent() {
    if (net()?.state?.spectator) {
      showError('المشاهدة للقراءة فقط');
      return;
    }
    const value = String(input?.value || '').trim();
    if (!value) return;
    if (!net()?.sendChat?.(value)) {
      showError('تعذر إرسال الرسالة');
      return;
    }
    input.value = '';
    platform()?.haptic?.('selection');
    try { input.focus({preventScroll:true}); } catch (_) { input.focus(); }
  }

  function updateViewport() {
    if (!root) return;
    const vv = window.visualViewport;
    let offset = 0;
    if (vv && isMobileLayout()) {
      offset = Math.max(0, Math.round(window.innerHeight - vv.height - vv.offsetTop));
    }
    document.documentElement.style.setProperty('--sd-chat-keyboard-offset', `${offset}px`);
  }

  function openMobileChat({focus = true} = {}) {
    if (!visible || !isMobileLayout()) return;
    mobileOpen = true;
    unread = 0;
    updateUnread();
    root?.classList.add('mobile-open');
    document.body.classList.add('sd-chat-mobile-open');
    updateViewport();
    render();
    platform()?.haptic?.('selection');
    if (focus) {
      requestAnimationFrame(() => {
        try { input?.focus({preventScroll:true}); } catch (_) { input?.focus(); }
      });
    }
  }

  function closeMobileChat() {
    if (!mobileOpen) return;
    mobileOpen = false;
    root?.classList.remove('mobile-open', 'focused');
    document.body.classList.remove('sd-chat-mobile-open');
    try { input?.blur(); } catch (_) {}
    updateViewport();
  }

  let gameResizePending = false;

  function notifyGameResize() {
    if (gameResizePending) return;
    gameResizePending = true;
    requestAnimationFrame(() => {
      gameResizePending = false;
      window.dispatchEvent(new Event('resize'));
    });
  }

  function syncLayout() {
    if (!root) return;
    if (!isMobileLayout()) {
      mobileOpen = false;
      root.classList.remove('mobile-open');
      document.body.classList.remove('sd-chat-mobile-open');
    }
    // Never emit another resize from the resize handler itself. Doing so creates
    // an endless RAF -> resize -> syncLayout loop that repeatedly resynchronizes
    // the game and clears/rebuilds timer/UI state.
    updateViewport();
  }

  function showForRoom(show) {
    visible = !!show;
    root?.classList.toggle('room-active', visible);
    launcher?.classList.toggle('room-active', visible);
    document.body.classList.toggle('sd-chat-room-active', visible);

    if (!visible) {
      mobileOpen = false;
      unread = 0;
      updateUnread();
      root?.classList.remove('mobile-open', 'focused');
      document.body.classList.remove('sd-chat-mobile-open');
      messages.length = 0;
      seen.clear();
      render();
      try { input?.blur(); } catch (_) {}
    }
    updateViewport();
    notifyGameResize();
  }

  function build() {
    if (root) return;

    const style = document.createElement('style');
    style.textContent = `
      :root{
        --sd-chat-desktop-width:clamp(300px,24vw,360px);
        --sd-chat-keyboard-offset:0px;
        --sd-chat-safe-bottom:env(safe-area-inset-bottom,0px);
      }

      /* Desktop: reserve a real right-hand column for chat instead of covering or
         squeezing the board from the bottom. */
      @media (min-width:821px) and (hover:hover) and (pointer:fine){
        body.sd-chat-room-active #game{
          position:fixed!important;
          left:0!important;top:0!important;bottom:0!important;right:auto!important;
          width:calc(100vw - var(--sd-chat-desktop-width))!important;
          height:100vh!important;height:100dvh!important;
          max-width:none!important;max-height:none!important;
          display:block!important;
        }
        #sd-chat-ui{
          display:none;position:fixed;z-index:15000;top:0;right:0;bottom:0;
          width:var(--sd-chat-desktop-width);box-sizing:border-box;
          flex-direction:column;background:#11161d;color:#fff;
          border-left:1px solid rgba(255,255,255,.10);
          box-shadow:-10px 0 28px rgba(0,0,0,.24);
          font-family:system-ui,-apple-system,"Segoe UI",Arial,sans-serif;
        }
        #sd-chat-ui.room-active{display:flex}
        #sd-chat-backdrop,#sd-chat-close{display:none!important}
        #sd-chat-header{display:flex;align-items:center;min-height:58px;padding:0 17px;border-bottom:1px solid rgba(255,255,255,.09);font-size:16px;font-weight:800;direction:rtl}
        #sd-chat-messages{flex:1;min-height:0;overflow-y:auto;padding:14px 12px;display:flex;flex-direction:column;justify-content:flex-end;gap:9px;background:linear-gradient(180deg,#11161d,#0e1319)}
        #sd-chat-form{display:flex;direction:ltr;align-items:center;gap:8px;padding:11px 10px 13px;background:#0b0f14;border-top:1px solid rgba(255,255,255,.10)}
        #sd-chat-launcher{display:none!important}
      }

      /* Mobile/tablet touch layout: the board never changes size. Chat floats over
         the board only after the player taps the chat button. */
      @media (max-width:820px), (hover:none) and (pointer:coarse){
        body.sd-chat-room-active #game{
          position:fixed!important;inset:0!important;
          width:100vw!important;height:100vh!important;height:100dvh!important;
          max-width:none!important;max-height:none!important;display:block!important;
        }
        #sd-chat-ui{
          display:none;position:fixed;z-index:15000;inset:0 0 var(--sd-chat-keyboard-offset) 0;
          color:#fff;font-family:system-ui,-apple-system,"Segoe UI",Arial,sans-serif;
          pointer-events:none;
        }
        #sd-chat-ui.room-active.mobile-open{display:flex;flex-direction:column;justify-content:flex-end}
        #sd-chat-backdrop{
          position:absolute;inset:0;background:rgba(2,6,10,.25);pointer-events:auto;
          -webkit-tap-highlight-color:transparent;
        }
        #sd-chat-shell{
          position:relative;z-index:1;display:flex;flex-direction:column;
          width:100%;height:min(62vh,520px);max-height:calc(100vh - var(--sd-chat-keyboard-offset));min-height:0;
          background:linear-gradient(180deg,rgba(7,11,16,.30),rgba(7,11,16,.64) 48%,rgba(7,11,16,.88));
          border-top:1px solid rgba(255,255,255,.13);
          box-shadow:0 -14px 36px rgba(0,0,0,.18);
          pointer-events:auto;
        }
        #sd-chat-header{height:44px;flex:0 0 44px;display:flex;align-items:center;justify-content:space-between;padding:0 12px;box-sizing:border-box;direction:rtl;background:rgba(8,12,17,.32)}
        #sd-chat-title{font-size:14px;font-weight:800;text-shadow:0 1px 3px rgba(0,0,0,.75)}
        #sd-chat-close{width:34px;height:34px;border:0;border-radius:50%;background:rgba(0,0,0,.28);color:#fff;font-size:23px;line-height:1;display:grid;place-items:center;cursor:pointer}
        #sd-chat-messages{
          flex:1;min-height:0;overflow-y:auto;padding:8px 10px 10px;
          display:flex;flex-direction:column;justify-content:flex-end;gap:6px;
          background:transparent;text-shadow:0 1px 3px rgba(0,0,0,.92);
          -webkit-overflow-scrolling:touch;
        }
        #sd-chat-form{
          flex:0 0 auto;display:flex;direction:ltr;align-items:center;gap:7px;
          padding:8px 8px calc(8px + var(--sd-chat-safe-bottom));
          background:rgba(8,12,17,.72);border-top:1px solid rgba(255,255,255,.11);
          backdrop-filter:blur(5px);-webkit-backdrop-filter:blur(5px);
        }
        #sd-chat-launcher{
          display:none;position:fixed;z-index:14950;right:14px;
          bottom:calc(18px + env(safe-area-inset-bottom,0px));
          width:50px;height:50px;border:1px solid rgba(255,255,255,.20);border-radius:50%;
          background:rgba(15,23,32,.76);color:#fff;box-shadow:0 6px 22px rgba(0,0,0,.32);
          backdrop-filter:blur(7px);-webkit-backdrop-filter:blur(7px);
          cursor:pointer;font-size:22px;place-items:center;-webkit-tap-highlight-color:transparent;
        }
        #sd-chat-launcher.room-active{display:grid}
        #sd-chat-ui.mobile-open + #sd-chat-launcher{display:none}
        #sd-chat-unread{
          position:absolute;top:-4px;right:-4px;min-width:18px;height:18px;padding:0 4px;
          box-sizing:border-box;border-radius:10px;background:#e84955;color:#fff;border:2px solid #111820;
          font:700 10px/14px system-ui;text-align:center;
        }
      }

      #sd-chat-shell{display:contents}
      @media (max-width:820px), (hover:none) and (pointer:coarse){#sd-chat-shell{display:flex}}
      .sd-chat-message{display:flex;align-items:flex-start;gap:8px;min-height:30px;font-size:14px;line-height:1.4;direction:rtl;animation:sdChatIn .13s ease-out}
      .sd-chat-message.me .sd-chat-name{color:#7ec3ff}
      .sd-chat-name{font-weight:800;color:#ffd86b;cursor:pointer;transition:color .15s ease}
      .sd-chat-name:hover{text-decoration:underline;color:#ffe699}
      .sd-chat-message-body{min-width:0;overflow-wrap:anywhere;padding-top:3px}
      .sd-chat-avatar{width:30px;height:30px;flex:0 0 30px;border-radius:50%;display:grid;place-items:center;background:#273849;border:1px solid rgba(255,255,255,.18);overflow:hidden;text-shadow:none;cursor:pointer;transition:transform .15s ease}
      .sd-chat-avatar:hover{transform:scale(1.08)}.sd-chat-avatar img{width:100%;height:100%;object-fit:cover;display:block}
      #sd-chat-input{min-width:0;flex:1;height:42px;box-sizing:border-box;border:1px solid rgba(255,255,255,.18);border-radius:12px;background:rgba(5,8,12,.78);color:#fff;padding:0 12px;font:16px system-ui,-apple-system,"Segoe UI",Arial,sans-serif;outline:none;text-align:start;direction:auto;unicode-bidi:plaintext}
      #sd-chat-input::placeholder{color:rgba(255,255,255,.48)}
      #sd-chat-input:focus{border-color:rgba(83,168,255,.78);box-shadow:0 0 0 2px rgba(60,145,230,.13)}
      #sd-chat-send{width:44px;height:42px;flex:0 0 44px;border:0;border-radius:11px;background:#247bd6;color:#fff;font-size:22px;line-height:1;cursor:pointer;display:grid;place-items:center;transform:scaleX(-1)}
      #sd-chat-send:active{transform:scaleX(-1) scale(.94)}
      #sd-chat-error{position:absolute;z-index:3;left:50%;bottom:calc(66px + var(--sd-chat-safe-bottom));transform:translate(-50%,8px);opacity:0;max-width:90vw;padding:7px 10px;border-radius:9px;background:rgba(180,43,54,.96);font-size:12px;transition:.15s;pointer-events:none;white-space:nowrap}
      #sd-chat-error.show{opacity:1;transform:translate(-50%,0)}
      @keyframes sdChatIn{from{opacity:0;transform:translateY(3px)}to{opacity:1;transform:none}}
    `;
    document.head.appendChild(style);

    root = document.createElement('section');
    root.id = 'sd-chat-ui';
    root.setAttribute('aria-label', 'محادثة المباراة');
    root.innerHTML = `
      <div id="sd-chat-backdrop" aria-hidden="true"></div>
      <div id="sd-chat-shell">
        <div id="sd-chat-header">
          <span id="sd-chat-title">محادثة المباراة</span>
          <button id="sd-chat-close" type="button" aria-label="إغلاق الشات">×</button>
        </div>
        <div id="sd-chat-messages" aria-live="polite"></div>
        <div id="sd-chat-error" role="status"></div>
        <form id="sd-chat-form" autocomplete="off">
          <button id="sd-chat-send" type="submit" aria-label="إرسال"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="m21 3-7 18-4-7-7-4 18-7Z"/><path d="m10 14 11-11"/></svg></button>
          <input id="sd-chat-input" type="text" inputmode="text" enterkeyhint="send" maxlength="160" placeholder="اكتب رسالة…" autocomplete="off" autocapitalize="sentences" spellcheck="true">
        </form>
      </div>`;
    document.body.appendChild(root);

    launcher = document.createElement('button');
    launcher.id = 'sd-chat-launcher';
    launcher.type = 'button';
    launcher.setAttribute('aria-label', 'فتح محادثة المباراة');
    launcher.innerHTML = `<span aria-hidden="true">💬</span><span id="sd-chat-unread" hidden></span>`;
    document.body.appendChild(launcher);

    list = root.querySelector('#sd-chat-messages');
    form = root.querySelector('#sd-chat-form');
    input = root.querySelector('#sd-chat-input');
    errorBox = root.querySelector('#sd-chat-error');
    closeBtn = root.querySelector('#sd-chat-close');
    backdrop = root.querySelector('#sd-chat-backdrop');
    unreadBadge = launcher.querySelector('#sd-chat-unread');
    input.maxLength = Number(window.__SAMIDEV_CLIENT_CONFIG?.chatMaxChars || 160);

    form.addEventListener('submit', e => { e.preventDefault(); e.stopPropagation(); sendCurrent(); });
    for (const type of ['keydown','keyup','keypress','click','pointerdown','touchstart']) {
      input.addEventListener(type, e => e.stopPropagation());
    }
    input.addEventListener('focus', () => { root.classList.add('focused'); updateViewport(); render(); });
    input.addEventListener('blur', () => { root.classList.remove('focused'); setTimeout(updateViewport, 70); });
    launcher.addEventListener('click', e => { e.preventDefault(); e.stopPropagation(); openMobileChat({focus:true}); });
    closeBtn.addEventListener('click', e => { e.preventDefault(); e.stopPropagation(); closeMobileChat(); });
    backdrop.addEventListener('click', e => { e.preventDefault(); e.stopPropagation(); closeMobileChat(); });
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && mobileOpen) closeMobileChat();
    });

    const n = net();
    n?.on?.('assignment', () => { showForRoom(true); setHistory(n.state.chatHistory || []); });
    n?.on?.('room_state', render);
    n?.on?.('start', render);
    n?.on?.('chat_history', e => setHistory(e?.messages || []));
    n?.on?.('chat_message', addMessage);
    n?.on?.('left_room', () => showForRoom(false));
    n?.on?.('error', e => {
      if (String(e?.code || '').startsWith('CHAT_')) showError(e?.message || 'تعذر إرسال الرسالة');
    });
    if (n?.state?.roomId) { showForRoom(true); setHistory(n.state.chatHistory || []); }

    window.visualViewport?.addEventListener('resize', updateViewport, {passive:true});
    window.visualViewport?.addEventListener('scroll', updateViewport, {passive:true});
    window.addEventListener('resize', syncLayout, {passive:true});
    mobileQuery.addEventListener?.('change', () => { syncLayout(); notifyGameResize(); });
    updateViewport();
  }

  window.SamiDevChatUI = { showForRoom, addMessage, setHistory, openMobileChat, closeMobileChat };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build, {once:true});
  else build();
})();
