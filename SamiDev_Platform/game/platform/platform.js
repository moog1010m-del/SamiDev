(() => {
  'use strict';
  const $ = (s, root=document) => root.querySelector(s);
  const $$ = (s, root=document) => [...root.querySelectorAll(s)];
  const state = { user:null, rooms:[], communities:[], activeCommunity:null, communityMembers:[], communityMessages:[], friends:[], requests:[], store:null, page:'lobby', poll:null, settings:{gameId:'carrom',players:'0',live:'1'} };
  const modeNames = ['Classic','Pool','Freestyle 120','Freestyle 160','Freestyle 210'];
  let toastTimer, activePublicProfile=null;

  function preferredTheme(){
    try{const saved=localStorage.getItem('samidev_theme');if(saved==='light'||saved==='dark')return saved;}catch(_){}
    return window.matchMedia&&window.matchMedia('(prefers-color-scheme: light)').matches?'light':'dark';
  }
  function applyTheme(theme,{persist=true}={}){
    theme=theme==='light'?'light':'dark';
    document.documentElement.dataset.theme=theme;
    document.documentElement.style.colorScheme=theme;
    const meta=document.querySelector('meta[name="theme-color"]');if(meta)meta.content=theme==='light'?'#f4f7f8':'#0b1016';
    $$('.theme-toggle').forEach(btn=>{
      btn.dataset.theme=theme;
      btn.setAttribute('aria-label',theme==='light'?'تفعيل الوضع الداكن':'تفعيل الوضع الفاتح');
      const label=btn.querySelector('.theme-label');if(label)label.textContent=theme==='light'?'داكن':'فاتح';
    });
    if(persist)try{localStorage.setItem('samidev_theme',theme);}catch(_){}
  }
  function toggleTheme(){applyTheme(document.documentElement.dataset.theme==='light'?'dark':'light');}

  function toast(message, error=false){
    const el=$('#toast'); el.textContent=message; el.className='toast show'+(error?' error':'');
    clearTimeout(toastTimer); toastTimer=setTimeout(()=>el.className='toast',3000);
  }
  async function api(path, options={}){
    const opts={credentials:'same-origin',...options};
    opts.headers={'Content-Type':'application/json',...(options.headers||{})};
    const r=await fetch(path,opts); let data={};
    try{data=await r.json();}catch(_){data={ok:false,message:`HTTP ${r.status}`};}
    if(!r.ok||data.ok===false) throw Object.assign(new Error(data.message||'فشل الطلب'),{status:r.status,code:data.error});
    return data;
  }
  function initials(name){return (name||'P').trim().slice(0,1).toUpperCase();}
  function escapeHtml(v){return String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));}
  function playerSinceValue(accountAgeDays,createdAt){
    let days=Number(accountAgeDays);
    if(!Number.isFinite(days)||days<0){
      const created=Number(createdAt);
      days=Number.isFinite(created)&&created>0?Math.max(0,Math.floor((Date.now()-created)/86400000)):0;
    }
    days=Math.max(0,Math.floor(days));
    if(days>=3&&days<=10)return `${days} أيام`;
    return `${days} يوم`;
  }
  function formatProfileStat(value){
    const n=Math.max(0,Math.floor(Number(value)||0));
    return n.toLocaleString('en-US');
  }
  const DEFAULT_AVATAR_URL='/images/default-avatar.png';
  function wireAvatarImage(image, fallback=null){
    if(!image)return;
    if(image.dataset.avatarWired==='1')return;
    image.dataset.avatarWired='1';
    image.addEventListener('load',()=>{image.classList.remove('hidden');if(fallback)fallback.classList.add('hidden');});
    image.addEventListener('error',()=>{
      if(image.src.endsWith(DEFAULT_AVATAR_URL)){
        image.classList.add('hidden');if(fallback)fallback.classList.remove('hidden');return;
      }
      image.src=DEFAULT_AVATAR_URL;
    });
  }
  function wireAvatarImages(root=document){
    $$('img[data-avatar-fallback]',root).forEach(image=>wireAvatarImage(image));
  }
  function renderAvatar(imageSelector,fallbackSelector,name,avatarData){
    const image=$(imageSelector), fallback=$(fallbackSelector);
    if(!image||!fallback)return;
    fallback.textContent=initials(name);
    wireAvatarImage(image,fallback);
    image.src=avatarData||DEFAULT_AVATAR_URL;
  }
  function setUser(user){
    state.user=user;
    const renameStatus=$('#profile-rename-status');if(renameStatus)renameStatus.textContent=user.freeRenameAvailable?'تغيير اسم المستخدم مجانًا مرة واحدة.':`بطاقات تغيير الاسم: ${Number(user.renameCredits)||0} · يمكن شراؤها من المتجر.`;
    window.SamiDevMobile?.postMessage(JSON.stringify({type:'platform_ready',role:user.role||'user'}));
    const name=user.displayName||user.username;
    $('#side-name').textContent=name; $('#side-username').textContent=user.username;
    $('#profile-name').textContent=name;
    const handle=$('#profile-identity-handle');if(handle)handle.textContent=String(user.username||'player');
    const sinceValue=$('#profile-since-value');if(sinceValue)sinceValue.textContent=playerSinceValue(user.accountAgeDays,user.createdAt);
    const wins=$('#profile-wins');if(wins)wins.textContent=formatProfileStat(user.wins);
    const reputation=$('#profile-reputation');if(reputation)reputation.textContent=formatProfileStat(user.reputation);
    const displayInput=$('#profile-display-input');
    if(displayInput&&document.activeElement!==displayInput)displayInput.value=name;
    const count=$('#profile-name-count');if(count)count.textContent=String((displayInput?.value||name).length);
    renderAvatar('#avatar-image','#avatar-fallback',name,user.avatarData);
    renderAvatar('#profile-avatar-image','#profile-avatar-fallback',name,user.avatarData);
    renderAvatar('#profile-editor-avatar-image','#profile-editor-avatar-fallback',name,user.avatarData);
    renderAvatar('#lobby-avatar-image','#lobby-avatar-fallback',name,user.avatarData);
    renderAvatar('#community-user-avatar-image','#community-user-avatar-fallback',name,user.avatarData);
    document.querySelectorAll('.lobby-profile .lobby-profile-cover,#page-profile .profile-cover').forEach(el=>window.SamiDevCosmetics?.cover(el,user.profileBanner));
    const communityUserName=$('#community-user-name');if(communityUserName)communityUserName.textContent=name;
    const communityUserHandle=$('#community-user-handle');if(communityUserHandle)communityUserHandle.textContent=String(user.username||'player');
    const lobbyName=$('#lobby-profile-name');if(lobbyName)lobbyName.textContent=name;
    const lobbyHandle=$('#lobby-profile-handle');if(lobbyHandle)lobbyHandle.textContent=String(user.username||'player');
    const lobbyAccount=$('#lobby-profile-account');if(lobbyAccount)lobbyAccount.textContent=String(user.username||'player');
    const lobbySince=$('#lobby-profile-since');if(lobbySince)lobbySince.textContent=playerSinceValue(user.accountAgeDays,user.createdAt);
    const lobbyWins=$('#lobby-profile-wins');if(lobbyWins)lobbyWins.textContent=formatProfileStat(user.wins);
    const lobbyRep=$('#lobby-profile-reputation');if(lobbyRep)lobbyRep.textContent=formatProfileStat(user.reputation);
    const storeBalance=$('#store-balance');if(storeBalance&&user.coins!=null)storeBalance.textContent=formatProfileStat(user.coins);
    const badgeAsset=user.nameBadgeAsset||'/platform/assets/profile/raster/palm-swords.webp';
    const badgeName=user.nameBadgeName||'سيفين ونخلة';
    $$('.profile-name-row .profile-sticker').forEach(el=>{
      window.SamiDevStickerArt.render(el,badgeAsset,badgeName);
      el.setAttribute('aria-label',badgeName);
      el.setAttribute('title',badgeName);
    });
    const userStars=Math.max(0,Math.min(5,Number(user.starsCount??0)));
    $$('#page-profile .profile-stars,.lobby-profile-stars,#profile-editor .profile-stars').forEach(root=>{
      root.setAttribute('aria-label',`${userStars} نجوم زينة مملوكة`);
      root.querySelectorAll('.profile-sprite').forEach((el,i)=>{el.hidden=i>=userStars;el.classList.remove('dim');});
    });
    if(Array.isArray(user.showcaseItems))window.SamiDevProfileDetails?.render($('#own-profile-details'),user,{own:true});
    else refreshOwnProfile();
    const admin=user.role==='admin'; $('#admin-nav').classList.toggle('hidden',!admin); $('#admin-bottom').classList.toggle('hidden',!admin);
  }
  let ownProfileRequest=0;
  async function refreshOwnProfile(){
    const id=state.user?.id;if(!id)return;const request=++ownProfileRequest;
    try{const data=await api('/api/public-profile/'+encodeURIComponent(id));
      if(request!==ownProfileRequest||state.user?.id!==id)return;
      Object.assign(state.user,{showcaseItems:data.user.showcaseItems,gameStatistics:data.user.gameStatistics,legacyWins:data.user.legacyWins,profileBanner:data.user.profileBanner,chatBubble:data.user.chatBubble,nameBadge:data.user.nameBadge,starsCount:data.user.starsCount,nameBadgeAsset:data.user.nameBadgeAsset,nameBadgeName:data.user.nameBadgeName});
      setUser(state.user);
    }catch(_){const node=$('#own-profile-details');if(node&&!node.children.length)node.textContent='تعذر تحميل المقتنيات والإحصاءات. افتح الملف مجددًا للمحاولة.';}
  }
  async function avatarDataFromFile(file){
    if(!file||!String(file.type||'').startsWith('image/'))throw new Error('اختر ملف صورة صالح');
    if(file.size>12*1024*1024)throw new Error('الصورة الأصلية كبيرة جدًا');
    const url=URL.createObjectURL(file);
    try{
      const image=await new Promise((resolve,reject)=>{const img=new Image();img.onload=()=>resolve(img);img.onerror=()=>reject(new Error('تعذر قراءة الصورة'));img.src=url;});
      const side=Math.min(image.naturalWidth,image.naturalHeight);
      const sx=Math.floor((image.naturalWidth-side)/2), sy=Math.floor((image.naturalHeight-side)/2);
      const canvas=document.createElement('canvas');canvas.width=320;canvas.height=320;
      const ctx=canvas.getContext('2d',{alpha:false});if(!ctx)throw new Error('تعذر تجهيز الصورة');
      ctx.drawImage(image,sx,sy,side,side,0,0,320,320);
      let data=canvas.toDataURL('image/webp',.82);
      if(!data.startsWith('data:image/webp'))data=canvas.toDataURL('image/jpeg',.82);
      if(data.length>410000)data=canvas.toDataURL('image/jpeg',.68);
      if(data.length>410000)throw new Error('تعذر ضغط الصورة للحجم المناسب');
      return data;
    }finally{URL.revokeObjectURL(url);}
  }
  function presetAvatarData(index,name){
    const palettes=[
      ['#3d1d1d','#10191b','#8e302c','#e0b67f','#e0ac49'],
      ['#17363d','#0b1517','#ece6d6','#e0c195','#252729'],
      ['#44341f','#101719','#b99455','#cfa16c','#17191b'],
      ['#303839','#0a1416','#323738','#b98661','#15191a'],
      ['#47231f','#10191a','#90312c','#d6a96f','#d9a54a']
    ];
    const c=palettes[Math.max(0,Math.min(palettes.length-1,Number(index)||0))], canvas=document.createElement('canvas');
    canvas.width=320;canvas.height=320;const ctx=canvas.getContext('2d',{alpha:false});if(!ctx)throw new Error('تعذر تجهيز الأفاتار');
    const g=ctx.createLinearGradient(0,0,320,320);g.addColorStop(0,c[0]);g.addColorStop(1,c[1]);ctx.fillStyle=g;ctx.fillRect(0,0,320,320);
    ctx.fillStyle='rgba(255,255,255,.035)';for(let x=-320;x<640;x+=42){ctx.save();ctx.translate(x,0);ctx.rotate(-.48);ctx.fillRect(0,-90,2,520);ctx.restore();}
    ctx.fillStyle=c[3];ctx.beginPath();ctx.arc(160,116,54,0,Math.PI*2);ctx.fill();
    ctx.fillStyle=c[2];ctx.beginPath();ctx.moveTo(63,320);ctx.quadraticCurveTo(73,203,160,190);ctx.quadraticCurveTo(247,203,257,320);ctx.closePath();ctx.fill();
    ctx.strokeStyle=c[4];ctx.lineWidth=13;ctx.beginPath();ctx.moveTo(99,153);ctx.lineTo(221,153);ctx.stroke();
    ctx.fillStyle='rgba(7,15,16,.78)';ctx.beginPath();ctx.moveTo(107,73);ctx.quadraticCurveTo(159,28,213,73);ctx.lineTo(211,102);ctx.quadraticCurveTo(160,70,109,102);ctx.closePath();ctx.fill();
    const initial=initials(name);ctx.fillStyle='rgba(255,255,255,.12)';ctx.font='900 86px Arial';ctx.textAlign='center';ctx.fillText(initial,160,294);
    let data=canvas.toDataURL('image/webp',.86);if(!data.startsWith('data:image/webp'))data=canvas.toDataURL('image/jpeg',.86);return data;
  }
  async function saveAvatarData(avatarData,message='تم تحديث صورة الملف الشخصي'){
    const d=await api('/api/profile',{method:'PATCH',body:JSON.stringify({avatarData})});setUser(d.user);toast(message);return d.user;
  }
  function openProfileEditor(){
    const editor=$('#profile-editor'), backdrop=$('#profile-editor-backdrop');
    if(editor){editor.classList.add('open');editor.setAttribute('aria-hidden','false');}
    if(backdrop){backdrop.classList.add('open');backdrop.setAttribute('aria-hidden','false');}
    document.body.classList.add('profile-editor-open');
  }
  function closeProfileEditor(){
    const editor=$('#profile-editor'), backdrop=$('#profile-editor-backdrop');
    if(editor){editor.classList.remove('open');editor.setAttribute('aria-hidden','true');}
    if(backdrop){backdrop.classList.remove('open');backdrop.setAttribute('aria-hidden','true');}
    document.body.classList.remove('profile-editor-open');
  }
  let guestResume=null;
  function resumeGuest(){
    if(guestResume)return guestResume;
    guestResume=api('/api/auth/guest',{method:'POST',body:'{}'}).then(d=>{setUser(d.user);showApp();}).catch(error=>toast(error.message,true)).finally(()=>{guestResume=null;});
    return guestResume;
  }
  function showAuth({accountSettings=false}={}){ if(!accountSettings){clearInterval(state.poll);resumeGuest();return;}state.store=null; document.body.classList.remove('community-mode'); $('#auth-screen').classList.remove('hidden'); $('#app').classList.add('hidden'); clearInterval(state.poll); }
  function showApp(){ $('#auth-screen').classList.add('hidden'); $('#app').classList.remove('hidden'); navigate('lobby'); startPolling(); loadFriends(); handlePendingInvite(); restoreCommunityFromLocation(); const url=new URL(location.href),reason=url.searchParams.get('notice'),notices={ROOM_WAIT_EXPIRED:'انتهت مهلة انتظار اللاعبين',TABLE_CLOSED:'أغلق منشئ الطاولة المباراة قبل اللعب',TABLE_KICKED:'أخرجك منشئ الطاولة قبل بدء اللعب',COMMUNITY_BANNED:'أُخرجت من المساحة بسبب الحظر',COMMUNITY_KICKED:'أُخرجت من المساحة لمدة دقيقة'};if(notices[reason]){toast(notices[reason]);url.searchParams.delete('notice');history.replaceState(null,'',url);}}

  async function boot(){
    applyTheme(preferredTheme(),{persist:false});
    bind();
    const authControls=$$('.auth-form input,.auth-form button,.auth-tab');authControls.forEach(node=>node.disabled=true);
    try{await window.SamiDevFirebaseAuth.mount({api,currentUser:()=>state.user,onAuthenticated:user=>{setUser(user);showApp();}});authControls.forEach(node=>node.disabled=false);}catch(err){toast('تعذر تحميل إعدادات تسجيل الدخول. أعد تحميل الصفحة.',true);return;}
    try{let d;try{d=await api('/api/me');}catch(error){if(error.status!==401)throw error;d=await api('/api/auth/guest',{method:'POST',body:'{}'});}setUser(d.user);showApp();}catch(error){toast(error.message,true);}
  }
  function selectCreateGame(gameId){
    const pool=gameId==='pool';
    const soccer=gameId==='tablesoccer';
    const cards=gameId==='crazy8';
    state.settings.gameId=window.SamiDevGames.get(gameId).id;
    $('#create-game').value=state.settings.gameId;
    $$('[data-create-game]').forEach(button=>{
      const selected=button.dataset.createGame===state.settings.gameId;
      button.classList.toggle('selected',selected);
      button.setAttribute('aria-pressed',String(selected));
    });
    $$('.carrom-setting').forEach(x=>x.classList.toggle('hidden',soccer||cards||pool));
    $$('.soccer-setting').forEach(x=>x.classList.toggle('hidden',!soccer));
    $$('.crazy8-setting').forEach(x=>x.classList.toggle('hidden',!cards));
    $$('.pool-setting').forEach(x=>x.classList.toggle('hidden',!pool));
    $$('.board-players-setting').forEach(x=>x.classList.toggle('hidden',cards||pool));
    $('#create-game-description').textContent=pool?'اختر نوع البلياردو: إيت بول أو ناين بول أو الثلاثي أو قيم بول.':cards?'طابق اللون أو الرقم وتخلّص من أوراقك أولًا.':soccer?'فريقان، تسديدات وتمريرات وأهداف.':'الكيرم الكلاسيكي وأنماط النقاط.';
    $('#create-go').textContent=pool?'إنشاء مباراة بلياردو':cards?'إنشاء مباراة أونو':soccer?'إنشاء مباراة كرة الطاولة':'إنشاء مباراة الكيرم';
  }
  function openCreateGame(gameId=state.settings.gameId){
    if(!state.activeCommunity)return toast('اختر مساحة أولًا',true);
    selectCreateGame(gameId);
    $('#create-modal').classList.remove('hidden');
    $('#create-modal .modal-card').scrollTop=0;
  }
  function bind(){
    $$('.auth-tab').forEach(b=>b.onclick=()=>{$$('.auth-tab').forEach(x=>x.classList.toggle('active',x===b));$('#login-form').classList.toggle('hidden',b.dataset.auth!=='login');$('#register-form').classList.toggle('hidden',b.dataset.auth!=='register');});
    $('#login-form').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.currentTarget);try{const d=await api('/api/auth/login',{method:'POST',body:JSON.stringify(Object.fromEntries(f))});setUser(d.user);showApp();}catch(err){toast(err.message,true);}};
    $('#register-form').onsubmit=async e=>{e.preventDefault();const f=new FormData(e.currentTarget);try{const d=await api('/api/auth/register',{method:'POST',body:JSON.stringify(Object.fromEntries(f))});setUser(d.user);showApp();}catch(err){toast(err.message,true);}};
    $('#account-settings-btn').onclick=()=>{closeProfileEditor();showAuth({accountSettings:true});};
    $('#auth-back').onclick=()=>{if(window.SamiDevFirebaseAuth?.cancel?.()===false)return;if(state.user)showApp();};
    $('#logout-btn').onclick=async()=>{try{await api('/api/auth/logout',{method:'POST',body:'{}'});}catch(err){toast(err.message,true);return;}try{sessionStorage.removeItem('samidev_reconnect');sessionStorage.removeItem('samidev_return_community');}catch(_){}window.SamiDevFirebaseAuth?.clear();state.user=null;try{const d=await api('/api/auth/guest',{method:'POST',body:'{}'});setUser(d.user);showApp();}catch(error){toast(error.message,true);}};
    $$('.nav-btn,.bottom-btn,[data-page]').forEach(b=>b.addEventListener('click',()=>navigate(b.dataset.page)));
    $$('.theme-toggle').forEach(b=>b.addEventListener('click',toggleTheme));
    $$('[data-community-tab]').forEach(button=>button.addEventListener('click',()=>{
      const tab=button.dataset.communityTab;
      $('.community-layout').dataset.mobileTab=tab;
      $$('[data-community-tab]').forEach(item=>item.setAttribute('aria-selected',String(item===button)));
      if(tab==='chat'){const box=$('#community-chat-messages');box.scrollTop=box.scrollHeight;}
    }));
    $('#community-self-profile').onclick=()=>navigate('profile');
    $('#community-profile-page').onclick=()=>navigate('profile');
    $('#community-profile-edit').onclick=()=>{navigate('profile');requestAnimationFrame(openProfileEditor);};
    $('#refresh-communities').onclick=()=>loadCommunities(true);
    $('#refresh-rooms').onclick=()=>loadCommunityState(true);
    $('#mobile-menu').onclick=()=>navigate('lobby');
    $('#leave-community').onclick=leaveCommunity;
    const exitCommunity=$('#exit-community');if(exitCommunity)exitCommunity.onclick=leaveCommunity;
    $('#community-profile-close').onclick=()=>{$('#community-profile-modal').classList.contains('sd-profile-expanded')?setPublicProfileFull(false):closeCommunityProfile();};
    $('#community-profile-modal').addEventListener('click',e=>{if(e.target.id==='community-profile-modal')closeCommunityProfile();});
    $('#community-profile-friend').onclick=communityProfileFriendAction;
    $('#community-profile-full').onclick=()=>setPublicProfileFull(true);
    $('#community-profile-collection').onclick=()=>{setPublicProfileFull(true);$('#sd-public-extra .sd-collection-section')?.scrollIntoView({block:'start',behavior:'smooth'});};
    $('#community-profile-reputation-btn').onclick=communityProfileReputationAction;
    $('#community-profile-report').onclick=()=>{$('#community-profile-report-box').classList.remove('hidden');$('#community-profile-report-text').focus();};
    $('#community-profile-report-cancel').onclick=()=>$('#community-profile-report-box').classList.add('hidden');
    $('#community-profile-report-send').onclick=communityProfileReportAction;
    document.addEventListener('click',e=>{const target=e.target.closest?.('[data-public-profile]');if(target)openCommunityProfile(target.dataset.publicProfile);});
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&$('#community-profile-modal')?.classList.contains('open'))closeCommunityProfile();if((e.key==='Enter'||e.key===' ')&&e.target?.matches?.('[data-public-profile]')){e.preventDefault();openCommunityProfile(e.target.dataset.publicProfile);}});
    $('#community-chat-form').onsubmit=sendCommunityChat;
    $('#community-chat-input').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();sendCommunityChat(e);}});
    $('#create-game').onchange=()=>selectCreateGame($('#create-game').value);
    $$('[data-create-game]').forEach(button=>button.onclick=()=>selectCreateGame(button.dataset.createGame));
    $$('[data-quick-game]').forEach(button=>button.onclick=()=>openCreateGame(button.dataset.quickGame));
    $('#open-create').onclick=()=>openCreateGame();
    $$('[data-close]').forEach(b=>b.onclick=()=>$('#'+b.dataset.close).classList.add('hidden'));
    selectCreateGame(state.settings.gameId);
    $('#create-modal').addEventListener('click',e=>{if(e.target.id==='create-modal')e.currentTarget.classList.add('hidden');});
    $$('[data-setting]').forEach(b=>b.onclick=()=>{const key=b.dataset.setting;state.settings[key]=b.dataset.value;$$(`[data-setting="${key}"]`).forEach(x=>x.classList.toggle('selected',x===b));});
    $('#create-go').onclick=createRoom;
    $('#friend-add').onsubmit=async e=>{e.preventDefault();const username=new FormData(e.currentTarget).get('username');try{const d=await api('/api/friends/request',{method:'POST',body:JSON.stringify({username})});toast(d.status==='accepted'?'تمت إضافة الصديق':'تم إرسال الطلب');e.currentTarget.reset();loadFriends();}catch(err){toast(err.message,true);}};
    $('#search-btn').onclick=searchUsers; $('#user-search').addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();searchUsers();}});
    $('#admin-refresh').onclick=loadAdmin;
    window.matchMedia('(max-width:600px)').addEventListener('change',()=>{state.storePage=0;if(state.store)renderStore();});
    $('#store-refresh').onclick=()=>loadStore(true);
    const photoInput=$('#profile-photo-input');
    const choosePhoto=()=>photoInput.click();
    $('#profile-photo-btn').onclick=openProfileEditor;
    $('#profile-editor-upload').onclick=choosePhoto;
    $('#profile-upload-button').onclick=choosePhoto;
    $('#profile-edit-toggle').onclick=openProfileEditor;
    $('#profile-editor-close').onclick=closeProfileEditor;
    $('#profile-editor-backdrop').onclick=closeProfileEditor;
    document.addEventListener('keydown',e=>{if(e.key==='Escape'&&$('#profile-editor')?.classList.contains('open'))closeProfileEditor();});
    photoInput.onchange=async e=>{
      const input=e.currentTarget, file=input.files&&input.files[0];
      if(!file)return;
      try{await saveAvatarData(await avatarDataFromFile(file));}
      catch(err){toast(err.message||'تعذر تحديث الصورة',true);}
      finally{input.value='';}
    };
    $$('.profile-preset').forEach(button=>button.onclick=async()=>{
      try{button.disabled=true;await saveAvatarData(presetAvatarData(button.dataset.avatarPreset,state.user?.displayName||state.user?.username),'تم اختيار الأفاتار');}
      catch(err){toast(err.message||'تعذر اختيار الأفاتار',true);}
      finally{button.disabled=false;}
    });
    $('#profile-display-input').addEventListener('input',e=>$('#profile-name-count').textContent=String(e.currentTarget.value.length));
    $('#profile-save-name').onclick=async()=>{
      const username=$('#profile-display-input').value.trim();
      if(!/^[A-Za-z0-9_]{3,20}$/.test(username))return toast('اسم المستخدم: ٣–٢٠ حرفًا إنجليزيًا أو رقمًا أو _ بدون @',true);
      if(!confirm('تغيير اسم المستخدم؟ '+(state.user?.freeRenameAvailable?'هذا التغيير مجاني.':'سيتم استهلاك بطاقة تغيير اسم.')))return;
      try{const d=await api('/api/profile',{method:'PATCH',body:JSON.stringify({username})});setUser(d.user);toast('تم حفظ التغييرات');}
      catch(err){toast(err.message||'تعذر حفظ الاسم',true);}
    };
    $('#profile-remove-photo').onclick=async()=>{try{await saveAvatarData('','تمت إزالة الصورة');}catch(err){toast(err.message||'تعذر إزالة الصورة',true);}};
  }
  async function loadStore(manual=false){
    try{
      const d=await api('/api/store');state.store=d;
      if(state.user){
        state.user.coins=Number(d.coins)||0;
        state.user.renameCredits=Number(d.renameCredits)||0;
        const renameStatus=$('#profile-rename-status');if(renameStatus&&!state.user.freeRenameAvailable)renameStatus.textContent=`بطاقات تغيير الاسم: ${state.user.renameCredits} · يمكن شراؤها من المتجر.`;
        if(d.starsCount!==undefined)state.user.starsCount=d.starsCount;
        const balance=$('#store-balance');if(balance)balance.textContent=formatProfileStat(d.coins);
      }
      renderStore();if(manual)toast('تم تحديث المتجر');
    }catch(err){if(err.status===401)return showAuth();toast(err.message||'تعذر تحميل المتجر',true);}
  }
  function wireStoreCategoryButtons(){
    const bar=$('#store-category-bar');
    if(!bar||bar.dataset.wired==='1')return;
    bar.dataset.wired='1';
    bar.querySelectorAll('.store-category-btn').forEach(btn=>{
      btn.addEventListener('click',()=>{
        bar.querySelectorAll('.store-category-btn').forEach(b=>b.classList.toggle('active',b===btn));
        state.storeCategory=btn.dataset.category||'all';state.storePage=0;
        renderStore();
      });
    });
  }
  function cosmeticProductArt(item,className=''){
    if(item.consumable)return `<div class="store-name-preview">↻ <strong>تغيير الاسم</strong></div>`;
    if(item.slot==='chat_bubble')return `<div class="store-chat-sample ${escapeHtml(className)}"><div class="store-chat-preview-meta"><strong>${escapeHtml(state.user?.displayName||state.user?.username||'لاعب')}</strong><small>الآن</small></div><div class="store-chat-preview" data-chat-cosmetic="${escapeHtml(item.id)}"><span>مرحبًا</span></div></div>`;
    if(item.slot==='profile_banner'&&!item.asset)return '<img class="store-item-visual store-banner-art" src="/platform/assets/profile/identity/samidev-night-cover.png" alt="الغلاف الافتراضي">';
    return window.SamiDevStickerArt.markup(item.asset,className+(item.slot==='profile_banner'?' store-banner-art':''),item.name);
  }
  function applyCosmeticPreviews(root){root.querySelectorAll('[data-chat-cosmetic]').forEach(el=>window.SamiDevCosmetics?.bubble(el,el.dataset.chatCosmetic));}
  function renderStore(){
    wireStoreCategoryButtons();
    const data=state.store||{}, catalog=Array.isArray(data.catalog)?data.catalog:[], inventory=Array.isArray(data.inventory)?data.inventory:[], ledger=Array.isArray(data.ledger)?data.ledger:[];
    const userStars=Number(data.starsCount??state.user?.starsCount??5);
    const selectedCat=state.storeCategory||'profile';
    $$('.store-category-btn').forEach(button=>button.classList.toggle('active',button.dataset.category===selectedCat));
    const balance=$('#store-balance');if(balance)balance.textContent=formatProfileStat(data.coins);
    const owned=$('#store-owned-count');if(owned)owned.textContent=`${inventory.length} مملوك`;

    const filteredCatalog=catalog.filter(item=>{
      if(selectedCat==='all')return true;
      if(selectedCat==='profile')return item.category==='profile';
      if(selectedCat==='chat'||selectedCat==='banners')return item.category===selectedCat;
      if(selectedCat==='pool')return item.category==='pool';
      if(selectedCat==='carrom')return item.category==='carrom';
      if(selectedCat==='other')return !['profile','chat','banners','pool','carrom'].includes(item.category);
      return true;
    });

    if(selectedCat==='profile')filteredCatalog.sort((a,b)=>{const order=item=>item.slot==='profile_stars'?-1:(window.SamiDevStickerArt.cell(item.asset)??10);return order(a)-order(b);});
    const pageSize=window.matchMedia("(max-width:600px)").matches?6:12;
    const pageCount=Math.max(1,Math.ceil(filteredCatalog.length/pageSize));
    state.storePage=Math.max(0,Math.min(pageCount-1,Number(state.storePage)||0));
    const visibleCatalog=filteredCatalog.slice(state.storePage*pageSize,(state.storePage+1)*pageSize);
    const pager=$('#store-pagination');if(pager){pager.replaceChildren();pager.hidden=pageCount<=1;if(pageCount>1){
      for(const [label,delta] of [['السابق',-1],['التالي',1]]){
        const button=document.createElement('button');button.type='button';button.textContent=label;
        button.disabled=state.storePage+delta<0||state.storePage+delta>=pageCount;
        button.onclick=()=>{state.storePage+=delta;renderStore();$('#store-catalog').scrollIntoView({block:'start',behavior:'smooth'});};pager.append(button);
        if(delta===-1){const status=document.createElement('span');status.setAttribute('aria-live','polite');status.textContent=`${state.storePage+1} / ${pageCount}`;pager.append(status);}
      }
    }}
    const box=$('#store-catalog');if(box){box.replaceChildren();if(!filteredCatalog.length){box.append(emptyBlock('لا توجد عناصر متاحة في هذا القسم حاليًا.'));}else for(const item of visibleCatalog){
      const active=(data.equipped?.[item.slot]===item.id);
      const owned=item.owned||item.availableToAll||item.default;
      const card=document.createElement('article');card.className='store-item-card'+(active?' is-equipped':'');card.dataset.itemId=item.id;
      card.tabIndex=0;card.setAttribute('role','button');card.setAttribute('aria-label',`معاينة ${item.name}`);
      card.innerHTML=cosmeticProductArt(item,'store-item-visual')+`<div class="store-item-copy"><strong>${escapeHtml(item.name)}</strong><small>${escapeHtml(item.description||'')}</small><div class="store-product-footer"><span class="store-item-price">${item.price?formatProfileStat(item.price)+' <span class="coin-mark small">C</span>':'مجاني'}</span><span class="store-item-badge">${active?'مفعّل':owned?'مملوك':'معاينة'}</span></div></div>`;
      applyCosmeticPreviews(card);
      card.onclick=()=>openStoreProduct(item.id,card);
      card.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();openStoreProduct(item.id,card);}};
      box.append(card);
    }}
    const ledgerBox=$('#store-ledger');if(ledgerBox){ledgerBox.replaceChildren();if(!ledger.length){ledgerBox.append(emptyBlock('لا توجد حركات حتى الآن.'));}else for(const entry of ledger){
      const row=document.createElement('div');row.className='store-ledger-row';const mark=document.createElement('span');mark.className='coin-mark small';mark.textContent='C';
      const copy=document.createElement('div');const title=document.createElement('strong');
      title.textContent=entry.type==='daily_match_reward'?'مكافأة مباراة يومية':entry.type==='store_purchase'?'شراء من المتجر':entry.type==='username_change'?'تغيير اسم المستخدم':'حركة متجر';
      const meta=document.createElement('small');const d=new Date(Number(entry.createdAt)||Date.now());meta.textContent=(entry.roomId?`مباراة ${entry.roomId} · `:'')+d.toLocaleString('ar-SA',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});copy.append(title,meta);
      const amount=document.createElement('b');const n=Math.trunc(Number(entry.amount)||0),abs=Math.abs(n).toLocaleString('en-US');amount.textContent=`${n>=0?'+':'-'}${abs}`;row.append(mark,copy,amount);ledgerBox.append(row);
    }}
  }
  let storeProductId=null,storeProductReturnFocus=null,storePurchaseBusy=false;
  function closeStoreProduct(){
    if(storePurchaseBusy)return;
    $('#store-product-modal')?.remove();storeProductId=null;
    if(storeProductReturnFocus?.isConnected)storeProductReturnFocus.focus();else $('#store-refresh')?.focus();
  }
  function openStoreProduct(itemId,origin){
    if(storePurchaseBusy)return;
    storeProductId=itemId;storeProductReturnFocus=origin||storeProductReturnFocus;
    renderStoreProduct(false);
  }
  function renderStoreProduct(confirming=false){
    const item=(state.store?.catalog||[]).find(row=>row.id===storeProductId);if(!item)return closeStoreProduct();
    let modal=$('#store-product-modal');
    if(!modal){modal=document.createElement('div');modal.id='store-product-modal';modal.className='store-product-modal';document.body.append(modal);
      modal.addEventListener('click',event=>{if(event.target===modal)closeStoreProduct();});
      modal.addEventListener('keydown',event=>{if(event.key==='Escape'){event.preventDefault();closeStoreProduct();}if(event.key==='Tab'){const buttons=Array.from(modal.querySelectorAll('button:not(:disabled)'));const first=buttons[0],last=buttons.at(-1);if(event.shiftKey&&document.activeElement===first){event.preventDefault();last?.focus();}else if(!event.shiftKey&&document.activeElement===last){event.preventDefault();first?.focus();}}});
    }
    const coins=Number(state.store?.coins??state.user?.coins??0),price=Number(item.price)||0;
    const isStar=item.slot==='profile_stars',stars=Math.max(0,Math.min(5,Number(state.store?.starsCount??state.user?.starsCount??0)));
    const owned=item.consumable?false:isStar?stars>=5:(item.owned||item.availableToAll||item.default);
    const active=!isStar&&state.store?.equipped?.[item.slot]===item.id;
    const preview=item.slot==='name_badge'?window.SamiDevStickerArt.markup(item.asset,'store-name-sticker'):isStar?`<span class="store-preview-stars">${'★'.repeat(Math.min(5,stars+1))}</span>`:'';
    modal.innerHTML=`<section class="store-product-sheet${item.slot==='chat_bubble'?' has-chat-preview':''}" role="dialog" aria-modal="true" aria-labelledby="store-product-title">
      <header><span>رصيدك <b>${formatProfileStat(coins)}</b> <span class="coin-mark small">C</span></span><button type="button" data-product-close aria-label="إغلاق">×</button></header>
      <div class="store-product-art">${cosmeticProductArt(item)}</div>
      ${preview?`<div class="store-name-preview">${preview}<strong>${escapeHtml(state.user?.displayName||state.user?.username||'لاعب')}</strong></div>`:''}
      <h3 id="store-product-title">${escapeHtml(item.name)}</h3><p class="store-product-description">${escapeHtml(item.description||'')}</p>
      ${isStar?`<small class="store-star-count">تملك ${stars} من 5 نجوم. ${stars<5?'هذه العملية تضيف نجمة واحدة.':''}</small>`:''}
      <p class="store-product-error" role="alert" hidden></p>
      ${confirming?`<div class="store-purchase-confirm"><h4>تأكيد الشراء</h4><p>شراء ${escapeHtml(item.name)} مقابل <b>${formatProfileStat(price)} كوينز</b>؟</p><small>رصيدك بعد الشراء: ${formatProfileStat(coins-price)} كوينز</small><div><button type="button" class="ghost" data-product-back>رجوع</button><button type="button" class="primary" data-product-confirm>تأكيد الشراء</button></div></div>`:
      `<footer><strong>${price?formatProfileStat(price)+' كوينز':'مجاني'}</strong><button type="button" class="primary" data-product-action ${active||(isStar&&stars>=5)?'disabled':''}>${active?'مفعّل الآن':isStar&&stars>=5?'اكتملت النجوم':owned?'تفعيل الملصق أو التصميم':'شراء'}</button></footer>`}
    </section>`;
    applyCosmeticPreviews(modal);
    $('[data-product-close]',modal).onclick=closeStoreProduct;
    $('[data-product-back]',modal)?.addEventListener('click',()=>renderStoreProduct(false));
    $('[data-product-confirm]',modal)?.addEventListener('click',()=>buyStoreItem(item.id));
    $('[data-product-action]',modal)?.addEventListener('click',async event=>{
      if(owned){await equipStoreItem(item.id,event.currentTarget);renderStoreProduct(false);return;}
      if(coins<price){const error=$('.store-product-error',modal);error.hidden=false;error.textContent='رصيدك لا يكفي لشراء هذا العنصر.';return;}
      renderStoreProduct(true);
    });
    (confirming?$('[data-product-back]',modal):$('[data-product-close]',modal))?.focus();
  }
  async function buyStoreItem(itemId){
    if(storePurchaseBusy||itemId!==storeProductId||!$('#store-product-modal [data-product-confirm]'))return;
    storePurchaseBusy=true;
    const modal=$('#store-product-modal');modal.querySelectorAll('button').forEach(button=>button.disabled=true);
    try{
      const result=await api('/api/store/buy',{method:'POST',body:JSON.stringify({itemId})});
      if(state.user){state.user.coins=result.coins;if(result.starsCount!==undefined)state.user.starsCount=result.starsCount;setUser(state.user);}
      await loadStore();refreshOwnProfile();
      toast('تم الشراء وإضافة العنصر إلى مقتنياتك');storePurchaseBusy=false;renderStoreProduct(false);
    }catch(err){storePurchaseBusy=false;modal.querySelectorAll('button').forEach(button=>button.disabled=false);const error=$('.store-product-error',modal);error.hidden=false;error.textContent=err.message||'تعذر إتمام الشراء. حاول مجددًا.';}
  }
  async function equipStoreItem(itemId,button){
    try{
      button.disabled=true;
      const result=await api('/api/store/equip',{method:'POST',body:JSON.stringify({itemId})});
      if(state.store){state.store.equipped=result.equipped;renderStore();}
      ++ownProfileRequest;
      if(state.user&&result.equipped?.name_badge){
        state.user.nameBadge=result.equipped.name_badge;
        const bItem=(state.store?.catalog||[]).find(x=>x.id===result.equipped.name_badge);
        if(bItem){state.user.nameBadgeAsset=bItem.asset;state.user.nameBadgeName=bItem.name;}
      }
      if(state.user){state.user.profileBanner=result.equipped?.profile_banner||'';state.user.chatBubble=result.equipped?.chat_bubble||'';setUser(state.user);}
      toast('تم تفعيل العنصر بنجاح');
    }
    catch(err){button.disabled=false;toast(err.message||'تعذر تجهيز العنصر',true);}
  }
  function syncBottomNavigation(){
    const nav=$('.bottom-nav');if(nav)nav.hidden=!!state.activeCommunity;
    const back=$('#mobile-menu');if(back){
      back.setAttribute('aria-label',state.activeCommunity?'العودة للروم':'المساحات');
      back.innerHTML='<svg viewBox="0 0 24 24" width="24" height="24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'+(state.activeCommunity?'<path d="m9 5 7 7-7 7"/>':'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c5 5 5 13 0 18-5-5-5-13 0-18Z"/>')+'</svg>';
    }
  }
  function navigate(page){
    if(!page)return;
    if(page!=='profile')closeProfileEditor();
    state.page=page;
    syncBottomNavigation();
    document.body.classList.toggle('community-mode',page==='lobby'&&!!state.activeCommunity);
    $$('.page').forEach(p=>p.classList.toggle('active',p.id===`page-${page}`));
    $$('.nav-btn,.bottom-btn').forEach(b=>b.classList.toggle('active',b.dataset.page===page));
    if(page==='lobby'){
      if(state.activeCommunity)loadCommunityState(); else loadCommunities();
    }
    if(page==='friends')loadFriends();
    if(page==='profile')refreshOwnProfile();
    if(page==='store')loadStore();
    if(page==='admin')loadAdmin();
  }
  function startPolling(){
    clearInterval(state.poll);
    loadCommunities();
    state.poll=setInterval(()=>{
      if(state.page==='lobby'){
        if(state.activeCommunity)loadCommunityState(); else loadCommunities();
      }
      api('/api/heartbeat',{method:'POST',body:'{}'}).catch(()=>{});
      if(state.page==='friends')loadFriends();
    },3000);
  }
  async function loadCommunities(manual=false){
    try{
      const d=await api('/api/communities');const notices=$('#system-notifications');if(notices){notices.replaceChildren();for(const n of d.notifications||[]){const card=document.createElement('section');card.className='panel';card.style.padding='16px';const title=document.createElement('strong');title.textContent=n.sender+' · هدية الإشراف';const text=document.createElement('p');text.textContent=n.text;card.append(title,text);notices.append(card);}}state.communities=d.communities||[];renderCommunities();
      if(manual)toast('تم تحديث المساحات');
    }catch(err){if(err.status===401)return showAuth();if(manual)toast(err.message,true);}
  }
  function renderCommunities(){
    const box=$('#community-grid');if(!box)return;
    if(!state.communities.length){box.innerHTML='<div class="empty">لا توجد مساحات متاحة الآن.</div>';return;}
    box.innerHTML=state.communities.map(c=>`<button class="community-card" type="button" data-community="${escapeHtml(c.id)}" style="--community-accent:${escapeHtml(c.accent||'#d5a34c')}"><div class="community-card-copy"><small class="eyebrow">مساحة اجتماعية</small><h3>${escapeHtml(c.name)}</h3><p>${escapeHtml(c.description||'')}</p></div><span class="community-card-mark">${escapeHtml(c.mark||initials(c.name))}</span><div class="community-card-meta"><span><b>${Number(c.onlineCount)||0}</b> متصل</span><span><b>${Number(c.gameRoomCount)||0}</b> مباراة</span><span class="community-card-enter">دخول ‹</span></div></button>`).join('');
    $$('.community-card',box).forEach(card=>card.onclick=()=>enterCommunity(card.dataset.community));
  }
  function communityLocationId(){
    try{return new URLSearchParams(location.search).get('community')||sessionStorage.getItem('samidev_return_community')||'';}catch(_){return '';}
  }
  function syncCommunityLocation(id){
    try{
      const u=new URL(location.href);
      if(id){u.searchParams.set('community',id);sessionStorage.setItem('samidev_return_community',id);}else{u.searchParams.delete('community');sessionStorage.removeItem('samidev_return_community');}
      history.replaceState(null,'',u.pathname+(u.search?u.search:''));
    }catch(_){}
  }
  async function restoreCommunityFromLocation(){
    const id=communityLocationId();if(!id)return;
    try{await enterCommunity(id,{syncUrl:false});}catch(_){}
  }
  async function enterCommunity(id,{syncUrl=true}={}){
    try{
      await api(`/api/communities/${encodeURIComponent(id)}/enter`,{method:'POST',body:'{}'});
      const found=state.communities.find(c=>c.id===id)||{id};state.activeCommunity=found;syncBottomNavigation();
      $('#community-home').classList.add('hidden');$('#community-room').classList.remove('hidden');document.body.classList.add('community-mode');
      if(syncUrl)syncCommunityLocation(id);else{try{sessionStorage.setItem('samidev_return_community',id);}catch(_){}}
      await loadCommunityState();
    }catch(err){toast(err.message||'تعذر دخول المساحة',true);throw err;}
  }
  async function leaveCommunity(){
    closeCommunityProfile();
    const cid=state.activeCommunity?.id||null;
    if(cid){
      try{await api(`/api/communities/${encodeURIComponent(cid)}/leave`,{method:'POST',body:'{}'});}
      catch(err){if(err?.status===401)return showAuth();toast(err?.message||'تعذر تسجيل الخروج من الروم، تم إرجاعك للمساحات',true);}
    }
    state.activeCommunity=null;state.rooms=[];state.communityMembers=[];state.communityMessages=[];syncBottomNavigation();
    $('#community-room').classList.add('hidden');$('#community-home').classList.remove('hidden');document.body.classList.remove('community-mode');
    syncCommunityLocation('');loadCommunities();
  }
  async function loadCommunityState(manual=false){
    const active=state.activeCommunity;if(!active)return loadCommunities(manual);
    try{
      const d=await api(`/api/communities/${encodeURIComponent(active.id)}`);
      state.communityCapabilities=d.capabilities||{};state.activeCommunity=d.community||active;state.rooms=d.rooms||[];state.communityMembers=d.members||[];state.communityMessages=d.messages||[];
      renderCommunityState();renderRooms();
      if(manual)toast('تم تحديث المساحة');
    }catch(err){if(err.status===401)return showAuth();if(err.status===404||['COMMUNITY_BANNED','COMMUNITY_KICKED'].includes(err.code)){toast(err.message,true);leaveCommunity();return;}if(manual)toast(err.message,true);}
  }
  function visibleCommunityMembers(){
    const selfId=String(state.user?.id||'');
    return (state.communityMembers||[]).filter(u=>String(u?.id||'')!==selfId);
  }
  function renderCommunityState(){
    const c=state.activeCommunity;if(!c)return;
    const room=$('#community-room');room.style.setProperty('--community-accent',c.accent||'#d5a34c');
    $('#active-community-name').textContent=c.name||'المساحة';$('#active-community-description').textContent=(c.description||'')+(state.communityCapabilities?.canModerate?' · لديك صلاحية إدارة المساحة: افتح ملف عضو للكتم أو الحظر أو الإخراج.':'');$('#active-community-mark').textContent=c.mark||initials(c.name);$('#active-community-mark').style.setProperty('--community-accent',c.accent||'#d5a34c');
    $('#community-chat-title').textContent=`شات ${c.name||'المساحة'}`;$('#community-member-count').textContent=String(visibleCommunityMembers().length);
    renderCommunityMembers();renderCommunityMessages();
  }
  function avatarMarkup(user,cls,clickable=false){
    const name=user.displayName||user.username||'Player';const id=String(user.id||'');
    const data=clickable&&id?` data-public-profile="${escapeHtml(id)}" tabindex="0" role="button" aria-label="فتح ملف ${escapeHtml(name)}"`:'';
    const src=id?`/api/avatar/${encodeURIComponent(id)}`:DEFAULT_AVATAR_URL;
    return `<span class="${cls}"${data}><img data-avatar-fallback="1" src="${src}" alt="صورة ${escapeHtml(name)}"></span>`;
  }
  function avatarNode(user,cls,clickable=false){
    const name=String(user?.displayName||user?.username||'Player'),id=String(user?.id||user?.userId||'');
    const wrap=document.createElement('span');wrap.className=cls;
    if(clickable&&id){wrap.dataset.publicProfile=id;wrap.tabIndex=0;wrap.setAttribute('role','button');wrap.setAttribute('aria-label',`فتح ملف ${name}`);}
    const img=document.createElement('img');img.dataset.avatarFallback='1';img.alt=`صورة ${name}`;img.src=id?`/api/avatar/${encodeURIComponent(id)}`:DEFAULT_AVATAR_URL;wrap.append(img);wireAvatarImage(img);return wrap;
  }
  function profileSprite(className){const span=document.createElement('span');span.className=`profile-sprite ${className}`;span.setAttribute('aria-hidden','true');return span;}
  function communityStarsMarkup(){return Array.from({length:5},()=>'<span class="profile-sprite profile-sprite-star community-member-star" aria-hidden="true"></span>').join('');}
  function emptyBlock(text){const el=document.createElement('div');el.className='empty small';el.textContent=text;return el;}
  // Keep unchanged DOM nodes mounted: image requests and scroll position stay stable.
  const stableLists=new WeakMap();
  function stableList(box){const previous=stableLists.get(box)||new Map(),next=new Map(),nodes=[];return {
    reuse(key,value){const signature=JSON.stringify(value),old=previous.get(key);if(old?.signature===signature){next.set(key,old);nodes.push(old.node);return true;}this.key=key;this.signature=signature;return false;},
    add(node){next.set(this.key,{signature:this.signature,node});nodes.push(node);},
    finish(){const keep=new Set(nodes);for(const child of [...box.children])if(!keep.has(child))child.remove();nodes.forEach((node,i)=>{if(box.children[i]!==node)box.insertBefore(node,box.children[i]||null);});stableLists.set(box,next);}
  };}
  function renderCommunityMembers(){
    const box=$('#community-members');if(!box)return;
    const members=visibleCommunityMembers(),update=stableList(box);
    if(!members.length){if(!update.reuse('empty',null))update.add(emptyBlock('لا يوجد أعضاء آخرون متصلون الآن.'));update.finish();return;}
    for(const u of members){
      if(update.reuse(String(u.id),[u.id,u.displayName,u.username,u.nameBadgeAsset,u.nameBadgeName,u.starsCount,u.wins,u.reputation]))continue;
      const name=String(u.displayName||u.username||'Player');
      const row=document.createElement('div');row.className='community-member';row.dataset.publicProfile=String(u.id||'');row.tabIndex=0;row.setAttribute('role','button');row.setAttribute('aria-label',`فتح ملف ${name}`);
      row.append(avatarNode(u,'community-member-avatar'));
      const copy=document.createElement('div');copy.className='community-member-copy';
      const title=document.createElement('div');title.className='community-member-title';const strong=document.createElement('strong');strong.textContent=name;
      const emblem=profileSprite('profile-sprite-emblem community-member-emblem');
      const badgeAsset=u.nameBadgeAsset||'/platform/assets/profile/raster/palm-swords.webp';
      window.SamiDevStickerArt.render(emblem,badgeAsset,u.nameBadgeName||'ملصق الاسم');
      title.append(strong,emblem);
      const stars=document.createElement('div');stars.className='community-member-stars';
      const userStars=Math.max(0,Math.min(5,Number(u.starsCount??0)));
      stars.setAttribute('aria-label',`${userStars} نجوم`);
      for(let i=0;i<5;i++){
        const star=profileSprite('profile-sprite-star community-member-star');
        star.hidden=i>=userStars;
        stars.append(star);
      }
      const meta=document.createElement('div');meta.className='community-member-meta';
      for(const text of [`${String(u.username||'player')}`,`فوز ${formatProfileStat(u.wins)}`,`سمعة ${formatProfileStat(u.reputation)}`]){const span=document.createElement('span');span.textContent=text;meta.append(span);}
      copy.append(title,stars,meta);const online=document.createElement('span');online.className='community-member-online';online.setAttribute('aria-label','متصل الآن');row.append(copy,online);update.add(row);
    }update.finish();
  }
  function chatTime(ts){const d=new Date(Number(ts)||Date.now());return d.toLocaleTimeString('ar-SA',{hour:'2-digit',minute:'2-digit'});}
  function renderCommunityMessages(){
    const box=$('#community-chat-messages');if(!box)return;const wasNearBottom=box.scrollHeight-box.scrollTop-box.clientHeight<70,update=stableList(box);
    if(!state.communityMessages.length){if(!update.reuse('empty',null))update.add(emptyBlock('ابدأ أول محادثة هنا.'));update.finish();return;}
    for(const [index,m] of state.communityMessages.entries()){
      if(update.reuse(String(m.id||JSON.stringify([m.userId,m.createdAt,index])),[m,state.user?.id]))continue;
      const article=document.createElement('article');article.className='community-chat-message'+(m.userId&&String(m.userId)===String(state.user?.id)?' me':'');article.append(avatarNode({id:m.userId,displayName:m.displayName,username:m.username},'community-chat-avatar',true));
      const content=document.createElement('div');content.className='community-chat-content';const bubble=document.createElement('div');bubble.className='community-chat-bubble';const meta=document.createElement('div');meta.className='community-chat-meta';
      const name=document.createElement('strong');name.className='community-chat-profile-name';name.textContent=String(m.displayName||m.username||'Player');if(m.userId)name.dataset.publicProfile=String(m.userId);
      const time=document.createElement('time');time.textContent=chatTime(m.createdAt);const text=document.createElement('p');text.textContent=String(m.text||'');meta.append(name,time);bubble.append(text);window.SamiDevCosmetics?.bubble(bubble,m.chatBubble);content.append(meta,bubble);article.append(content);update.add(article);
    }update.finish();
    if(wasNearBottom||!box.dataset.loaded){box.scrollTop=box.scrollHeight;box.dataset.loaded='1';}
  }
  function closeCommunityProfile(){
    if(window.__sdNativePublicProfile){window.__sdNativePublicProfile=false;window.SamiDevMobile?.postMessage(JSON.stringify({type:'native_home'}));}
    const modal=$('#community-profile-modal');if(!modal)return;
    modal.classList.remove('open','sd-profile-expanded');modal.setAttribute('aria-hidden','true');activePublicProfile=null;
    $('#community-profile-report-box')?.classList.add('hidden');if($('#community-profile-report-text'))$('#community-profile-report-text').value='';
  }
  function communityRelationLabel(user){
    if(user.relation==='friend')return 'صديق';
    if(user.relation==='outgoing')return 'تم إرسال الطلب';
    if(user.relation==='incoming')return 'قبول الصداقة';
    if(user.relation==='self')return 'ملفك الشخصي';
    return 'إضافة صديق';
  }
  function renderCommunityPublicProfile(user){
    let moderation=$('#community-profile-moderation');
    if(!moderation){moderation=document.createElement('div');moderation.id='community-profile-moderation';moderation.className='community-public-actions';$('#community-profile-actions').insertAdjacentElement('afterend',moderation);}
    moderation.replaceChildren();
    if(user.id!==state.user?.id&&state.activeCommunity&&state.communityCapabilities?.canModerate){
      const options={kick:'إخراج لمدة دقيقة',mute:'كتم ١٠ دقائق',unmute:'إلغاء الكتم',ban:'حظر من المساحة',unban:'فك حظر المساحة'};
      if(state.communityCapabilities.canAssignModerators){options.grant_moderator='تعيين مشرف لهذه المساحة';options.revoke_moderator='سحب إشراف هذه المساحة';}
      for(const [action,title] of Object.entries(options)){
        const button=document.createElement('button');button.type='button';button.className='ghost';button.textContent=title;
        button.onclick=async()=>{
          if(!confirm(title+' للمستخدم '+(user.displayName||user.username)+'؟'))return;
          button.disabled=true;
          try{await api('/api/communities/'+encodeURIComponent(state.activeCommunity.id)+'/moderation',{method:'POST',body:JSON.stringify({targetUserId:user.id,action})});toast('تم تنفيذ الإجراء في هذه المساحة');await loadCommunityState();}
          catch(error){toast(error.message,true);}finally{button.disabled=false;}
        };moderation.append(button);
      }
    }

    const keepFull=$('#community-profile-modal').classList.contains('sd-profile-expanded');
    activePublicProfile=user;window.SamiDevCosmetics?.cover($('#community-profile-modal .profile-cover'),user.profileBanner);
    const name=user.displayName||user.username||'Player';
    $('#community-profile-name').textContent=name;
    const badgeAsset=user.nameBadgeAsset||'/platform/assets/profile/raster/palm-swords.webp';
    const badgeName=user.nameBadgeName||'سيفين ونخلة';
    const modalBadge=$('#community-profile-modal .profile-sticker');
    if(modalBadge){window.SamiDevStickerArt.render(modalBadge,badgeAsset,badgeName);modalBadge.setAttribute('aria-label',badgeName);modalBadge.setAttribute('title',badgeName);}
    const userStars=Math.max(0,Math.min(5,Number(user.starsCount??0)));
    $('#community-profile-modal .profile-stars')?.setAttribute('aria-label',`${userStars} نجوم زينة مملوكة`);
    $$('#community-profile-modal .community-public-profile-star').forEach((el,i)=>{el.hidden=i>=userStars;el.classList.remove('dim');});
    $('#community-profile-handle').textContent=String(user.username||'player');
    $('#community-profile-since').textContent=playerSinceValue(user.accountAgeDays,user.createdAt);
    $('#community-profile-wins').textContent=formatProfileStat(user.wins);
    $('#community-profile-reputation').textContent=formatProfileStat(user.reputation);
    const img=$('#community-profile-avatar-image'),fallback=$('#community-profile-avatar-fallback');fallback.textContent=initials(name);
    wireAvatarImage(img,fallback);img.src=user.id?'/api/avatar/'+encodeURIComponent(user.id)+'?v='+Date.now():DEFAULT_AVATAR_URL;
    const self=user.relation==='self'||String(user.id)===String(state.user?.id);
    const friend=$('#community-profile-friend');friend.querySelector('span:last-child').textContent=communityRelationLabel(user);friend.disabled=self||['friend','outgoing'].includes(user.relation);
    const remaining=Math.max(0,Number(user.reputationDailyRemaining??5)||0);const rep=$('#community-profile-reputation-btn');rep.disabled=self||!!user.reputationGrantedToday||remaining<=0;rep.querySelector('span:nth-child(2)').textContent=user.reputationGrantedToday?'مُنحت اليوم':'منح سمعة';$('#community-profile-reputation-left').textContent=`${remaining}/5 اليوم`;
    $('#community-profile-report').disabled=self;$('#community-profile-actions').classList.toggle('self',self);
    let extra=$('#sd-public-extra');
    if(!extra){extra=document.createElement('section');extra.id='sd-public-extra';extra.className='sd-public-extra';$('#community-profile-actions').insertAdjacentElement('afterend',extra);}
    window.SamiDevProfileDetails?.render(extra,user,{own:self});
    renderFeaturedRank($('#community-profile-featured'),user);
    setPublicProfileFull(keepFull);
    $('#community-profile-loading').classList.add('hidden');
  }
  function renderFeaturedRank(root,user){
    if(!root)return;root.replaceChildren();
    const rows=(user.gameStatistics||[]).filter(s=>Number(s.played)>0).sort((a,b)=>Number(b.wins)-Number(a.wins));
    const best=rows[0];root.hidden=!best;if(!best)return;
    const mark={pool:'pool',carrom:'carrom',tablesoccer:'football',crazy8:'cards'}[best.gameId];
    const names={pool:'البلياردو',carrom:'الكيرم',tablesoccer:'كرة الطاولة',crazy8:'أونو'};
    const img=document.createElement('img');img.src='/room-sprites/'+mark+'.png';img.alt='';
    const info=document.createElement('div'),name=document.createElement('strong'),rank=document.createElement('small');
    name.textContent=names[best.gameId]||'اللعبة';rank.textContent=`${best.rankName} · المستوى ${formatProfileStat(best.level)}`;
    info.append(name,rank);root.append(img,info);
  }
  function setPublicProfileFull(full){
    const modal=$('#community-profile-modal');modal.classList.toggle('sd-profile-expanded',full);
    const extra=$('#sd-public-extra');if(extra)extra.hidden=!full;
    $('#community-profile-full').textContent=full?'العودة إلى البطاقة المختصرة':'الملف الكامل والمقتنيات والإحصاءات';
    const close=$('#community-profile-close');close.textContent=full?'‹':'×';close.setAttribute('aria-label',full?'العودة إلى البطاقة المختصرة':'إغلاق');
    const title=$('#community-profile-modal .profile-card-bar strong');if(title)title.textContent=full?'الملف الشخصي':'بطاقة اللاعب';
  }
  async function openCommunityProfile(userId){
    userId=String(userId||'').trim();if(!userId)return;
    const modal=$('#community-profile-modal');modal.classList.add('open');modal.setAttribute('aria-hidden','false');$('#community-profile-loading').classList.remove('hidden');
    try{const d=await api('/api/public-profile/'+encodeURIComponent(userId));renderCommunityPublicProfile(d.user);}
    catch(err){toast(err.message||'تعذر تحميل الملف',true);closeCommunityProfile();}
  }
  async function communityProfileFriendAction(){
    const u=activePublicProfile;if(!u||u.relation==='self')return;
    const btn=$('#community-profile-friend');btn.disabled=true;
    try{
      if(u.relation==='incoming'){await api('/api/friends/respond',{method:'POST',body:JSON.stringify({userId:u.id,accept:true})});u.relation='friend';toast('تمت إضافة الصديق');}
      else{await api('/api/friends/request',{method:'POST',body:JSON.stringify({username:u.username})});u.relation='outgoing';toast('تم إرسال طلب الصداقة');}
      renderCommunityPublicProfile(u);loadFriends();
    }catch(err){btn.disabled=false;toast(err.message||'تعذر تنفيذ طلب الصداقة',true);}
  }
  async function communityProfileReputationAction(){
    const u=activePublicProfile;if(!u)return;const btn=$('#community-profile-reputation-btn');btn.disabled=true;
    try{const d=await api(`/api/users/${encodeURIComponent(u.id)}/reputation`,{method:'POST',body:JSON.stringify({source:'profile'})});u.reputation=d.reputation;u.reputationDailyRemaining=d.remaining;u.reputationGrantedToday=true;renderCommunityPublicProfile(u);toast('تم منح السمعة');}
    catch(err){btn.disabled=false;toast(err.message||'تعذر منح السمعة',true);}
  }
  async function communityProfileReportAction(){
    const u=activePublicProfile;if(!u)return;const text=String($('#community-profile-report-text').value||'').trim();const btn=$('#community-profile-report-send');btn.disabled=true;
    try{await api(`/api/users/${encodeURIComponent(u.id)}/report`,{method:'POST',body:JSON.stringify({message:text,roomId:'community:'+String(state.activeCommunity?.id||'')})});$('#community-profile-report-box').classList.add('hidden');$('#community-profile-report-text').value='';toast('تم إرسال البلاغ للإدارة');}
    catch(err){toast(err.message||'تعذر إرسال البلاغ',true);}finally{btn.disabled=false;}
  }

  async function sendCommunityChat(event){
    event?.preventDefault?.();const c=state.activeCommunity,input=$('#community-chat-input');if(!c||!input)return;
    const text=input.value.trim();if(!text)return;
    input.disabled=true;
    try{await api(`/api/communities/${encodeURIComponent(c.id)}/chat`,{method:'POST',body:JSON.stringify({text})});input.value='';await loadCommunityState();}
    catch(err){toast(err.message||'تعذر إرسال الرسالة',true);}finally{input.disabled=false;input.focus();}
  }
  async function loadRooms(manual=false){return state.activeCommunity?loadCommunityState(manual):loadCommunities(manual);}
  function roomKind(r){if(r.settings?.gameId==='crazy8')return Number(r.settings.seats)===4?'2v2':`${Number(r.capacity)||4}P`;return Number(r.capacity)===4?'2v2':'1v1';}
  function roomSeatsMarkup(r){
    const cap=Math.max(2,Number(r.capacity)||2),roster=Array.isArray(r.roster)?r.roster:[];
    const bySeat=new Map(roster.map(p=>[Number(p.seat),p]));
    return Array.from({length:cap},(_,seat)=>{
      const p=bySeat.get(seat),name=String(p?.name||'').trim();
      if(name){
        const accountId=String(p?.accountId||'');const src=accountId?`/api/avatar/${encodeURIComponent(accountId)}`:DEFAULT_AVATAR_URL;
        return `<span class="room-player-slot occupied" title="${escapeHtml(name)}"><img data-avatar-fallback="1" src="${src}" alt="${escapeHtml(name)}">${seat===0?'<i class="room-host-crown" aria-label="المنشئ"></i>':''}</span>`;
      }
      return '<span class="room-player-slot empty-seat" aria-label="مقعد فارغ"><span></span></span>';
    }).join('');
  }
  function renderRooms(){
    const rooms=state.rooms;
    const box=$('#rooms');const signature=JSON.stringify([state.activeCommunity?.id,rooms]);if(box.dataset.renderSignature===signature)return;box.dataset.renderSignature=signature;const update=stableList(box);if(!rooms.length){if(!update.reuse('empty',null))update.add(emptyBlock('لا توجد مباريات في هذه المساحة بعد. أنشئ أول مباراة.'));update.finish();return;}
    rooms.forEach(r=>{
      if(update.reuse(String(r.roomId),r))return;
      const open=!r.started&&Number(r.occupied)<Number(r.capacity);
      const watching=!!r.begun&&!r.finished;
      const preparing=!!r.started&&!r.begun;
      const stg=r.settings||{},modeName=escapeHtml(window.SamiDevGames.label(stg)),rid=escapeHtml(r.roomId),host=escapeHtml(r.hostName||'Player');
      const st=open
        ? '<span class="status-chip status-wait">متاحة</span>'
        : watching
          ? '<span class="status-chip status-live">جارية</span>'
          : '<span class="status-chip status-play">تجهيز</span>';
      const action=open
        ? `<button class="primary join-room" data-room="${rid}">انضم</button>`
        : watching
          ? `<button class="secondary watch-room" data-room="${rid}">مشاهدة</button>`
          : '<button class="secondary room-waiting" disabled>تجهيز</button>';
      const template=document.createElement('template');template.innerHTML=`<article class="room-card community-room-card">
        <div class="room-mobile-top"><div class="room-code">${rid}</div>${st}</div>
        <div class="room-game-identity">
          <span class="room-game-mark"><img src="/room-sprites/${({pool:"pool",carrom:"carrom",crazy8:"cards",tablesoccer:"football"})[stg.gameId]||"carrom"}.png?v=36" alt="${modeName}" width="58" height="58"></span>
          <div><small>غرفة ${rid}</small><strong>${modeName}</strong><p>المنشئ: ${host}</p></div>
        </div>
        <div class="room-roster" aria-label="اللاعبون">${roomSeatsMarkup(r)}</div>
        <div class="room-desktop-state"><strong>${Number(r.occupied)||0}/${Number(r.capacity)||0}</strong><small>لاعبون</small>${st}</div>
        <div class="room-mobile-meta room-meta"><div><b>${roomKind(r)}</b><small>النوع</small></div><div><b>${r.occupied}/${r.capacity}</b><small>اللاعبون</small></div><div><b>${modeName}</b><small>النمط</small></div></div>
        <div class="room-mobile-host room-host">المنشئ: ${host}</div>
        ${action}
      </article>`;update.add(template.content.firstElementChild);
    });update.finish();
    wireAvatarImages(box);
    $$('.join-room',box).forEach(b=>b.onclick=()=>joinRoom(b.dataset.room));
    $$('.watch-room',box).forEach(b=>b.onclick=()=>watchRoom(b.dataset.room));
  }

  async function handlePendingInvite(){
    const q=new URLSearchParams(location.search); const invite=q.get('invite');
    if(!invite) return;
    if(!/^[A-Za-z0-9_-]{20,64}$/.test(invite)){ history.replaceState(null,'','/platform/'); return; }
    try{
      const t=await ticket();
      const game=new URLSearchParams({online:'1',action:'invite',invite,ticket:t});
      location.href=window.SamiDevGames.get(q.get('game')).entry+'?'+game;
    }catch(err){ toast(err.message,true); }
  }
  async function ticket(communityId=null){const body=communityId?{communityId}:{};const d=await api('/api/game-ticket',{method:'POST',body:JSON.stringify(body)});return d.ticket;}
  async function joinRoom(room){try{const cid=state.activeCommunity?.id||null;if(cid)try{sessionStorage.setItem('samidev_return_community',cid);}catch(_){}const t=await ticket(cid);const q=new URLSearchParams({online:'1',action:'join',room,ticket:t});if(cid)q.set('community',cid);location.href=window.SamiDevGames.get(state.rooms.find(r=>r.roomId===room)?.settings?.gameId).entry+'?'+q;}catch(err){toast(err.message,true);}}
  async function watchRoom(room){try{const cid=state.activeCommunity?.id||null;if(cid)try{sessionStorage.setItem('samidev_return_community',cid);}catch(_){}const t=await ticket(cid);const q=new URLSearchParams({online:'1',action:'watch',room,ticket:t});if(cid)q.set('community',cid);location.href=window.SamiDevGames.get(state.rooms.find(r=>r.roomId===room)?.settings?.gameId).entry+'?'+q;}catch(err){toast(err.message,true);}}
  async function createRoom(){try{const cid=state.activeCommunity?.id;if(!cid)return toast('اختر مساحة أولًا',true);try{sessionStorage.setItem('samidev_return_community',cid);}catch(_){}const t=await ticket(cid);const gid=$('#create-game').value;const q=new URLSearchParams({online:'1',action:'create',ticket:t,community:cid,players:state.settings.players,game:gid});if(gid==='pool'){q.set('gameType',$('#create-pool-mode').value);q.set('live','1');}else if(gid==='crazy8'){q.delete('players');q.set('seats',$('#create-card-seats').value);q.set('special',$('#create-card-special').value);q.set('live',$('#create-card-live').value);}else if(gid==='tablesoccer'){q.set('live',$('#create-soccer-mode').value);q.set('goalsToWin',$('#create-goals').value);q.set('passes',$('#create-passes').value);}else{q.set('gamemode',$('#create-gamemode').value);q.set('live',state.settings.live);q.set('break',$('#create-break').value);}location.href=window.SamiDevGames.get(gid).entry+'?'+q;}catch(err){toast(err.message,true);}}
  async function loadFriends(){try{const d=await api('/api/friends');state.friends=d.friends||[];state.requests=d.requests||[];renderFriends();}catch(err){if(err.status===401)showAuth();}}
  function personRow(u,actions=''){return `<div class="person"><span class="presence ${u.online?'online':''}"></span><div class="person-info"><strong>${escapeHtml(u.displayName||u.username)}</strong><small>${escapeHtml(u.username)}${u.online?' · متصل':''}</small></div><div class="person-actions">${actions}</div></div>`;}
  function renderFriends(){
    const req=$('#friend-requests');req.innerHTML=state.requests.length?state.requests.map(u=>personRow(u,`<button class="small-btn accept" data-id="${u.id}">قبول</button><button class="danger-btn reject" data-id="${u.id}">رفض</button>`)).join(''):'<div class="empty small">لا توجد طلبات</div>';
    $('#request-badge').textContent=state.requests.length;$('#request-badge').classList.toggle('hidden',!state.requests.length);
    $$('.accept',req).forEach(b=>b.onclick=()=>respondFriend(b.dataset.id,true));$$('.reject',req).forEach(b=>b.onclick=()=>respondFriend(b.dataset.id,false));
    const list=$('#friends-list');list.innerHTML=state.friends.length?state.friends.map(u=>personRow(u,`<button class="danger-btn remove-friend" data-id="${u.id}">إزالة</button>`)).join(''):'<div class="empty small">لا يوجد أصدقاء حتى الآن</div>';
    $$('.remove-friend',list).forEach(b=>b.onclick=()=>removeFriend(b.dataset.id));
  }
  async function respondFriend(id,accept){try{await api('/api/friends/respond',{method:'POST',body:JSON.stringify({userId:id,accept})});loadFriends();}catch(err){toast(err.message,true);}}
  async function removeFriend(id){try{await api('/api/friends/'+encodeURIComponent(id),{method:'DELETE'});loadFriends();}catch(err){toast(err.message,true);}}
  async function searchUsers(){const q=$('#user-search').value.trim();if(q.length<2)return toast('اكتب حرفين على الأقل',true);try{const d=await api('/api/users/search?q='+encodeURIComponent(q));const box=$('#search-results');box.innerHTML=d.users.length?d.users.map(u=>personRow(u,u.relation==='friend'?'<span class="role-chip">صديق</span>':`<button class="small-btn add-user" data-username="${escapeHtml(u.username)}">إضافة</button>`)).join(''):'<div class="empty small">لا توجد نتائج</div>';$$('.add-user',box).forEach(b=>b.onclick=async()=>{try{await api('/api/friends/request',{method:'POST',body:JSON.stringify({username:b.dataset.username})});toast('تم إرسال الطلب');loadFriends();searchUsers();}catch(err){toast(err.message,true);}});}catch(err){toast(err.message,true);}}
  function reportTime(ts){
    const d=new Date(Number(ts)||0);
    if(!Number.isFinite(d.getTime()))return '—';
    return d.toLocaleString('ar-SA',{dateStyle:'short',timeStyle:'short'});
  }
  async function loadAdmin(){
    if(!state.user||state.user.role!=='admin')return;
    try{
      const [s,u,r,spaces]=await Promise.all([api('/api/admin/stats'),api('/api/admin/users'),api('/api/admin/reports'),api('/api/communities')]);
      const communityOptions=(spaces.communities||[]).map(c=>`<option value="${escapeHtml(c.id)}">${escapeHtml(c.name)}</option>`).join('');
      const communityNames=new Map((spaces.communities||[]).map(c=>[c.id,c.name]));
      const st=s.stats;
      $('#admin-stats').innerHTML=`<div><span>${st.users}</span><small>المستخدمون</small></div><div><span>${st.onlineUsers}</span><small>متصلون</small></div><div><span>${st.waitingRooms}</span><small>غرف انتظار</small></div><div><span>${st.runningRooms}</span><small>مباريات جارية</small></div>`;
      $('#admin-users').innerHTML=u.users.map(x=>`<tr><td><strong>${escapeHtml(x.displayName)}</strong><br><small>${escapeHtml(x.username)}</small></td><td>${x.online?'متصل':'غير متصل'}</td><td><select class="role-select" data-id="${x.id}" ${state.user.role!=='admin'||x.id===state.user.id?'disabled':''}><option value="user" ${x.role==='user'?'selected':''}>عضو</option>${x.role==='moderator'?'<option value="moderator" selected disabled>رتبة قديمة — عيّن المساحة أدناه</option>':''}<option value="admin" ${x.role==='admin'?'selected':''}>مدير المنصة</option></select>${x.id!==state.user.id?`<div class="admin-community-controls" data-user-id="${escapeHtml(x.id)}"><small>إشرافه: ${escapeHtml((x.moderatedCommunities||[]).map(cid=>communityNames.get(cid)||cid).join('، ')||'لا توجد مساحات')}</small><select aria-label="مساحة الإشراف">${communityOptions}</select><button class="small-btn scoped-moderation" data-action="grant_moderator">تعيين مشرف مساحة</button><button class="small-btn scoped-moderation" data-action="revoke_moderator">سحب إشراف المساحة</button></div>`:''}</td><td>${x.banned?'محظور':'—'}</td><td><button class="${x.banned?'small-btn':'danger-btn'} ban-user" data-id="${x.id}" data-ban="${x.banned?'0':'1'}" ${x.id===state.user.id?'disabled':''}>${x.banned?'فك الحظر':'حظر'}</button></td></tr>`).join('');
      $$('.ban-user').forEach(b=>b.onclick=()=>adminBan(b.dataset.id,b.dataset.ban==='1'));
      $$('.role-select').forEach(s=>s.onchange=()=>adminRole(s.dataset.id,s.value));
      $$('.scoped-moderation').forEach(button=>button.onclick=async()=>{
        const controls=button.closest('.admin-community-controls'),select=controls.querySelector('select'),cid=select.value;
        if(!cid)return toast('اختر المساحة أولًا',true);
        if(!confirm(button.textContent+' في '+select.selectedOptions[0].textContent+'؟'))return;
        button.disabled=true;
        try{await api('/api/communities/'+encodeURIComponent(cid)+'/moderation',{method:'POST',body:JSON.stringify({targetUserId:controls.dataset.userId,action:button.dataset.action})});toast(button.dataset.action==='grant_moderator'?'تم تعيين مشرف المساحة؛ أدواته داخل ملفات الأعضاء':'تم سحب إشراف المساحة');await loadAdmin();}catch(error){toast(error.message,true);button.disabled=false;}
      });
      const reports=Array.isArray(r.reports)?r.reports:[];
      const count=$('#admin-reports-count');if(count)count.textContent=String(reports.length);
      const box=$('#admin-reports');
      if(box)box.innerHTML=reports.length?reports.map(x=>`<article class="admin-report"><div class="admin-report-head"><strong>${escapeHtml(x.targetName||'Player')}</strong><span>${reportTime(x.createdAt)}</span></div><div class="admin-report-meta">من ${escapeHtml(x.reporterName||'Player')}${x.roomId?` • غرفة ${escapeHtml(x.roomId)}`:''}</div><p>${escapeHtml(x.message||'بدون وصف إضافي')}</p></article>`).join(''):'<div class="empty small">لا توجد بلاغات</div>';
    }catch(err){toast(err.message,true);}
  }
  async function adminBan(id,banned){try{await api(`/api/admin/users/${encodeURIComponent(id)}/ban`,{method:'POST',body:JSON.stringify({banned})});loadAdmin();}catch(err){toast(err.message,true);}}
  async function adminRole(id,role){try{await api(`/api/admin/users/${encodeURIComponent(id)}/role`,{method:'POST',body:JSON.stringify({role})});loadAdmin();}catch(err){toast(err.message,true);loadAdmin();}}
  window.SamiDevMobilePlatform={
    navigate(page){if(!['lobby','profile','friends','store','admin'].includes(page))return;navigate(page);},
    setNativeActive(active){clearInterval(state.poll);state.poll=null;if(!active&&state.user)startPolling();},
    setTheme(theme){applyTheme(theme);},
    closeProfile(){window.__sdNativePublicProfile=false;closeCommunityProfile();},
    openProfile(id){if(!/^[A-Za-z0-9_-]{1,64}$/.test(id))return;window.__sdNativePublicProfile=true;openCommunityProfile(id);},
  };
  boot();
})();
