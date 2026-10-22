(() => {
  'use strict';

  const $ = (sel, root=document) => root.querySelector(sel);
  let root = null;
  let panel = null;
  let infoModal = null;
  let confirmModal = null;
  let visible = false;
  let exiting = false;

  const GAME_MODE = ['Classic', 'Pool', 'Freestyle /120', 'Freestyle /160', 'Freestyle /210'];

  function net() { return window.SamiDevNetwork; }
  function gameUi() { return window.SamiDevGameUI; }
  function platform() { return window.SamiDevPlatform; }

  function esc(v) {
    return String(v ?? '').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  }

  function settingsRows(s={}) {
    if(s.gameId==='crazy8') return {players:window.SamiDevGames.cardSeats[Number(s.seats)]||'4 لاعبين',live:Number(s.live)===1?'مباشر':'تناوب الأدوار',mode:window.SamiDevGames.cardSpecial[Number(s.special)]||'أساسية',br:'عشوائي'};
    const players = Number(s.players) === 1 ? '2 ضد 2 — 4 لاعبين' : 'لاعبان';
    const live = Number(s.live) === 0 ? 'تناوب الأدوار' : 'مباشر';
    const mode = GAME_MODE[Number(s.gamemode)] || 'Classic';
    const br = Number(s.break) === 1 ? 'Player 2' : 'Player 1';
    return {players, live, mode, br};
  }

  function statusText(st) {
    if (st.begun) return 'المباراة جارية';
    if (st.started) return 'بانتظار جاهزية اللاعبين';
    return 'بانتظار اللاعبين';
  }

  function connectedCount(st) { return (st.roster || []).filter(x => x && x.connected).length; }

  function renderInfo() {
    const st = net()?.state || {};
    const sr = settingsRows(st.settings || {});
    const roster = (st.roster || []).map(p => p && p.name ? `
      <div class="sd-room-player ${p.seat === st.seat ? 'me' : ''}">
        <span>Player ${Number(p.seat)+1}${p.seat === st.seat ? ' — أنت' : ''}</span>
        <strong>${esc(p.name)}</strong>
        <em>${p.connected ? 'متصل' : 'غير متصل'}</em>
      </div>` : '').join('');
    const content = $('#sd-room-info-content');
    if (!content) return;
    content.innerHTML = `
      <div class="sd-room-code-row"><span>كود الغرفة</span><b dir="ltr">${esc(st.roomId || '------')}</b><button type="button" id="sd-copy-room">نسخ</button></div>
      <div class="sd-room-grid">
        <div><span>الحالة</span><b>${statusText(st)}</b></div>
        <div><span>المتصلون</span><b>${connectedCount(st)}/${Number(st.capacity || 0)}</b></div>
        <div><span>النمط</span><b>${esc(sr.mode)}</b></div>
        <div><span>نوع المباراة</span><b>${esc(sr.live)}</b></div>
        <div><span>اللاعبون</span><b>${esc(sr.players)}</b></div>
        <div><span>Break</span><b>${esc(sr.br)}</b></div>
        ${(st.settings?.gameId==='pool')?`<div><span>الطاولة</span><b>${Number(st.settings.largeTable)===1?'الطاولة الكبيرة':'الأصلية'}</b></div>`:''}
      </div>
      <div class="sd-room-roster">${roster}</div>`;
    $('#sd-copy-room')?.addEventListener('click', copyRoomCode);
    // Table management belongs in the existing information menu, not over the game.
    if(!window.SamiDevMobile?.postMessage&&!st.begun&&!st.spectator&&Number.isInteger(st.seat)&&st.ownerSeat===st.seat){
      const actions=document.createElement('div');actions.className='sd-actions';
      const add=(text,action,targetSeat=-1)=>{
        const button=document.createElement('button');button.type='button';button.textContent=text;button.dataset.tableAction=action;
        button.onclick=()=>{if(confirm(action==='close'?'إغلاق الطاولة وإعادة اللاعبين إلى المساحة؟':text+' قبل بدء اللعب؟')&&!net()?.send({type:'manage_table',action,targetSeat}))notify('انقطع الاتصال؛ أعد المحاولة بعد عودته');};
        actions.append(button);
      };
      add('إغلاق الطاولة','close');
      for(const player of (st.roster||[]).filter(p=>p&&p.seat!==st.seat&&p.name))add('إخراج '+player.name,'kick',player.seat);
      content.append(actions);
    }
  }

  async function copyRoomCode() {
    const code = net()?.state?.roomId;
    if (!code) return;
    try { await navigator.clipboard.writeText(code); }
    catch (_) {
      const input = document.createElement('textarea'); input.value = code; document.body.appendChild(input); input.select();
      try { document.execCommand('copy'); } catch (_) {} input.remove();
    }
    platform()?.haptic?.('success');
    const btn = $('#sd-copy-room');
    if (btn) { const old=btn.textContent; btn.textContent='تم النسخ'; setTimeout(()=>btn.textContent=old,1200); }
  }

  function notify(message) {
    const text = String(message || 'تعذر تنفيذ العملية');
    try {
      window.alert(text);
    } catch (_) {}
  }

  function updateInviteAvailability() {
    const st = net()?.state || {};
    const btn = $('#sd-invite');
    if (!btn) return;
    const disabled = !st.roomId || !!st.started;
    btn.disabled = disabled;
    btn.title = disabled ? 'الدعوة متاحة قبل اكتمال المقاعد' : '';
  }

  async function inviteFriend() {
    setMenu(false);
    const st = net()?.state || {};
    if (!st.roomId) return notify('لا توجد مباراة نشطة');
    if (st.started) return notify('اكتملت مقاعد المباراة بالفعل');
    const me = (st.roster || []).find(p => p && Number(p.seat) === Number(st.seat));
    try {
      const invite = await net().createInvite();
      const result = await platform()?.shareInvite?.({
        inviteToken: invite.inviteToken,
        inviterName: me?.name || 'صديقك',
        settings: st.settings || {},
      });
      if (result?.copied) notify('تم نسخ رابط الدعوة');
      platform()?.haptic?.('success');
    } catch (e) {
      console.warn('[SamiDev Room UI] invite failed', e);
      notify(e?.message || 'تعذر إنشاء الدعوة');
    }
  }

  function updateSoundLabel() {
    const muted = !!gameUi()?.isMuted?.();
    const label = $('#sd-sound-label');
    const icon = $('#sd-sound-icon');
    if (label) label.textContent = muted ? 'تشغيل الصوت' : 'كتم الصوت';
    if (icon) icon.textContent = muted ? '🔇' : '🔊';
  }

  function setMenu(open) {
    visible = !!open;
    root?.classList.toggle('open', visible);
    panel?.setAttribute('aria-hidden', visible ? 'false' : 'true');
    if (visible) { const help=$('#sd-help');if(help)help.hidden=!gameUi()?.canHelp?.();updateSoundLabel();const control=$('#sd-control');if(control){control.hidden=!window.SamiDevPoolControls?.available;$('#sd-control-label').textContent=window.SamiDevPoolControls?.mode==='hold'?'التحكم: الماوس والكلك اليمين':'التحكم: شريط القوة';} platform()?.haptic?.(); }
  }

  function openInfo() { setMenu(false); renderInfo(); infoModal?.classList.add('open'); platform()?.haptic?.(); }
  function closeInfo() { infoModal?.classList.remove('open'); }
  function openConfirm() { if(gameUi()?.isGameOver?.() || net()?.state?.finished) return confirmExit(); setMenu(false); confirmModal?.classList.add('open'); platform()?.haptic?.('warning'); }
  function closeConfirm() { confirmModal?.classList.remove('open'); }

  function openHelp() {
    setMenu(false);
    if (!gameUi()?.openHelp?.()) console.warn('[SamiDev Room UI] Help handler is not ready yet');
  }

  function toggleSound() {
    if (gameUi()?.toggleSound?.()) setTimeout(updateSoundLabel, 0);
    platform()?.haptic?.();
  }

  function currentCommunityId() {
    try{
      const fromNet=String(net()?.state?.communityId||'');if(fromNet)return fromNet;
      const q=new URLSearchParams(window.__SAMIDEV_QUERY ?? location.search);
      return q.get('community')||sessionStorage.getItem('samidev_return_community')||'';
    }catch(_){return '';}
  }
  function platformReturnUrl() {
    const cid=currentCommunityId();
    return cid?`/platform/?community=${encodeURIComponent(cid)}`:'/platform/';
  }

  function resetWebUrl() {
    if (window.__SAMIDEV_QUERY !== undefined) return;
    try {
      const u = new URL(location.href);
      for (const key of ['online','play','action','room','token','ticket']) u.searchParams.delete(key);
      history.replaceState(null, '', u);
    } catch (_) {}
  }

  async function confirmExit() {
    if (exiting) return;
    exiting = true;
    const btn = $('#sd-exit-confirm');
    if (btn) { btn.disabled = true; btn.textContent = 'جارٍ إنهاء المباراة…'; }

    const st = net()?.state || {};
    // Once authoritative play has begun, exiting is a resignation first. This makes
    // the opponent receive the native game-over/win event instead of merely seeing
    // this socket become disconnected.
    if (st.begun && !st.spectator && !gameUi()?.isGameOver?.()) {
      let resigned = null;
      try { resigned = await gameUi()?.resignMatch?.(5000); }
      catch (e) { resigned = {ok:false, error:e}; }
      if (!resigned?.ok) {
        console.warn('[SamiDev Room UI] resignation failed; room kept alive', resigned);
        exiting = false;
        if (btn) { btn.disabled = false; btn.textContent = 'إنهاء وخروج'; }
        notify('تعذر تسجيل الاستسلام لدى السيرفر. حاول مرة أخرى.');
        return;
      }
    }

    try {
      const result = await net()?.leaveRoom?.({closeSocket:true});
      if (result && !result.ok) console.warn('[SamiDev Room UI] leave_room acknowledgement', result);
    } catch (e) { console.warn('[SamiDev Room UI] leave failed', e); }
    try { sessionStorage.removeItem('samidev_reconnect'); } catch (_) {}
    resetWebUrl();
    platform()?.haptic?.('success');
    if(window.__SAMIDEV_APP_HOST)await window.__SAMIDEV_APP_HOST.returnToPlatform();else location.href = platformReturnUrl();
  }

  function returnToCommunity() {
    setMenu(false); closeInfo(); closeConfirm();
    if(window.SamiDevMobile?.postMessage){
      window.SamiDevMobile.postMessage(JSON.stringify({type:'room_background'}));
      return;
    }
    openConfirm();
  }

  function handleBack() {
    if (confirmModal?.classList.contains('open')) return closeConfirm();
    if (infoModal?.classList.contains('open')) return closeInfo();
    if (visible) return setMenu(false);
    setMenu(true);
  }

  function showForRoom(show) {
    root?.classList.toggle('room-active', !!show);
    // Browser mode: the in-game menu owns its own close/back controls.
  }

  function build() {
    if (root) return;
    const style = document.createElement('style');
    style.textContent = `
      :root{--sd-ui-bg:#111923;--sd-ui-text:#fff;--sd-ui-hint:rgba(255,255,255,.62);--sd-ui-button:#2481cc;--sd-ui-button-text:#fff;--sd-ui-secondary-bg:#18222d}
      #sd-room-ui{display:none;position:fixed;inset:0;z-index:16000;pointer-events:none;font-family:system-ui,-apple-system,"Segoe UI",Arial,sans-serif;color:var(--sd-ui-text)}
      #sd-room-ui.room-active{display:block}
      #sd-room-menu-button{pointer-events:auto;position:absolute;top:calc(env(safe-area-inset-top,0px) + 10px);right:calc(env(safe-area-inset-right,0px) + 10px);width:44px;height:44px;border:1px solid rgba(255,255,255,.12);border-radius:14px;background:rgba(7,12,18,.72);color:#fff;font-size:25px;line-height:1;backdrop-filter:blur(10px);box-shadow:0 7px 22px rgba(0,0,0,.3);cursor:pointer}
      #sd-room-ui.open .sd-menu-backdrop{display:block}.sd-menu-backdrop{display:none;pointer-events:auto;position:absolute;inset:0;background:rgba(0,0,0,.18)}
      #sd-room-menu{pointer-events:auto;position:absolute;top:calc(env(safe-area-inset-top,0px) + 62px);right:calc(env(safe-area-inset-right,0px) + 10px);width:min(290px,calc(100vw - 20px));padding:8px;background:rgba(13,20,28,.97);border:1px solid rgba(255,255,255,.12);border-radius:18px;box-shadow:0 20px 60px rgba(0,0,0,.45);transform:translateY(-8px) scale(.98);opacity:0;visibility:hidden;transition:.14s ease;direction:rtl}
      #sd-room-ui.open #sd-room-menu{transform:none;opacity:1;visibility:visible}
      .sd-menu-item{width:100%;display:flex;align-items:center;gap:12px;border:0;background:transparent;color:#fff;text-align:right;padding:12px;border-radius:12px;font-size:15px;cursor:pointer}.sd-menu-item:hover{background:rgba(255,255,255,.07)}.sd-menu-item:disabled{opacity:.42;cursor:not-allowed;background:transparent}.sd-menu-item.danger{color:#ff9d9d}.sd-menu-item .ico{width:24px;text-align:center;font-size:18px}
      .sd-modal{display:none;pointer-events:auto;position:absolute;inset:0;background:rgba(0,0,0,.58);align-items:center;justify-content:center;padding:calc(env(safe-area-inset-top,0px) + 16px) 16px calc(env(safe-area-inset-bottom,0px) + 16px)}.sd-modal.open{display:flex}
      .sd-card{width:min(520px,100%);max-height:86vh;overflow:auto;background:var(--sd-ui-secondary-bg,#18222d);border:1px solid rgba(255,255,255,.12);border-radius:22px;padding:18px;box-shadow:0 24px 90px rgba(0,0,0,.5);direction:rtl}.sd-card h2{margin:0 0 16px;font-size:21px}.sd-close{float:left;border:0;background:rgba(255,255,255,.08);color:#fff;width:34px;height:34px;border-radius:11px;font-size:20px;cursor:pointer}
      .sd-room-code-row{display:grid;grid-template-columns:1fr auto auto;gap:9px;align-items:center;background:rgba(255,255,255,.06);padding:11px;border-radius:14px}.sd-room-code-row span{color:var(--sd-ui-hint)}.sd-room-code-row b{font-size:19px;letter-spacing:2px}.sd-room-code-row button,.sd-actions button{border:0;border-radius:11px;padding:9px 12px;background:var(--sd-ui-button);color:var(--sd-ui-button-text);font-weight:700;cursor:pointer}
      .sd-room-grid{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin:12px 0}.sd-room-grid>div{background:rgba(255,255,255,.045);padding:10px;border-radius:12px}.sd-room-grid span{display:block;color:var(--sd-ui-hint);font-size:12px;margin-bottom:4px}.sd-room-grid b{font-size:14px}
      .sd-room-roster{display:grid;gap:7px}.sd-room-player{display:grid;grid-template-columns:1fr auto auto;gap:8px;align-items:center;padding:9px 10px;border-radius:12px;background:rgba(255,255,255,.045)}.sd-room-player.me{outline:1px solid rgba(80,170,255,.55)}.sd-room-player em{font-size:11px;color:var(--sd-ui-hint);font-style:normal}
      .sd-confirm-text{color:var(--sd-ui-hint);line-height:1.7}.sd-actions{display:grid;grid-template-columns:1fr 1fr;gap:9px;margin-top:17px}.sd-actions .cancel{background:rgba(255,255,255,.09);color:#fff}.sd-actions .danger{background:#b52d35;color:#fff}.sd-actions button:disabled{opacity:.6}
      #sd-room-menu-button{left:10px;right:auto;border-radius:50%;box-shadow:none}
      #sd-room-back-button{pointer-events:auto;position:absolute;top:calc(env(safe-area-inset-top,0px) + 10px);right:10px;width:44px;height:44px;border-radius:50%;border:1px solid rgba(255,255,255,.12);background:rgba(7,12,18,.72);color:white;font-size:32px;cursor:pointer}
      #sd-room-menu{left:10px;right:auto}
      html[data-theme="light"]{--sd-ui-text:#18212a;--sd-ui-hint:#66747f;--sd-ui-secondary-bg:#eef1f4}
      .sd-menu-item[hidden]{display:none}
      html[data-theme="light"] #sd-room-menu,html[data-theme="light"] .sd-card{background:#fafafa;color:#18212a;border-color:#dce1e5}
      html[data-theme="light"] .sd-menu-item{color:#18212a}
      @media(max-width:420px){.sd-room-grid{grid-template-columns:1fr}.sd-room-player{grid-template-columns:1fr auto}.sd-room-player em{grid-column:1/-1}}
    `;
    document.head.appendChild(style);

    root = document.createElement('div');
    root.id = 'sd-room-ui';
    root.innerHTML = `
      <div class="sd-menu-backdrop"></div>
      <button id="sd-room-menu-button" type="button" aria-label="قائمة المباراة"><svg viewBox="0 0 24 24" aria-hidden="true" fill="currentColor"><circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/></svg></button><button id="sd-room-back-button" type="button" aria-label="العودة إلى المساحة"><svg viewBox="0 0 24 24" aria-hidden="true" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m9 5 7 7-7 7"/></svg></button>
      <div id="sd-room-menu" aria-hidden="true">
        <button class="sd-menu-item" id="sd-items" type="button"><span class="ico"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" aria-hidden="true"><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9M8 5.3l8 4.5"/></svg></span><span>مقتنياتي</span></button>
        <button class="sd-menu-item" id="sd-info" type="button"><span class="ico">ⓘ</span><span>معلومات المباراة</span></button>
        <button class="sd-menu-item" id="sd-invite" type="button"><span class="ico">✉️</span><span>دعوة صديق</span></button>
        <button class="sd-menu-item" id="sd-sound" type="button"><span class="ico" id="sd-sound-icon">🔊</span><span id="sd-sound-label">كتم الصوت</span></button>
        <button class="sd-menu-item" id="sd-control" type="button" hidden><span class="ico">↕</span><span id="sd-control-label">طريقة التحكم</span></button>
        <button class="sd-menu-item" id="sd-help" type="button"><span class="ico">❓</span><span>المساعدة</span></button>
        <button class="sd-menu-item danger" id="sd-exit" type="button"><span class="ico">🚪</span><span>خروج</span></button>
      </div>
      <div class="sd-modal" id="sd-room-info-modal"><div class="sd-card"><button class="sd-close" type="button" aria-label="إغلاق">×</button><h2>معلومات المباراة</h2><div id="sd-room-info-content"></div></div></div>
      <div class="sd-modal" id="sd-exit-modal"><div class="sd-card"><button class="sd-close" type="button" aria-label="إغلاق">×</button><h2>الخروج من المباراة</h2><div class="sd-confirm-text">إذا بدأت المباراة فسيتم تسجيل استسلامك أولًا لدى سيرفر اللعبة، ثم الخروج من الغرفة. بذلك تصل نتيجة الفوز للطرف الآخر بشكل صحيح.</div><div class="sd-actions"><button class="cancel" id="sd-exit-cancel" type="button">إلغاء</button><button class="danger" id="sd-exit-confirm" type="button">إنهاء وخروج</button></div></div></div>`;
    document.body.appendChild(root);
    panel = $('#sd-room-menu'); infoModal = $('#sd-room-info-modal'); confirmModal = $('#sd-exit-modal');

    $('#sd-room-back-button').addEventListener('click',returnToCommunity);
    $('#sd-items').addEventListener('click',()=>{setMenu(false);window.SamiDevInventory?.open();});
    $('#sd-room-menu-button').addEventListener('click', () => setMenu(!visible));
    $('.sd-menu-backdrop').addEventListener('click', () => setMenu(false));
    $('#sd-info').addEventListener('click', openInfo);
    $('#sd-invite').addEventListener('click', inviteFriend);
    $('#sd-sound').addEventListener('click', toggleSound);
    $('#sd-help').addEventListener('click', openHelp);
    $('#sd-control').addEventListener('click',()=>{const c=window.SamiDevPoolControls;if(!c)return;c.setMode(c.mode==='hold'?'meter':'hold');setMenu(true);let hint=$('#sd-control-hint');if(!hint){hint=document.createElement('p');hint.id='sd-control-hint';hint.style.cssText='font-size:12px;line-height:1.7;padding:0 12px;color:#9cbbc6';panel.append(hint);}hint.textContent=c.mode==='hold'?'حرّك الماوس للتصويب، وثبّت الكلك اليمين على الطاولة لشحن القوة ثم أفلته للضرب.':'اسحب شريط القوة ثم أفلته للضرب.';});
    $('#sd-exit').addEventListener('click', openConfirm);
    infoModal.querySelector('.sd-close').addEventListener('click', closeInfo);
    confirmModal.querySelector('.sd-close').addEventListener('click', closeConfirm);
    $('#sd-exit-cancel').addEventListener('click', closeConfirm);
    $('#sd-exit-confirm').addEventListener('click', confirmExit);
    infoModal.addEventListener('click', e => { if (e.target === infoModal) closeInfo(); });
    confirmModal.addEventListener('click', e => { if (e.target === confirmModal) closeConfirm(); });

    const n = net();
    n?.on?.('assignment', () => { showForRoom(true); renderInfo(); updateInviteAvailability(); });
    n?.on?.('room_state', () => { updateInviteAvailability(); if (infoModal.classList.contains('open')) renderInfo(); });
    n?.on?.('start', () => { updateInviteAvailability(); if (infoModal.classList.contains('open')) renderInfo(); });
    n?.on?.('begin_match', () => { if (infoModal.classList.contains('open')) renderInfo(); });
    n?.on?.('left_room', () => showForRoom(false));
    if (n?.state?.roomId || new URLSearchParams(window.__SAMIDEV_QUERY ?? location.search).get('online')==='1') showForRoom(true);
    updateInviteAvailability();
  }

  window.SamiDevRoomUI = {openExit: openConfirm, exitMatch: confirmExit, returnToCommunity};

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', build, {once:true});
  else build();
})();
