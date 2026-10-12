(() => {
  'use strict';

  const canvas = document.getElementById('game');
  const net = () => window.SamiDevNetwork;
  const gameUi = () => window.SamiDevGameUI;
  const $ = (s, root=document) => root.querySelector(s);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

  let layer, card, ratingLayer, toastBox;
  let activeProfile = null;
  let profileFull = false;
  let lastGameOver = false;
  let ratingQueue = [];
  let ratingBusy = false;
  let returnTimer = null;
  let maxReturnTimer = null;
  let returningToCommunity = false;

  const DEFAULT_AVATAR_URL = '/images/default-avatar.png';
  function wireSafeAvatarImages(root=document){
    root.querySelectorAll?.('img[data-sd-avatar]').forEach(img=>{
      if(img.dataset.avatarWired==='1')return;
      img.dataset.avatarWired='1';
      img.addEventListener('error',()=>{if(!img.src.endsWith(DEFAULT_AVATAR_URL))img.src=DEFAULT_AVATAR_URL;});
    });
  }

  function icon(name, extra='') {
    return `<span class="sdpp-icon sdpp-icon-${name} ${extra}" aria-hidden="true"></span>`;
  }

  function initials(name) {
    const p=String(name||'P').trim().split(/\s+/).filter(Boolean);
    return (p.slice(0,2).map(x=>x[0]||'').join('')||'P').toUpperCase();
  }

  function daysText(days) {
    const n=Math.max(0,Math.floor(Number(days)||0));
    if(n>=3&&n<=10)return `${n} أيام`;
    return `${n} يوم`;
  }

  function numberText(value) {
    return Math.max(0,Math.floor(Number(value)||0)).toLocaleString('en-US');
  }

  function currentCommunityId() {
    try{
      const fromNet=String(net()?.state?.communityId||'');if(fromNet)return fromNet;
      const q=new URLSearchParams(window.__SAMIDEV_QUERY ?? location.search);
      return q.get('community')||sessionStorage.getItem('samidev_return_community')||'';
    }catch(_){return '';}
  }
  function communityReturnUrl() {
    const cid=currentCommunityId();
    return cid?`/platform/?community=${encodeURIComponent(cid)}`:'/platform/';
  }
  async function returnToCommunity() {
    if(returningToCommunity)return;
    const cid=currentCommunityId();if(!cid)return;
    returningToCommunity=true;
    clearTimeout(returnTimer);clearTimeout(maxReturnTimer);
    try{await net()?.leaveRoom?.({closeSocket:true});}catch(_){}
    try{sessionStorage.removeItem('samidev_reconnect');sessionStorage.setItem('samidev_return_community',cid);}catch(_){}
    location.replace(communityReturnUrl());
  }
  function scheduleCommunityReturn(delay=900) {
    if(!currentCommunityId()||returningToCommunity)return;
    clearTimeout(returnTimer);returnTimer=setTimeout(returnToCommunity,Math.max(100,Number(delay)||900));
  }

  function currentRoster() { return Array.isArray(net()?.state?.roster) ? net().state.roster : []; }
  function localSeat() { const n=Number(net()?.state?.seat); return Number.isInteger(n)?n:-1; }
  function capacity() { return Math.max(0,Number(net()?.state?.capacity)||currentRoster().length||0); }

  async function api(path, options={}) {
    const opts={credentials:'same-origin',...options};
    if(opts.body!==undefined) opts.headers={'Content-Type':'application/json',...(options.headers||{})};
    const response=await fetch(path,opts);
    let data={};
    try{data=await response.json();}catch(_){data={ok:false,message:`HTTP ${response.status}`};}
    if(!response.ok||data.ok===false)throw Object.assign(new Error(data.message||'فشل الطلب'),{status:response.status,code:data.error,data});
    return data;
  }

  function toast(message, error=false) {
    if(!toastBox)return;
    toastBox.textContent=String(message||'');
    toastBox.classList.toggle('error',!!error);
    toastBox.classList.add('show');
    clearTimeout(toast.timer);
    toast.timer=setTimeout(()=>toastBox?.classList.remove('show'),2600);
  }

  function canvasRect() {
    const r=canvas?.getBoundingClientRect?.();
    return r && r.width>0 && r.height>0 ? r : null;
  }

  function positionLayer() {
    const r=canvasRect();
    if(!r||!layer)return;
    Object.assign(layer.style,{left:"0",top:"0",width:"100%",height:"100dvh"});
    if(ratingLayer)Object.assign(ratingLayer.style,{left:`${r.left}px`,top:`${r.top}px`,width:`${r.width}px`,height:`${r.height}px`});
  }

  function relationButton(user) {
    if(user.relation==='self')return '<button class="sdpp-action friend" type="button" disabled>ملفك الشخصي</button>';
    if(user.relation==='friend')return `<button class="sdpp-action friend" type="button" disabled>${icon('friend')}<span>صديق</span></button>`;
    if(user.relation==='outgoing')return `<button class="sdpp-action friend" type="button" disabled>${icon('friend')}<span>تم إرسال الطلب</span></button>`;
    if(user.relation==='incoming')return `<button class="sdpp-action friend" type="button" data-action="friend">${icon('friend')}<span>قبول الصداقة</span></button>`;
    return `<button class="sdpp-action friend" type="button" data-action="friend">${icon('friend')}<span>إضافة صديق</span></button>`;
  }

  function starsMarkup(count = 5) {
    const n = Math.max(0, Math.min(5, Number(count ?? 5)));
    return Array.from({length:5}, (_, i) => `<span class="sdpp-icon sdpp-icon-star ${i < n ? 'active' : 'dim'}" aria-hidden="true"></span>`).join('');
  }

  function badgeMarkup(user) {
    const asset = user?.nameBadgeAsset || '/platform/assets/profile/raster/palm-swords.webp';
    const name = user?.nameBadgeName || 'سيفين ونخلة';
    return `<span class="sdpp-emblem-wrap"><img class="sdpp-emblem" src="${esc(asset)}" alt="${esc(name)}" title="${esc(name)}" loading="lazy"></span>`;
  }

  function showcaseMarkup(user){
    const best=(user.gameStatistics||[]).filter(row=>Number(row.played)>0).sort((a,b)=>Number(b.wins)-Number(a.wins))[0];
    const marks={pool:'pool',carrom:'carrom',tablesoccer:'football',crazy8:'cards'};
    const names={pool:'البلياردو',carrom:'الكيرم',tablesoccer:'كرة الطاولة',crazy8:'أونو'};
    const featured=best&&marks[best.gameId]?`<div class="sd-featured-rank"><img src="/room-sprites/${marks[best.gameId]}.png" alt=""><div><strong>${names[best.gameId]}</strong><small>${esc(best.rankName)} · المستوى ${numberText(best.level)}</small></div></div>`:'';
    return featured+'<button class="sd-open-full" data-action="full" type="button">الملف الكامل والمقتنيات والإحصاءات</button><section data-profile-details hidden></section>';
  }

  function renderProfile(user, player) {
    activeProfile={user,player};
    card.classList.add("profile-showcase");
    const img=`<img class="sdpp-avatar-img" data-sd-avatar src="${user.id?'/api/avatar/'+encodeURIComponent(user.id):DEFAULT_AVATAR_URL}" alt="">`;
    const remaining=Number.isFinite(Number(user.reputationDailyRemaining))?Math.max(0,Number(user.reputationDailyRemaining)):0;
    const repDisabled=user.relation==='self'||user.reputationGrantedToday||remaining<=0;
    card.innerHTML=`
      <button class="sdpp-close" type="button" aria-label="إغلاق">${icon('close')}</button>
      <div class="sdpp-cover"><span class="sdpp-cover-mark">S</span></div>
      <div class="sdpp-profile-body">
        <div class="sdpp-avatar">${img}</div>
        <div class="sdpp-name-row"><strong>${esc(user.displayName||player?.name||'لاعب')}</strong><div class="sdpp-stars" aria-label="${user.starsCount ?? 0} نجوم">${starsMarkup(user.starsCount ?? 0)}</div>${badgeMarkup(user)}</div>
        <div class="sdpp-handle">${esc(user.username ? "@"+user.username : "")}</div>
        <div class="sdpp-stats">
          <div><small>لاعب منذ</small><b>${icon('calendar')}${esc(daysText(user.accountAgeDays))}</b></div>
          <div><small>الفوز</small><b>${icon('trophy')}${esc(numberText(user.wins))}</b></div>
          <div><small>السمعة</small><b>${icon('fire')}${esc(numberText(user.reputation))}</b></div>
        </div>
        <div class="sdpp-actions">
          <button class="sdpp-action report" data-action="report" type="button" title="إبلاغ" ${user.relation==='self'?'disabled':''}>${icon('report')}<span>إبلاغ</span></button>
          ${relationButton(user)}
          <button class="sdpp-action reputation" data-action="reputation" type="button" ${repDisabled?'disabled':''}>${icon('fire')}<span>${user.reputationGrantedToday?'مُنحت اليوم':'منح سمعة'}</span><small>${remaining}/5 اليوم</small></button>
          <button class="sdpp-action collection" data-action="collection" type="button" aria-label="عرض المقتنيات"><span class="sdpp-icon sdpp-icon-collection" aria-hidden="true"></span></button>
        </div>
        ${showcaseMarkup(user)}
        <div id="sdpp-report-box" class="sdpp-report-box" hidden>
          <label for="sdpp-report-text">وصف المشكلة</label>
          <textarea id="sdpp-report-text" maxlength="500" rows="3" placeholder="اكتب باختصار ما حدث..."></textarea>
          <div><button type="button" data-action="report-cancel">إلغاء</button><button class="send" type="button" data-action="report-send">إرسال للإدارة</button></div>
        </div>
      </div>`;
    wireSafeAvatarImages(card);
    card.querySelector('.sdpp-close').onclick=()=>{if(profileFull)setProfileFull(false);else closeProfile();};
    card.querySelector('[data-action="full"]')?.addEventListener('click',()=>setProfileFull(true));
    card.querySelector('[data-action="collection"]')?.addEventListener("click",()=>{setProfileFull(true);card.querySelector(".sd-collection-section")?.scrollIntoView({block:"nearest"});});
    setProfileFull(profileFull);
    window.SamiDevProfileDetails?.render(card.querySelector('[data-profile-details]'),user,{own:user.relation==='self'});
    card.querySelector('[data-action="friend"]')?.addEventListener('click',()=>friendAction());
    card.querySelector('[data-action="reputation"]')?.addEventListener('click',()=>reputationAction());
    card.querySelector('[data-action="report"]')?.addEventListener('click',()=>{const b=$('#sdpp-report-box',card);if(b){b.hidden=false;$('#sdpp-report-text',card)?.focus();positionLayer();}});
    card.querySelector('[data-action="report-cancel"]')?.addEventListener('click',()=>{$('#sdpp-report-box',card).hidden=true;positionLayer();});
    card.querySelector('[data-action="report-send"]')?.addEventListener('click',()=>reportAction());
    layer.classList.add('open'); layer.setAttribute('aria-hidden','false');
  }

  function setProfileFull(full){
    profileFull=full;card.classList.toggle("sd-profile-expanded",full);
    const details=card.querySelector("[data-profile-details]");if(details)details.hidden=!full;
    const button=card.querySelector("[data-action=full]");if(button)button.hidden=full;
    const close=card.querySelector(".sdpp-close");if(close){close.textContent=full?"‹":"×";close.setAttribute("aria-label",full?"العودة إلى البطاقة المختصرة":"إغلاق");}
  }

  function renderGuestProfile(player) {
    activeProfile={user:null,player};
    card.classList.remove("sd-profile-expanded");
    card.innerHTML=`
      <button class="sdpp-close" type="button" aria-label="إغلاق">${icon('close')}</button>
      <div class="sdpp-cover"><span class="sdpp-cover-mark">S</span></div>
      <div class="sdpp-profile-body">
        <div class="sdpp-avatar"><img class="sdpp-avatar-img" data-sd-avatar src="${DEFAULT_AVATAR_URL}" alt=""></div>
        <div class="sdpp-name-row"><strong>${esc(player?.name||'Player')}</strong>${badgeMarkup(null)}</div>

        <div class="sdpp-divider"></div>
        <div class="sdpp-guest-note">هذا اللاعب داخل المباراة كضيف، لذلك لا توجد بيانات حساب مرتبطة بهذه الجلسة.</div>
        <div class="sdpp-stats">
          <div><small>لاعب منذ</small><b>${icon('calendar')}—</b></div>
          <div><small>الفوز</small><b>${icon('trophy')}—</b></div>
          <div><small>السمعة</small><b>${icon('fire')}—</b></div>
        </div>
        <div class="sdpp-actions sdpp-actions-guest">
          <button class="sdpp-action" type="button" disabled>${icon('friend')}<span>يلزم حساب مسجل</span></button>
        </div>
      </div>`;
    wireSafeAvatarImages(card);
    card.querySelector('.sdpp-close').onclick=closeProfile;
    layer.classList.add('open');layer.setAttribute('aria-hidden','false');
  }

  async function openProfile(player) {
    if(!player?.name)return;
    profileFull=false;
    positionLayer();
    if(!player.accountId){renderGuestProfile(player);return;}
    card.innerHTML='<div class="sdpp-loading">تحميل الملف...</div>';
    layer.classList.add('open'); layer.setAttribute('aria-hidden','false');
    try{
      const d=await api(`/api/public-profile/${encodeURIComponent(player.accountId)}`);
      renderProfile(d.user,player);
    }catch(e){card.innerHTML=`<button class="sdpp-close" type="button">${icon('close')}</button><div class="sdpp-loading error">${esc(e.message||'تعذر تحميل الملف')}</div>`;card.querySelector('.sdpp-close').onclick=closeProfile;}
  }

  function closeProfile() { layer?.classList.remove('open'); layer?.setAttribute('aria-hidden','true'); activeProfile=null; }

  async function friendAction() {
    const u=activeProfile?.user;if(!u)return;
    try{
      if(u.relation==='incoming'){
        await api('/api/friends/respond',{method:'POST',body:JSON.stringify({userId:u.id,accept:true})});
        u.relation='friend'; toast('تمت إضافة الصديق');
      }else{
        await api('/api/friends/request',{method:'POST',body:JSON.stringify({username:u.username})});
        u.relation='outgoing'; toast('تم إرسال طلب الصداقة');
      }
      renderProfile(u,activeProfile.player);
    }catch(e){toast(e.message||'تعذر تنفيذ طلب الصداقة',true);}
  }

  async function reputationAction() {
    const u=activeProfile?.user;if(!u)return;
    const button=card.querySelector('[data-action="reputation"]');if(button)button.disabled=true;
    try{
      const d=await api(`/api/users/${encodeURIComponent(u.id)}/reputation`,{method:'POST',body:JSON.stringify({source:'profile'})});
      u.reputation=d.reputation;u.reputationDailyRemaining=d.remaining;u.reputationGrantedToday=true;
      toast('تم منح السمعة'); renderProfile(u,activeProfile.player);
    }catch(e){if(button)button.disabled=false;toast(e.message||'تعذر منح السمعة',true);}
  }

  async function reportAction() {
    const u=activeProfile?.user;if(!u)return;
    const text=String($('#sdpp-report-text',card)?.value||'').trim();
    const send=card.querySelector('[data-action="report-send"]');if(send)send.disabled=true;
    try{
      await api(`/api/users/${encodeURIComponent(u.id)}/report`,{method:'POST',body:JSON.stringify({message:text,roomId:String(net()?.state?.roomId||'')})});
      toast('تم إرسال البلاغ للإدارة');
      const box=$('#sdpp-report-box',card);if(box)box.hidden=true;
    }catch(e){toast(e.message||'تعذر إرسال البلاغ',true);}
    finally{if(send)send.disabled=false;}
  }

  function opponentPlayers() {
    const me=localSeat(), cap=capacity(); if(me<0)return [];
    const gid=window.SamiDevGames?.current().id;
    const individual=gid==='crazy8' && Number(net()?.state?.settings?.seats)!==4;
    const team = seat => gid === 'tablesoccer' ? Math.floor(seat/2) : seat%2;
    return currentRoster().filter(p=>p&&p.accountId&&Number(p.seat)!==me&&(individual||cap<4||team(Number(p.seat))!==team(me)));
  }

  function alreadyRated(roomId,userId) {
    try{return sessionStorage.getItem(`samidev-rated:${roomId}:${userId}`)==='1';}catch(_){return false;}
  }
  function markRated(roomId,userId) {try{sessionStorage.setItem(`samidev-rated:${roomId}:${userId}`,'1');}catch(_){} }

  function startRatingFlow() {
    if(ratingBusy)return;
    const roomId=String(net()?.state?.roomId||'');if(!roomId)return;
    ratingQueue=opponentPlayers().filter(p=>!alreadyRated(roomId,p.accountId));
    if(!ratingQueue.length){scheduleCommunityReturn(1800);return;}
    ratingBusy=true;closeProfile();showNextRating();
  }

  async function showNextRating() {
    const roomId=String(net()?.state?.roomId||'');
    const player=ratingQueue.shift();
    if(!player){ratingLayer.classList.remove('open');ratingBusy=false;scheduleCommunityReturn(700);return;}
    let profile=null;
    try{profile=(await api(`/api/public-profile/${encodeURIComponent(player.accountId)}`)).user;}catch(_){profile={id:player.accountId,displayName:player.name,hasAvatar:true};}
    const avatar=`<img data-sd-avatar src="${player.accountId?'/api/avatar/'+encodeURIComponent(player.accountId):DEFAULT_AVATAR_URL}" alt="">`;
    ratingLayer.innerHTML=`<div class="sdpp-rating-card"><div class="sdpp-rating-avatar">${avatar}</div><strong>${esc(profile.displayName||player.name||'Player')}</strong><p>كيف كانت تجربتك مع هذا اللاعب؟</p><div class="sdpp-rating-actions"><button data-like="1" type="button">${icon('up')}<span>إعجاب</span></button><button data-like="0" type="button">${icon('down')}<span>عدم إعجاب</span></button></div><button class="sdpp-rating-skip" type="button">تخطي</button></div>`;
    wireSafeAvatarImages(ratingLayer);
    ratingLayer.classList.add('open');positionLayer();
    ratingLayer.querySelectorAll('[data-like]').forEach(b=>b.onclick=async()=>{
      if(b.disabled)return;ratingLayer.querySelectorAll('button').forEach(x=>x.disabled=true);
      try{
        await api(`/api/users/${encodeURIComponent(player.accountId)}/reputation`,{method:'POST',body:JSON.stringify({source:'game',roomId,liked:b.dataset.like==='1'})});
        markRated(roomId,player.accountId);toast(b.dataset.like==='1'?'تم إرسال الإعجاب وإضافة نقطة سمعة':'تم تسجيل عدم الإعجاب وخصم نقطة سمعة');
      }catch(e){toast(e.message||'تعذر حفظ التقييم',true);}
      ratingLayer.classList.remove('open');setTimeout(showNextRating,180);
    });
    ratingLayer.querySelector('.sdpp-rating-skip').onclick=()=>{ratingLayer.classList.remove('open');setTimeout(showNextRating,120);};
  }

  function pollGameOver() {
    const over=!!gameUi()?.isGameOver?.();
    if(over&&!lastGameOver){
      setTimeout(startRatingFlow,850);
      clearTimeout(maxReturnTimer);
      if(currentCommunityId())maxReturnTimer=setTimeout(returnToCommunity,15000);
    }
    lastGameOver=over;
  }

  function resetRoomState() { lastGameOver=false;ratingQueue=[];ratingBusy=false;returningToCommunity=false;clearTimeout(returnTimer);clearTimeout(maxReturnTimer);ratingLayer?.classList.remove('open');closeProfile(); }

  function build() {
    if(!canvas||layer)return;
    const identity=document.createElement("link");identity.rel="stylesheet";identity.href="/platform/profile-identity.css";document.head.appendChild(identity);
    const style=document.createElement('style');
    style.textContent=`
      .sdpp-icon{display:inline-block;width:22px;height:22px;flex:0 0 22px;background:url('/player-profile-sheet.svg') no-repeat;background-size:1100% 100%;vertical-align:middle}.sdpp-icon-star,.sdpp-icon-trophy,.sdpp-icon-fire,.sdpp-icon-emblem{background-repeat:no-repeat;background-position:center;background-size:contain}.sdpp-icon-star{background-image:url('/platform/assets/profile/raster/star.webp')}.sdpp-icon-trophy{background-image:url('/platform/assets/profile/raster/trophy.webp')}.sdpp-icon-calendar{background-position:20% 0}.sdpp-icon-fire{background-image:url('/platform/assets/profile/raster/reputation-flame.webp')}.sdpp-icon-emblem{background-image:url('/platform/assets/profile/raster/palm-swords.webp')}.sdpp-icon-friend{background-position:50% 0}.sdpp-icon-report{background-position:60% 0}.sdpp-icon-up{background-position:70% 0}.sdpp-icon-down{background-position:80% 0}.sdpp-icon-close{background-position:90% 0}.sdpp-icon-user{background-position:100% 0}
      #sdpp-layer,#sdpp-rating-layer{display:none;position:fixed;z-index:23000;pointer-events:none;font-family:system-ui,-apple-system,"Segoe UI",Arial,sans-serif;color:#f5f3ec}#sdpp-layer.open,#sdpp-rating-layer.open{display:flex;pointer-events:auto;align-items:flex-start;justify-content:center;background:rgba(0,0,0,.42);backdrop-filter:blur(3px);padding:clamp(14px,3vh,28px);box-sizing:border-box;overflow:auto}
      #sdpp-card{width:min(390px,100%);background:#0b0f11;border:1px solid rgba(255,255,255,.09);border-radius:22px;overflow:hidden;box-shadow:0 26px 90px rgba(0,0,0,.62);direction:rtl;position:relative;margin:auto}.sdpp-close{position:absolute;z-index:3;left:12px;top:12px;width:38px;height:38px;border-radius:50%;border:1px solid rgba(255,255,255,.12);background:rgba(8,10,12,.72);display:grid;place-items:center;cursor:pointer}.sdpp-close .sdpp-icon{width:21px;height:21px}.sdpp-cover{height:126px;position:relative;overflow:hidden;background:radial-gradient(circle at 25% 35%,rgba(117,35,28,.42),transparent 32%),linear-gradient(125deg,#262728 0 22%,#343536 22% 38%,#1a1b1c 38% 60%,#292a2b 60% 77%,#151617 77%)}.sdpp-cover:after{content:"";position:absolute;inset:0;background:linear-gradient(135deg,transparent 0 35%,rgba(255,255,255,.035) 35% 48%,transparent 48%)}.sdpp-cover-mark{position:absolute;right:22px;top:14px;font:900 82px/1 Arial;color:rgba(195,64,43,.22)}
      .sdpp-profile-body{padding:0 22px 20px;text-align:center}.sdpp-avatar{width:132px;height:132px;border-radius:50%;margin:-66px auto 0;position:relative;z-index:2;display:grid;place-items:center;overflow:hidden;background:#20282b;border:3px solid #d7a743;box-shadow:0 0 0 5px #0b0f11,0 13px 32px rgba(0,0,0,.5);font-size:38px;font-weight:850}.sdpp-avatar-img{width:100%;height:100%;object-fit:cover}.sdpp-avatar-fallback{letter-spacing:.5px}.sdpp-name-row{margin-top:13px;display:flex;align-items:center;justify-content:center;gap:7px;direction:rtl}.sdpp-name-row strong{font-size:23px;max-width:260px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.sdpp-emblem-wrap{display:inline-flex;align-items:center;justify-content:center;width:27px;height:27px;flex:0 0 27px;vertical-align:middle}.sdpp-emblem{width:100%;height:100%;object-fit:contain;display:block;filter:drop-shadow(0 2px 4px rgba(215,167,67,.25))}.sdpp-stars{display:flex;direction:ltr;justify-content:center;gap:1px;margin-top:5px}.sdpp-stars .sdpp-icon{width:20px;height:20px}.sdpp-stars .sdpp-icon-star.dim{opacity:.20;filter:grayscale(1)}.sdpp-stars .sdpp-icon-star.active{opacity:1;filter:drop-shadow(0 1px 3px rgba(255,215,0,.3))}.sdpp-divider{width:92px;height:2px;background:#ae2930;margin:10px auto 14px;border-radius:4px}
      .sdpp-extra{margin-top:18px;text-align:right;border-top:1px solid #304044;padding-top:12px}.sdpp-extra h3{font-size:15px;margin:15px 0 10px;color:#f0dfb9}.sdpp-items{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;max-height:112px;overflow:hidden}.sdpp-items.expanded{max-height:none}.sdpp-item{min-width:0;border:1px solid #304044;border-radius:12px;background:#132124;padding:7px;text-align:center;font-size:11px}.sdpp-item-preview{height:62px;display:grid;place-items:center}.sdpp-item-preview img{width:100%;height:100%;object-fit:contain}.sdpp-item span{display:block;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.sdpp-show-all{display:block;margin:10px auto;background:transparent;border:1px solid #6e6a4c;border-radius:10px;padding:8px 15px;color:#e7d29c}.sdpp-game-list{display:grid;gap:7px}.sdpp-game{display:grid;grid-template-columns:1fr auto auto;gap:12px;align-items:center;background:#132124;border:1px solid #304044;border-radius:10px;padding:12px 10px;font-size:12px}.sdpp-game span,.sdpp-empty{color:#9aacab;font-size:11px}
      .sdpp-stats{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid rgba(255,255,255,.08);border-bottom:1px solid rgba(255,255,255,.08);padding:12px 0;margin-top:5px}.sdpp-stats>div{display:grid;gap:5px;padding:0 8px;min-width:0}.sdpp-stats>div:not(:last-child){border-left:1px solid rgba(255,255,255,.10)}.sdpp-stats small{color:#8f9a9f;font-size:10px}.sdpp-stats b{display:flex;align-items:center;justify-content:center;gap:4px;font-size:16px;white-space:nowrap}.sdpp-stats .sdpp-icon{width:21px;height:21px;flex-basis:21px}
      .sdpp-actions{display:grid;grid-template-columns:62px 1fr 92px;gap:9px;margin-top:17px;direction:ltr}.sdpp-action{min-height:48px;border:1px solid rgba(255,255,255,.10);border-radius:12px;background:#17212a;color:#fff;display:flex;align-items:center;justify-content:center;gap:7px;font-weight:750;cursor:pointer;padding:8px 10px;font-family:inherit}.sdpp-action.friend{background:#1d6cc5}.sdpp-action.report{background:#101519;border-color:rgba(255,255,255,.15)}.sdpp-action.reputation{background:#b86419;display:grid;grid-template-columns:24px 1fr;column-gap:5px;direction:rtl}.sdpp-action.reputation small{grid-column:1/-1;font-size:8px;color:rgba(255,255,255,.72);margin-top:-4px}.sdpp-action:disabled{opacity:.48;cursor:default}.sdpp-action .sdpp-icon{width:22px;height:22px}.sdpp-action.report span{display:none}
      .sdpp-more-wrap{margin-top:14px;display:flex;justify-content:center}.sdpp-more-btn{display:inline-flex;align-items:center;justify-content:center;gap:7px;background:rgba(255,255,255,.05);border:1px solid rgba(215,167,67,.32);border-radius:18px;padding:7px 18px;color:#e5cb93;font-size:12px;font-weight:700;cursor:pointer;transition:all .2s ease;font-family:inherit;outline:none}.sdpp-more-btn:hover{background:rgba(215,167,67,.14);border-color:rgba(215,167,67,.65);color:#fff;transform:translateY(-1px)}.sdpp-more-btn.expanded{background:rgba(215,167,67,.12);border-color:rgba(215,167,67,.5)}.sdpp-more-arrow{font-size:9px;opacity:.85;transition:transform .2s ease}.sdpp-full-section{margin-top:6px;animation:sdppFadeIn .2s ease}@keyframes sdppFadeIn{from{opacity:0;transform:translateY(-5px)}to{opacity:1;transform:none}}
      .sdpp-report-box{margin-top:12px;text-align:right;border:1px solid rgba(230,107,112,.22);border-radius:12px;padding:11px;background:#10171b}.sdpp-report-box label{display:block;font-size:12px;margin-bottom:6px;color:#c7d0d4}.sdpp-report-box textarea{box-sizing:border-box;width:100%;resize:vertical;border:1px solid #2c3b42;border-radius:9px;background:#080d10;color:#fff;padding:9px;font:13px/1.6 inherit;outline:none}.sdpp-report-box>div{display:flex;gap:7px;margin-top:8px}.sdpp-report-box button{border:0;border-radius:8px;padding:8px 11px;background:#26333a;color:#fff;font-family:inherit;cursor:pointer}.sdpp-report-box button.send{background:#a53238}.sdpp-guest-note{margin:2px auto 12px;max-width:290px;color:#8f9da3;font-size:11px;line-height:1.7}.sdpp-actions-guest{grid-template-columns:1fr}.sdpp-actions-guest .sdpp-action{background:#151c20}.sdpp-loading{padding:80px 24px;text-align:center;color:#9ca9ae}.sdpp-loading.error{color:#ef8c91}
      #sdpp-rating-layer{z-index:23020;align-items:center!important}.sdpp-rating-card{width:min(330px,100%);background:#0c1114;border:1px solid rgba(255,255,255,.1);border-radius:20px;padding:22px;text-align:center;box-shadow:0 24px 80px rgba(0,0,0,.58);direction:rtl}.sdpp-rating-avatar{width:82px;height:82px;border-radius:50%;overflow:hidden;background:#26343a;border:2px solid #d7a743;display:grid;place-items:center;margin:0 auto 10px;font-size:24px;font-weight:800}.sdpp-rating-avatar img{width:100%;height:100%;object-fit:cover}.sdpp-rating-card strong{font-size:19px}.sdpp-rating-card p{font-size:12px;color:#94a1a7;margin:6px 0 15px}.sdpp-rating-actions{display:grid;grid-template-columns:1fr 1fr;gap:9px;direction:rtl}.sdpp-rating-actions button{min-height:48px;border-radius:11px;border:1px solid rgba(255,255,255,.1);background:#14201f;color:#fff;font-family:inherit;font-weight:750;display:flex;align-items:center;justify-content:center;gap:7px;cursor:pointer}.sdpp-rating-actions button:last-child{background:#171b1e}.sdpp-rating-skip{margin-top:10px;border:0;background:transparent;color:#7f8b91;font-family:inherit;cursor:pointer;padding:6px 14px}.sdpp-toast{position:fixed;z-index:24000;left:50%;bottom:calc(env(safe-area-inset-bottom,0px) + 22px);transform:translate(-50%,12px);opacity:0;pointer-events:none;padding:9px 13px;border-radius:10px;background:#17372d;color:#eaf7f1;font:12px system-ui;transition:.16s;max-width:min(420px,88vw);text-align:center}.sdpp-toast.show{opacity:1;transform:translate(-50%,0)}.sdpp-toast.error{background:#5d2428;color:#ffecef}
      @media(max-width:520px){#sdpp-layer.open,#sdpp-rating-layer.open{padding:10px}.sdpp-cover{height:112px}.sdpp-avatar{width:118px;height:118px;margin-top:-59px}.sdpp-profile-body{padding:0 14px 15px}.sdpp-name-row strong{font-size:20px}.sdpp-actions{grid-template-columns:54px 1fr 82px;gap:6px}.sdpp-action{font-size:12px;padding:7px 6px}.sdpp-stats b{font-size:14px}.sdpp-stats>div{padding:0 4px}}
    `;
    style.textContent+=`
      #sdpp-card{background:#121719;width:min(470px,100%);border-color:#303a3f}
      #sdpp-card.sd-profile-expanded{width:min(540px,100%)}
      #sdpp-card [hidden]{display:none!important}
      #sdpp-card .sdpp-cover{height:145px;background:url('/platform/assets/profile/identity/samidev-night-cover.png') center 46%/cover}
      #sdpp-card .sdpp-cover:after,#sdpp-card .sdpp-cover-mark,#sdpp-card .sdpp-divider{display:none}
      #sdpp-card .sdpp-avatar{width:118px;height:118px;margin-top:-59px;box-shadow:0 0 0 4px #121719;border-color:#deba6c}
      #sdpp-card .sdpp-name-row{margin-top:18px;flex-wrap:wrap;gap:6px}
      #sdpp-card .sdpp-name-row strong{max-width:170px;font-size:21px}
      #sdpp-card .sdpp-stars{margin:0;gap:0}
      #sdpp-card .sdpp-handle{margin-top:14px;color:#99a5a9;font-size:12px}
      #sdpp-card.sd-profile-expanded .sd-featured-rank{display:none}
      #sdpp-card .sdpp-stats{margin-top:24px;border:0;padding:10px 0}
      #sdpp-card .sdpp-actions{margin:16px 0 0;grid-template-columns:38px minmax(90px,1fr) 44px 44px;gap:6px}
      #sdpp-card .sdpp-actions-guest{grid-template-columns:1fr}
      #sdpp-card .sdpp-action{height:46px;min-height:46px;padding:6px}
      #sdpp-card .sdpp-action.report .sdpp-icon{display:inline-block}
      #sdpp-card .sdpp-action.reputation{display:flex}
      #sdpp-card .sdpp-action.reputation span:not(.sdpp-icon),#sdpp-card .sdpp-action.reputation small{display:none}
      #sdpp-card .sdpp-action.collection{background:#655295}
      #sdpp-card .sdpp-icon-collection{background:url('/platform/assets/profile/identity/profile-atlas.png') 33.333% 100%/400% 200%}
      #sdpp-card .sdpp-action{border:0;border-radius:11px}
      #sdpp-card .sdpp-action.friend{background:#237b89}
      #sdpp-card .sdpp-action.reputation{background:#b4772a}
      #sdpp-card .sdpp-icon-star,#sdpp-card .sdpp-icon-fire,#sdpp-card .sdpp-icon-trophy,#sdpp-card .sdpp-icon-calendar,#sdpp-card .sdpp-icon-friend,#sdpp-card .sdpp-icon-report{background-image:url('/platform/assets/profile/identity/profile-atlas.png');background-size:400% 200%}
      #sdpp-card .sdpp-icon-star{background-position:0 0}
      #sdpp-card .sdpp-icon-fire{background-position:33.333% 0}
      #sdpp-card .sdpp-icon-trophy{background-position:66.667% 0}
      #sdpp-card .sdpp-icon-calendar{background-position:100% 0}
      #sdpp-card .sdpp-icon-friend{background-position:0 100%}
      #sdpp-card .sdpp-icon-report{background-position:66.667% 100%}
      #sdpp-card .sd-open-full{width:100%;margin:16px 0 4px;padding:8px;border:1px solid #303a3f;border-radius:999px;background:transparent;color:#65cbbc;cursor:pointer}
      #sdpp-card .sdpp-close{color:#f1f3ef;font-size:26px}
    `;
    document.head.appendChild(style);

    layer=document.createElement('div');layer.id='sdpp-layer';layer.className='sdpp-layer';layer.setAttribute('aria-hidden','true');
    card=document.createElement('div');card.id='sdpp-card';layer.appendChild(card);document.body.appendChild(layer);
    layer.addEventListener('click',e=>{if(e.target===layer)closeProfile();});

    ratingLayer=document.createElement('div');ratingLayer.id='sdpp-rating-layer';ratingLayer.setAttribute('aria-hidden','true');document.body.appendChild(ratingLayer);
    toastBox=document.createElement('div');toastBox.className='sdpp-toast';document.body.appendChild(toastBox);

    const n=net();
    n?.on?.('assignment',()=>{resetRoomState();positionLayer();});
    n?.on?.('room_state',()=>{positionLayer();});
    n?.on?.('start',()=>{positionLayer();});
    n?.on?.('left_room',()=>{resetRoomState();});
    window.addEventListener('resize',positionLayer,{passive:true});
    // Avatar taps are handled natively by main.js Avatar.image.onTap -> SamiDev.showProfile(seat).
    // Do not place transparent hit targets over WebGL or stop pointer propagation here.
    if(window.ResizeObserver)new ResizeObserver(positionLayer).observe(canvas);
    setInterval(()=>{positionLayer();pollGameOver();},500);
    positionLayer();
  }

  window.SamiDevPlayerProfileUI={
    openSeat(seat){const p=currentRoster().find(x=>x&&Number(x.seat)===Number(seat));if(p)openProfile(p);},
    openUser(accountId,name){
      const p=currentRoster().find(x=>x&&(x.accountId===accountId||String(x.seat)===String(accountId)));
      if(p)openProfile(p);else if(accountId)openProfile({accountId,name:name||'Player'});
    },
    refresh(){positionLayer();}
  };
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',build,{once:true});else build();
})();
