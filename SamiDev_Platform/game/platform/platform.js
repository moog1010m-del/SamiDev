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
    window.SamiDevMobile?.postMessage(JSON.stringify({type:'platform_ready',role:user.role||'user'}));
    const name=user.displayName||user.username;
    $('#side-name').textContent=name; $('#side-username').textContent='@'+user.username;
    $('#profile-name').textContent=name;
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
    const communityUserName=$('#community-user-name');if(communityUserName)communityUserName.textContent=name;
    const communityUserHandle=$('#community-user-handle');if(communityUserHandle)communityUserHandle.textContent='@'+String(user.username||'player');
    const lobbyName=$('#lobby-profile-name');if(lobbyName)lobbyName.textContent=name;
    const lobbyHandle=$('#lobby-profile-handle');if(lobbyHandle)lobbyHandle.textContent='@'+String(user.username||'player');
    const lobbyAccount=$('#lobby-profile-account');if(lobbyAccount)lobbyAccount.textContent='@'+String(user.username||'player');
    const lobbySince=$('#lobby-profile-since');if(lobbySince)lobbySince.textContent=playerSinceValue(user.accountAgeDays,user.createdAt);
    const lobbyWins=$('#lobby-profile-wins');if(lobbyWins)lobbyWins.textContent=formatProfileStat(user.wins);
    const lobbyRep=$('#lobby-profile-reputation');if(lobbyRep)lobbyRep.textContent=formatProfileStat(user.reputation);
    const storeBalance=$('#store-balance');if(storeBalance&&user.coins!=null)storeBalance.textContent=formatProfileStat(user.coins);
    const badgeAsset=user.nameBadgeAsset||'/platform/assets/profile/raster/palm-swords.webp';
    const badgeName=user.nameBadgeName||'سيفين ونخلة';
    $$('.profile-name-row .profile-sticker').forEach(el=>{
      el.style.backgroundImage=`url('${badgeAsset}')`;
      el.setAttribute('aria-label',badgeName);
      el.setAttribute('title',badgeName);
    });
    const userStars=Math.max(0,Math.min(5,Number(user.starsCount??5)));
    $$('#page-profile .profile-stars .profile-sprite-star').forEach((el,i)=>{
      el.classList.toggle('dim',i>=userStars);
    });
    const admin=['admin','moderator'].includes(user.role); $('#admin-nav').classList.toggle('hidden',!admin); $('#admin-bottom').classList.toggle('hidden',!admin);
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
  function showAuth(){ state.store=null; document.body.classList.remove('community-mode'); $('#auth-screen').classList.remove('hidden'); $('#app').classList.add('hidden'); clearInterval(state.poll); }
  function showApp(){ $('#auth-screen').classList.add('hidden'); $('#app').classList.remove('hidden'); navigate('lobby'); startPolling(); loadFriends(); handlePendingInvite(); restoreCommunityFromLocation(); }

  async function boot(){
    applyTheme(preferredTheme(),{persist:false});
    bind();
    try{const d=await api('/api/me');setUser(d.user);showApp();}catch(_){showAuth();}
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
    $$('.board-players-setting').forEach(x=>x.classList.toggle('hidden',cards||pool));
    $('#create-game-description').textContent=pool?'بلياردو 8 كرات، تصويب وقوة ودوران.':cards?'طابق اللون أو الرقم وتخلّص من أوراقك أولًا.':soccer?'فريقان، تسديدات وتمريرات وأهداف.':'الكيرم الكلاسيكي وأنماط النقاط.';
    $('#create-go').textContent=pool?'إنشاء مباراة بلياردو':cards?'إنشاء مباراة كريزي 8':soccer?'إنشاء مباراة كرة الطاولة':'إنشاء مباراة الكيرم';
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
    $('#logout-btn').onclick=async()=>{try{await api('/api/auth/logout',{method:'POST',body:'{}'});}catch(err){toast(err.message,true);return;}try{sessionStorage.removeItem('samidev_reconnect');sessionStorage.removeItem('samidev_return_community');}catch(_){}showAuth();};
    $$('.nav-btn,.bottom-btn,[data-page]').forEach(b=>b.addEventListener('click',()=>navigate(b.dataset.page)));
    $$('.theme-toggle').forEach(b=>b.addEventListener('click',toggleTheme));
    $('#community-self-profile').onclick=()=>navigate('profile');
    $('#community-profile-page').onclick=()=>navigate('profile');
    $('#community-profile-edit').onclick=()=>{navigate('profile');requestAnimationFrame(openProfileEditor);};
    $('#refresh-communities').onclick=()=>loadCommunities(true);
    $('#refresh-rooms').onclick=()=>loadCommunityState(true);
    $('#leave-community').onclick=leaveCommunity;
    const exitCommunity=$('#exit-community');if(exitCommunity)exitCommunity.onclick=leaveCommunity;
    $('#community-profile-close').onclick=closeCommunityProfile;
    $('#community-profile-modal').addEventListener('click',e=>{if(e.target.id==='community-profile-modal')closeCommunityProfile();});
    $('#community-profile-friend').onclick=communityProfileFriendAction;
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
      const displayName=$('#profile-display-input').value.trim();
      if(!displayName)return toast('اكتب الاسم أولًا',true);
      try{const d=await api('/api/profile',{method:'PATCH',body:JSON.stringify({displayName})});setUser(d.user);toast('تم حفظ التغييرات');}
      catch(err){toast(err.message||'تعذر حفظ الاسم',true);}
    };
    $('#profile-remove-photo').onclick=async()=>{try{await saveAvatarData('','تمت إزالة الصورة');}catch(err){toast(err.message||'تعذر إزالة الصورة',true);}};
  }
  async function loadStore(manual=false){
    try{
      const d=await api('/api/store');state.store=d;
      if(state.user){
        state.user.coins=Number(d.coins)||0;
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
        state.storeCategory=btn.dataset.category||'all';
        renderStore();
      });
    });
  }
  function renderStore(){
    wireStoreCategoryButtons();
    const data=state.store||{}, reward=data.dailyReward||{}, catalog=Array.isArray(data.catalog)?data.catalog:[], inventory=Array.isArray(data.inventory)?data.inventory:[], ledger=Array.isArray(data.ledger)?data.ledger:[];
    const userStars=Number(data.starsCount??state.user?.starsCount??5);
    const selectedCat=state.storeCategory||'all';
    const balance=$('#store-balance');if(balance)balance.textContent=formatProfileStat(data.coins);
    const rewardCoins=$('#store-reward-coins');if(rewardCoins)rewardCoins.textContent=formatProfileStat(reward.coinsPerMatch||50);
    const max=Math.max(1,Number(reward.maxMatches)||5),done=Math.max(0,Math.min(max,Number(reward.rewardedMatches)||0));
    const progress=$('#store-reward-progress');if(progress)progress.textContent=`${done}/${max}`;
    const note=$('#store-reward-note');if(note)note.textContent=done>=max?`اكتملت مكافآت اليوم: ${formatProfileStat(reward.maxCoins||0)} كوينز.`:`متبقي ${Math.max(0,max-done)} مباراة مكافأة اليوم.`;
    const steps=$('#store-reward-steps');if(steps){steps.replaceChildren();for(let i=0;i<max;i++){const step=document.createElement('span');step.className='reward-step'+(i<done?' done':'');step.setAttribute('aria-label',i<done?`المباراة ${i+1} تمت مكافأتها`:`المباراة ${i+1} لم تكتمل بعد`);const n=document.createElement('b');n.textContent=String(i+1);const c=document.createElement('small');c.textContent=`+${formatProfileStat(reward.coinsPerMatch||50)}`;step.append(n,c);steps.append(step);}}
    const owned=$('#store-owned-count');if(owned)owned.textContent=`${inventory.length} مملوك`;

    const filteredCatalog=catalog.filter(item=>{
      if(selectedCat==='all')return true;
      if(selectedCat==='profile')return item.category==='profile';
      if(selectedCat==='pool')return item.category==='pool';
      if(selectedCat==='carrom')return item.category==='carrom';
      if(selectedCat==='other')return !['profile','pool','carrom'].includes(item.category);
      return true;
    });

    const box=$('#store-catalog');if(box){box.replaceChildren();if(!filteredCatalog.length){box.append(emptyBlock('لا توجد عناصر متاحة في هذا القسم حاليًا.'));}else for(const item of filteredCatalog){
      const isStar=item.slot==='profile_stars'||item.id==='profile_star';
      const isBadge=item.slot==='name_badge';
      const active=isBadge?(data.equipped?.name_badge||'badge_palm_swords')===item.id:(data.equipped?.[item.slot]===item.id);
      const card=document.createElement('article');card.className='store-item-card'+(active?' is-equipped':'');
      if(item.asset){const visual=document.createElement('img');visual.className='store-item-visual';visual.alt=String(item.name||'تصميم');visual.loading='lazy';visual.src=String(item.asset);card.append(visual);}
      const copy=document.createElement('div');copy.className='store-item-copy';
      const title=document.createElement('strong');title.textContent=String(item.name||item.id||'عنصر');
      const desc=document.createElement('small');desc.textContent=String(item.description||'');
      const badge=document.createElement('span');badge.className='store-item-badge';
      if(isStar){
        badge.textContent=userStars>=5?'الحد الأقصى (5/5 نجوم)':`${userStars}/5 نجوم مكتسبة`;
      }else if(item.default){
        badge.textContent='الافتراضي المجاني';
      }else if(item.availableToAll){
        badge.textContent='متاح للجميع';
      }else if(item.owned){
        badge.textContent=isBadge?'ملصق اسم مملوك':'مملوك';
      }else{
        badge.textContent=`سعر الشراء: ${item.price} كوينز`;
      }
      copy.append(badge,title,desc);
      if(!item.owned&&!item.availableToAll&&!item.default&&item.price>0){
        const priceLabel=document.createElement('span');priceLabel.className='store-item-price';
        priceLabel.innerHTML=`<span class="coin-mark small" aria-hidden="true">C</span> ${formatProfileStat(item.price)} كوينز`;
        copy.append(priceLabel);
      }
      card.append(copy);

      const action=document.createElement('button');action.type='button';action.className='ghost compact';
      if(isStar){
        if(userStars>=5){
          action.textContent='مكتمل (5 نجوم)';action.disabled=true;
        }else{
          action.className='ghost compact store-item-btn-buy';
          action.textContent=`شراء نجمة (${formatProfileStat(item.price||50)} كوينز)`;
          action.onclick=()=>buyStoreItem(item.id,action);
        }
      }else if(item.owned||item.availableToAll||item.default){
        action.textContent=active?'مفعّل الآن':isBadge?'تفعيل الشارة':'تفعيل التصميم';
        action.setAttribute('aria-pressed',String(active));
        action.disabled=active;
        if(!active)action.onclick=()=>equipStoreItem(item.id,action);
      }else{
        action.className='ghost compact store-item-btn-buy';
        action.textContent=`شراء (${formatProfileStat(item.price)} كوينز)`;
        action.onclick=()=>buyStoreItem(item.id,action);
      }
      card.append(action);box.append(card);
    }}
    const ledgerBox=$('#store-ledger');if(ledgerBox){ledgerBox.replaceChildren();if(!ledger.length){ledgerBox.append(emptyBlock('لا توجد حركات حتى الآن.'));}else for(const entry of ledger){
      const row=document.createElement('div');row.className='store-ledger-row';const mark=document.createElement('span');mark.className='coin-mark small';mark.textContent='C';
      const copy=document.createElement('div');const title=document.createElement('strong');
      title.textContent=entry.type==='daily_match_reward'?'مكافأة مباراة يومية':entry.type==='store_purchase'?'شراء من المتجر':'حركة متجر';
      const meta=document.createElement('small');const d=new Date(Number(entry.createdAt)||Date.now());meta.textContent=(entry.roomId?`مباراة ${entry.roomId} · `:'')+d.toLocaleString('ar-SA',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});copy.append(title,meta);
      const amount=document.createElement('b');const n=Math.trunc(Number(entry.amount)||0),abs=Math.abs(n).toLocaleString('en-US');amount.textContent=`${n>=0?'+':'-'}${abs}`;row.append(mark,copy,amount);ledgerBox.append(row);
    }}
  }
  async function buyStoreItem(itemId,button){
    const item=(state.store?.catalog||[]).find(x=>x.id===itemId);
    const itemName=item?.name||'العنصر';
    const price=item?.price||0;
    const balance=Number(state.store?.coins??state.user?.coins??0);
    if(balance<price){
      toast(`رصيد الكوينز غير كافٍ. يتطلب ${price} كوينز (رصيدك الحالي ${balance})`,true);
      return;
    }
    try{
      button.disabled=true;
      const result=await api('/api/store/buy',{method:'POST',body:JSON.stringify({itemId})});
      toast(`تم شراء ${itemName} بنجاح!`);
      await loadStore();
      if(result.starsCount!==undefined&&state.user){
        state.user.starsCount=result.starsCount;
        setUser(state.user);
      }
    }catch(err){
      button.disabled=false;
      toast(err.message||'تعذر إتمام الشراء',true);
    }
  }
  async function equipStoreItem(itemId,button){
    try{
      button.disabled=true;
      const result=await api('/api/store/equip',{method:'POST',body:JSON.stringify({itemId})});
      if(state.store){state.store.equipped=result.equipped;renderStore();}
      if(state.user&&result.equipped?.name_badge){
        state.user.nameBadge=result.equipped.name_badge;
        const bItem=(state.store?.catalog||[]).find(x=>x.id===result.equipped.name_badge);
        if(bItem){state.user.nameBadgeAsset=bItem.asset;state.user.nameBadgeName=bItem.name;}
        setUser(state.user);
      }
      toast('تم تفعيل العنصر بنجاح');
    }
    catch(err){button.disabled=false;toast(err.message||'تعذر تجهيز العنصر',true);}
  }
  function navigate(page){
    if(!page)return;
    if(page!=='profile')closeProfileEditor();
    state.page=page;
    document.body.classList.toggle('community-mode',page==='lobby'&&!!state.activeCommunity);
    $$('.page').forEach(p=>p.classList.toggle('active',p.id===`page-${page}`));
    $$('.nav-btn,.bottom-btn').forEach(b=>b.classList.toggle('active',b.dataset.page===page));
    if(page==='lobby'){
      if(state.activeCommunity)loadCommunityState(); else loadCommunities();
    }
    if(page==='friends')loadFriends();
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
      const d=await api('/api/communities');state.communities=d.communities||[];renderCommunities();
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
      const found=state.communities.find(c=>c.id===id)||{id};state.activeCommunity=found;
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
    state.activeCommunity=null;state.rooms=[];state.communityMembers=[];state.communityMessages=[];
    $('#community-room').classList.add('hidden');$('#community-home').classList.remove('hidden');document.body.classList.remove('community-mode');
    syncCommunityLocation('');loadCommunities();
  }
  async function loadCommunityState(manual=false){
    const active=state.activeCommunity;if(!active)return loadCommunities(manual);
    try{
      const d=await api(`/api/communities/${encodeURIComponent(active.id)}`);
      state.activeCommunity=d.community||active;state.rooms=d.rooms||[];state.communityMembers=d.members||[];state.communityMessages=d.messages||[];
      renderCommunityState();renderRooms();
      if(manual)toast('تم تحديث المساحة');
    }catch(err){if(err.status===401)return showAuth();if(err.status===404){leaveCommunity();return;}if(manual)toast(err.message,true);}
  }
  function visibleCommunityMembers(){
    const selfId=String(state.user?.id||'');
    return (state.communityMembers||[]).filter(u=>String(u?.id||'')!==selfId);
  }
  function renderCommunityState(){
    const c=state.activeCommunity;if(!c)return;
    const room=$('#community-room');room.style.setProperty('--community-accent',c.accent||'#d5a34c');
    $('#active-community-name').textContent=c.name||'المساحة';$('#active-community-description').textContent=c.description||'';$('#active-community-mark').textContent=c.mark||initials(c.name);$('#active-community-mark').style.setProperty('--community-accent',c.accent||'#d5a34c');
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
  function renderCommunityMembers(){
    const box=$('#community-members');if(!box)return;
    const members=visibleCommunityMembers();box.replaceChildren();
    if(!members.length){box.append(emptyBlock('لا يوجد أعضاء آخرون متصلون الآن.'));return;}
    for(const u of members){
      const name=String(u.displayName||u.username||'Player');
      const row=document.createElement('div');row.className='community-member';row.dataset.publicProfile=String(u.id||'');row.tabIndex=0;row.setAttribute('role','button');row.setAttribute('aria-label',`فتح ملف ${name}`);
      row.append(avatarNode(u,'community-member-avatar'));
      const title=document.createElement('div');title.className='community-member-title';const strong=document.createElement('strong');strong.textContent=name;
      const emblem=profileSprite('profile-sprite-emblem community-member-emblem');
      const badgeAsset=u.nameBadgeAsset||'/platform/assets/profile/raster/palm-swords.webp';
      if(badgeAsset)emblem.style.backgroundImage=`url('${badgeAsset}')`;
      title.append(strong,emblem);
      const stars=document.createElement('div');stars.className='community-member-stars';
      const userStars=Math.max(0,Math.min(5,Number(u.starsCount??5)));
      stars.setAttribute('aria-label',`${userStars} نجوم`);
      for(let i=0;i<5;i++){
        const star=profileSprite('profile-sprite-star community-member-star');
        if(i>=userStars)star.classList.add('dim');
        stars.append(star);
      }
      const meta=document.createElement('div');meta.className='community-member-meta';
      for(const text of [`@${String(u.username||'player')}`,`فوز ${formatProfileStat(u.wins)}`,`سمعة ${formatProfileStat(u.reputation)}`]){const span=document.createElement('span');span.textContent=text;meta.append(span);}
      copy.append(title,stars,meta);const online=document.createElement('span');online.className='community-member-online';online.setAttribute('aria-label','متصل الآن');row.append(copy,online);box.append(row);
    }
  }
  function chatTime(ts){const d=new Date(Number(ts)||Date.now());return d.toLocaleTimeString('ar-SA',{hour:'2-digit',minute:'2-digit'});}
  function renderCommunityMessages(){
    const box=$('#community-chat-messages');if(!box)return;const wasNearBottom=box.scrollHeight-box.scrollTop-box.clientHeight<70;box.replaceChildren();
    if(!state.communityMessages.length){box.append(emptyBlock('ابدأ أول محادثة هنا.'));return;}
    for(const m of state.communityMessages){
      const article=document.createElement('article');article.className='community-chat-message';article.append(avatarNode({id:m.userId,displayName:m.displayName,username:m.username},'community-chat-avatar',true));
      const bubble=document.createElement('div');bubble.className='community-chat-bubble';const meta=document.createElement('div');meta.className='community-chat-meta';
      const name=document.createElement('strong');name.className='community-chat-profile-name';name.textContent=String(m.displayName||m.username||'Player');if(m.userId)name.dataset.publicProfile=String(m.userId);
      const time=document.createElement('time');time.textContent=chatTime(m.createdAt);const text=document.createElement('p');text.textContent=String(m.text||'');meta.append(name,time);bubble.append(meta,text);article.append(bubble);box.append(article);
    }
    if(wasNearBottom||!box.dataset.loaded){box.scrollTop=box.scrollHeight;box.dataset.loaded='1';}
  }
  function closeCommunityProfile(){
    if(window.__sdNativePublicProfile){window.__sdNativePublicProfile=false;window.SamiDevMobile?.postMessage(JSON.stringify({type:'native_home'}));}
    const modal=$('#community-profile-modal');if(!modal)return;
    modal.classList.remove('open');modal.setAttribute('aria-hidden','true');activePublicProfile=null;
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
    activePublicProfile=user;
    const name=user.displayName||user.username||'Player';
    $('#community-profile-name').textContent=name;
    const badgeAsset=user.nameBadgeAsset||'/platform/assets/profile/raster/palm-swords.webp';
    const badgeName=user.nameBadgeName||'سيفين ونخلة';
    const modalBadge=$('#community-profile-modal .profile-sticker');
    if(modalBadge){modalBadge.style.backgroundImage=`url('${badgeAsset}')`;modalBadge.setAttribute('aria-label',badgeName);modalBadge.setAttribute('title',badgeName);}
    const userStars=Math.max(0,Math.min(5,Number(user.starsCount??5)));
    $$('#community-profile-modal .community-public-profile-star').forEach((el,i)=>el.classList.toggle('dim',i>=userStars));
    $('#community-profile-handle').textContent='@'+String(user.username||'player');
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
    const items=Array.isArray(user.showcaseItems)?user.showcaseItems:[];
    const safe=x=>/^\/(?:images|games)\/[a-zA-Z0-9_./-]+$/.test(String(x||''))?x:'';
    extra.innerHTML=`<div class="sd-public-toggle-wrap"><button type="button" class="sd-public-toggle-btn" data-action="toggle-public-extra"><span>عرض الملف كاملاً</span><span class="sd-public-toggle-arrow">▼</span></button></div><div class="sd-public-full-content" hidden><h3>عناصر اللاعب</h3><div class="sd-public-items">${items.map(x=>`<div><img src="${escapeHtml(safe(x.asset))}" alt="" loading="lazy"><span>${escapeHtml(x.name)}</span></div>`).join('')||'<p>لا توجد عناصر للعرض</p>'}</div>${items.length>3?'<button type="button" class="sd-public-more">عرض كل العناصر</button>':''}<h3>الألعاب</h3>${[['pool','بلياردو'],['carrom','كيرم'],['tablesoccer','فوتبول'],['crazy8','أونو']].map(([id,name])=>{const g=(user.gameStatistics||[]).find(x=>x.gameId===id);return `<div class="sd-public-game"><b>${name}</b><span>المباريات: ${g?formatProfileStat(g.played):'—'}</span><span>الفوز: ${g?formatProfileStat(g.wins):'—'}</span></div>`}).join('')}<p class="sd-public-hint">تظهر الأرقام عند توفر سجل مباريات موثوق لكل لعبة.</p></div>`;
    extra.querySelector('[data-action="toggle-public-extra"]')?.addEventListener('click',e=>{
      const full=extra.querySelector('.sd-public-full-content');
      if(!full)return;
      const isHidden=full.hidden;
      full.hidden=!isHidden;
      const btn=e.currentTarget;
      btn.querySelector('span:first-child').textContent=isHidden?'عرض مختصر':'عرض الملف كاملاً';
      btn.querySelector('.sd-public-toggle-arrow').textContent=isHidden?'▲':'▼';
    });
    extra.querySelector('.sd-public-more')?.addEventListener('click',e=>{extra.querySelector('.sd-public-items').classList.toggle('expanded');e.currentTarget.textContent=extra.querySelector('.sd-public-items').classList.contains('expanded')?'عرض أقل':'عرض كل العناصر';});
    $('#community-profile-loading').classList.add('hidden');
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
    const box=$('#rooms'); if(!rooms.length){box.innerHTML='<div class="empty">لا توجد مباريات في هذه المساحة بعد. أنشئ أول مباراة.</div>';return;}
    box.innerHTML=rooms.map(r=>{
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
      return `<article class="room-card community-room-card">
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
      </article>`;
    }).join('');
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
  async function createRoom(){try{const cid=state.activeCommunity?.id;if(!cid)return toast('اختر مساحة أولًا',true);try{sessionStorage.setItem('samidev_return_community',cid);}catch(_){}const t=await ticket(cid);const gid=$('#create-game').value;const q=new URLSearchParams({online:'1',action:'create',ticket:t,community:cid,players:state.settings.players,game:gid});if(gid==='pool'){q.set('players','0');q.set('live','1');}else if(gid==='crazy8'){q.delete('players');q.set('seats',$('#create-card-seats').value);q.set('special',$('#create-card-special').value);q.set('live',$('#create-card-live').value);}else if(gid==='tablesoccer'){q.set('live',$('#create-soccer-mode').value);q.set('goalsToWin',$('#create-goals').value);q.set('passes',$('#create-passes').value);}else{q.set('gamemode',$('#create-gamemode').value);q.set('live',state.settings.live);q.set('break',$('#create-break').value);}location.href=window.SamiDevGames.get(gid).entry+'?'+q;}catch(err){toast(err.message,true);}}
  async function loadFriends(){try{const d=await api('/api/friends');state.friends=d.friends||[];state.requests=d.requests||[];renderFriends();}catch(err){if(err.status===401)showAuth();}}
  function personRow(u,actions=''){return `<div class="person"><span class="presence ${u.online?'online':''}"></span><div class="person-info"><strong>${escapeHtml(u.displayName||u.username)}</strong><small>@${escapeHtml(u.username)}${u.online?' · متصل':''}</small></div><div class="person-actions">${actions}</div></div>`;}
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
    if(!state.user||!['admin','moderator'].includes(state.user.role))return;
    try{
      const [s,u,r]=await Promise.all([api('/api/admin/stats'),api('/api/admin/users'),api('/api/admin/reports')]);
      const st=s.stats;
      $('#admin-stats').innerHTML=`<div><span>${st.users}</span><small>المستخدمون</small></div><div><span>${st.onlineUsers}</span><small>متصلون</small></div><div><span>${st.waitingRooms}</span><small>غرف انتظار</small></div><div><span>${st.runningRooms}</span><small>مباريات جارية</small></div>`;
      $('#admin-users').innerHTML=u.users.map(x=>`<tr><td><strong>${escapeHtml(x.displayName)}</strong><br><small>@${escapeHtml(x.username)}</small></td><td>${x.online?'متصل':'غير متصل'}</td><td><select class="role-select" data-id="${x.id}" ${state.user.role!=='admin'||x.id===state.user.id?'disabled':''}><option value="user" ${x.role==='user'?'selected':''}>user</option><option value="moderator" ${x.role==='moderator'?'selected':''}>moderator</option><option value="admin" ${x.role==='admin'?'selected':''}>admin</option></select></td><td>${x.banned?'محظور':'—'}</td><td><button class="${x.banned?'small-btn':'danger-btn'} ban-user" data-id="${x.id}" data-ban="${x.banned?'0':'1'}" ${x.id===state.user.id?'disabled':''}>${x.banned?'فك الحظر':'حظر'}</button></td></tr>`).join('');
      $$('.ban-user').forEach(b=>b.onclick=()=>adminBan(b.dataset.id,b.dataset.ban==='1'));
      $$('.role-select').forEach(s=>s.onchange=()=>adminRole(s.dataset.id,s.value));
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
