(() => {
  'use strict';
  const currentGame=window.SamiDevGames.current();
  const soccer=currentGame.id==='tablesoccer';
  const cards=currentGame.id==='crazy8';
  const pool=currentGame.id==='pool';

  const qs = new URLSearchParams(window.__SAMIDEV_QUERY ?? location.search);
  const running = qs.get('play') === '1' || qs.get('online') === '1';

  const css = document.createElement('style');
  css.textContent = `
    #samidev-launcher{position:fixed;inset:0;z-index:20000;display:flex;align-items:center;justify-content:center;
      background:radial-gradient(circle at 50% 22%,#263d55 0,#111923 48%,#080c11 100%);font-family:Arial,sans-serif;color:#fff;padding:20px;box-sizing:border-box}
    #samidev-launcher .panel{width:min(800px,96vw);max-height:94vh;overflow:auto;background:rgba(12,17,24,.95);border:1px solid rgba(255,255,255,.12);
      border-radius:22px;padding:24px;box-shadow:0 24px 80px rgba(0,0,0,.48)}
    #samidev-launcher h1{margin:0 0 6px;font-size:30px;text-align:center}
    #samidev-launcher .brand{font-size:13px;letter-spacing:2px;opacity:.65;text-align:center;margin-bottom:20px}
    #samidev-launcher .tabs{display:grid;grid-template-columns:1fr 1fr;gap:8px;margin-bottom:20px}
    #samidev-launcher .tab{border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.05);color:#fff;border-radius:12px;padding:11px;cursor:pointer;font-weight:700}
    #samidev-launcher .tab.active{background:#1565c0;border-color:#64b5f6}
    #samidev-launcher .section{margin:17px 0}
    #samidev-launcher .label{font-weight:700;margin:0 0 8px;display:block}
    #samidev-launcher .choices{display:grid;grid-template-columns:repeat(auto-fit,minmax(130px,1fr));gap:9px}
    #samidev-launcher label.choice{display:block}
    #samidev-launcher .choice input{position:absolute;opacity:0;pointer-events:none}
    #samidev-launcher .choice span{display:flex;align-items:center;justify-content:center;text-align:center;min-height:44px;padding:7px 10px;border-radius:12px;
      border:1px solid rgba(255,255,255,.13);background:rgba(255,255,255,.055);cursor:pointer;transition:.15s}
    #samidev-launcher .choice input:checked + span{background:#1976d2;border-color:#64b5f6;box-shadow:0 0 0 2px rgba(100,181,246,.18) inset}
    #samidev-launcher .teams{font-size:13px;opacity:.7;margin-top:8px;text-align:center}
    #samidev-launcher input.text{width:100%;box-sizing:border-box;border-radius:12px;border:1px solid rgba(255,255,255,.16);background:rgba(255,255,255,.07);color:#fff;padding:12px 13px;font-size:16px;outline:none}
    #samidev-launcher input.text:focus{border-color:#64b5f6}
    #samidev-launcher .actions{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-top:18px}
    #samidev-launcher button.action{border:0;border-radius:14px;padding:14px 18px;font-size:17px;font-weight:700;color:#fff;background:#16883f;cursor:pointer}
    #samidev-launcher button.join{background:#1565c0}
    #samidev-launcher .joinbox{display:grid;grid-template-columns:1fr auto;gap:9px;align-items:end}
    #samidev-launcher .joinbox button{height:46px;padding:0 18px;border:0;border-radius:12px;background:#1565c0;color:#fff;font-weight:700;cursor:pointer}
    #samidev-launcher .hint{font-size:12px;opacity:.62;margin-top:7px;line-height:1.6}
    #mode-menu-button{position:fixed;left:10px;bottom:10px;z-index:10000;border:0;border-radius:999px;padding:7px 11px;background:rgba(0,0,0,.62);color:#fff;font:12px Arial,sans-serif;cursor:pointer;backdrop-filter:blur(6px);opacity:.82}
    .hidden{display:none!important}
    @media(max-width:560px){#samidev-launcher .panel{padding:17px}#samidev-launcher h1{font-size:24px}#samidev-launcher .actions{grid-template-columns:1fr}.joinbox{grid-template-columns:1fr!important}.joinbox button{width:100%}}
  `;
  document.head.appendChild(css);

  function choice(name, value, text, checked=false){
    return `<label class="choice"><input type="radio" name="${name}" value="${value}" ${checked?'checked':''}><span>${text}</span></label>`;
  }

  function showLauncher(){
    const status=document.getElementById('status');
    if(status) status.style.display='none';
    const wrap=document.createElement('div');
    wrap.id='samidev-launcher';
    wrap.innerHTML=`
      <div class="panel" dir="rtl">
        <h1>${currentGame.title}</h1>
        <div class="brand">SAMIDEV GAME PLATFORM</div>

        <div class="tabs">
          <button class="tab active" data-tab="online" type="button">SamiDev Online</button>
          <button class="tab" data-tab="local" type="button">لعب محلي</button>
        </div>

        <div id="online-only" class="section">
          <span class="label">اسم اللاعب</span>
          <input id="player-name" class="text" maxlength="24" value="Player" placeholder="اسم اللاعب">
        </div>

        <div id="settings-block">
          ${soccer?`<div class="section"><span class="label">أهداف الفوز</span><div class="choices">${choice('goalsToWin','0','2')}${choice('goalsToWin','1','3',true)}${choice('goalsToWin','2','5')}</div></div><div class="section"><span class="label">التمريرات</span><div class="choices">${choice('passes','0','بدون حد',true)}${choice('passes','1','3')}${choice('passes','2','6')}</div></div>`:''}
          <div class="section">
            <span class="label">عدد اللاعبين</span>
            <div class="choices">
              ${choice('players','0','2 Players',true)}
              ${choice('players','1','2v2 — 4 Players')}
            </div>
            <div class="teams">${soccer?'2v2: Player 1 + Player 2 ضد Player 3 + Player 4':'2v2: Player 1 + Player 3 ضد Player 2 + Player 4'}</div>
          </div>

          <div class="section">
            <span class="label">نمط اللعب</span>
            <div class="choices">
              ${choice('gamemode','0','Classic',true)}
              ${choice('gamemode','1','Pool')}
              ${choice('gamemode','2','Freestyle /120')}
              ${choice('gamemode','3','Freestyle /160')}
              ${choice('gamemode','4','Freestyle /210')}
            </div>
          </div>

          <div class="section">
            <span class="label">نوع المباراة</span>
            <div class="choices">
              ${choice('live','1',soccer?'ACTIVE — متزامن':'LIVE',!soccer)}
              ${choice('live','0',soccer?'TACTICAL — تناوب':'TURN-BASED',soccer)}
            </div>
          </div>

          <div class="section">
            <span class="label">من يبدأ الـ Break؟</span>
            <div class="choices">
              ${choice('break','0','1st Player',true)}
              ${choice('break','1','2nd Player')}
              ${choice('break','2','Random')}
            </div>
          </div>
        </div>

        <div id="online-actions">
          <div class="actions">
            <button id="create-room" class="action" type="button">إنشاء غرفة</button>
            <button id="show-join" class="action join" type="button">دخول بكود غرفة</button>
          </div>
          <div id="join-panel" class="section hidden">
            <span class="label">كود الغرفة</span>
            <div class="joinbox">
              <input id="room-code" class="text" maxlength="6" autocomplete="off" placeholder="مثال: A7K9Q2" style="text-transform:uppercase;direction:ltr;text-align:center;font-weight:700;letter-spacing:2px">
              <button id="join-room" type="button">دخول</button>
            </div>
            <div class="hint">إعدادات المباراة تأتي من صاحب الغرفة؛ ما تحتاج تختارها عند الدخول.</div>
          </div>
        </div>

        <div id="local-actions" class="hidden">
          <button id="start-local" class="action" style="width:100%;margin-top:12px" type="button">ابدأ المباراة المحلية</button>
        </div>
      </div>`;
    document.body.appendChild(wrap);
    if(pool){
      wrap.querySelector('input[name="break"][value="2"]')?.closest('label')?.remove();
      wrap.querySelector('input[name="gamemode"]').closest('.section').outerHTML=`<div class="section"><span class="label">نوع البلياردو</span><div class="choices">${window.SamiDevGames.poolModes.map((label,i)=>choice('gameType',i,label,i===0)).join('')}</div></div>`;
      for(const name of ['players','live'])wrap.querySelector(`input[name="${name}"]`)?.closest('.section')?.classList.add('hidden');
      wrap.querySelector('#settings-block').insertAdjacentHTML('beforeend',`<div class="section"><span class="label">الطاولة</span><div class="choices">${choice('largeTable','0','الأصلية',true)}${choice('largeTable','1','الطاولة الكبيرة')}</div></div>`);
    }
    if(cards){
      wrap.querySelector('[data-tab="local"]').classList.add('hidden');
      wrap.querySelector('input[name="players"]').closest('.section').outerHTML=`<div class="section"><span class="label">عدد اللاعبين</span><div class="choices">${window.SamiDevGames.cardSeats.map((label,i)=>choice('seats',i,label,i===2)).join('')}</div></div><div class="section"><span class="label">الأوراق الخاصة</span><div class="choices">${window.SamiDevGames.cardSpecial.map((label,i)=>choice('special',i,label,i===0)).join('')}</div></div>`;
    }
    if(soccer||cards)for(const name of ['gamemode','break'])wrap.querySelector(`input[name="${name}"]`)?.closest('.section')?.classList.add('hidden');

    let current='online';
    const onlineActions=wrap.querySelector('#online-actions');
    const localActions=wrap.querySelector('#local-actions');
    const onlineOnly=wrap.querySelector('#online-only');
    const tabs=[...wrap.querySelectorAll('.tab')];
    tabs.forEach(btn=>btn.addEventListener('click',()=>{
      current=btn.dataset.tab;
      tabs.forEach(x=>x.classList.toggle('active',x===btn));
      onlineActions.classList.toggle('hidden',current!=='online');
      onlineOnly.classList.toggle('hidden',current!=='online');
      localActions.classList.toggle('hidden',current!=='local');
    }));

    const val=n=>wrap.querySelector(`input[name="${n}"]:checked`).value;
    const gameParams=()=>pool?{game:currentGame.id,gameType:val('gameType'),break:val('break'),live:'1',largeTable:val('largeTable')}:cards?{game:currentGame.id,seats:val('seats'),special:val('special'),live:val('live')}:({game:currentGame.id,...(soccer?{goalsToWin:val('goalsToWin'),passes:val('passes')} : {}),players:val('players'),gamemode:val('gamemode'),live:val('live'),break:val('break')});
    const go=params=>{
      const p=new URLSearchParams(params);
      location.search=p.toString();
    };

    wrap.querySelector('#start-local').onclick=()=>go({play:'1',...gameParams()});
    wrap.querySelector('#create-room').onclick=()=>{
      const name=(wrap.querySelector('#player-name').value||'Player').trim();
      go({online:'1',action:'create',name,...gameParams()});
    };
    wrap.querySelector('#show-join').onclick=()=>wrap.querySelector('#join-panel').classList.toggle('hidden');
    const join=()=>{
      const name=(wrap.querySelector('#player-name').value||'Player').trim();
      const room=(wrap.querySelector('#room-code').value||'').trim().toUpperCase();
      if(room.length<4){ wrap.querySelector('#room-code').focus(); return; }
      go({online:'1',action:'join',name,room});
    };
    wrap.querySelector('#join-room').onclick=join;
    wrap.querySelector('#room-code').addEventListener('keydown',e=>{if(e.key==='Enter')join();});
  }

  if(!running){
    showLauncher();
    return;
  }

  if(qs.get('online')!=='1'||!window.SamiDevRoomUI){
  const menu=document.createElement('button');
  menu.id='mode-menu-button';
  menu.textContent=qs.get('online')==='1'?'EXIT':'MODES';
  menu.title='الرجوع للقائمة الرئيسية';
  menu.onclick=()=>{
    if(qs.get('online')==='1' && window.SamiDevRoomUI?.openExit){ window.SamiDevRoomUI.openExit(); return; }
    if(window.__SAMIDEV_APP_HOST)window.__SAMIDEV_APP_HOST.returnToPlatform();else location.href='/platform/';
  };
  document.body.appendChild(menu);
  }
  window.__startSamiDevGame();
})();
