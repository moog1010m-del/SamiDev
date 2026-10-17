(() => {
  'use strict';
  // Identity/status overlay only. browser-runtime draws the actual native scene.
  const game=window.SamiDevGames.current().id;
  let root,opponents,own,label,loading,themeObserver,complete=false;
  const el=(tag,cls,text)=>{const n=document.createElement(tag);n.className=cls;if(text!==undefined)n.textContent=text;return n;};
  function build(){
    if(root)return;
    const style=el('style','');style.textContent=`
      body.sd-waiting #status,body.sd-waiting #mode-menu-button{display:none!important}
      #sd-waiting{position:fixed;inset:0;z-index:20;display:grid;grid-template-rows:auto minmax(0,1fr) auto;padding:64px 12px 18px;gap:12px;box-sizing:border-box;background:#0a1d25;color:#edf5ee;font:14px system-ui;direction:rtl;touch-action:none}
      #sd-waiting[hidden]{display:none!important}#sd-waiting.scene-ready{display:block;background:transparent;pointer-events:none;padding:0}#sd-waiting.scene-ready .sd-waiting-stage{display:none}#sd-waiting.scene-ready .sd-waiting-bottom{position:absolute;left:12px;right:12px;bottom:12px;display:flex;justify-content:center;align-items:center;flex-wrap:wrap}#sd-table-controls{pointer-events:auto}#sd-waiting.scene-ready .sd-waiting-label{flex:0 1 auto}#sd-waiting.scene-ready>.sd-waiting-top,#sd-waiting.scene-ready .sd-waiting-own{display:none}
      .sd-waiting-top,.sd-waiting-own{display:flex;justify-content:center;gap:8px;flex-wrap:wrap;min-width:0}.sd-waiting-stage{display:grid;place-items:center;pointer-events:none;min-height:0}.sd-waiting-loading{padding:16px 22px;border-radius:14px;background:#071b22e8;color:#e9d5a0;font-size:13px}.scene-ready .sd-waiting-loading{display:none}
      .sd-waiting-player{box-sizing:border-box;display:grid;grid-template-columns:40px minmax(0,1fr);align-items:center;gap:8px;min-width:0;max-width:min(44vw,240px);padding:6px 10px;border:1px solid #b9a16c88;border-radius:15px;background:#081b23e8;box-shadow:0 4px 18px #0005;color:inherit;font:600 13px system-ui;cursor:pointer;text-align:right}
      .sd-waiting-player img{width:40px;height:40px;object-fit:cover;border-radius:50%}.sd-waiting-identity{min-width:0;display:grid;gap:3px}.sd-waiting-name{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;unicode-bidi:plaintext}.sd-waiting-status{font-size:10px;color:#aacabe;font-weight:400}.sd-waiting-player[data-connected="false"]{opacity:.7}
      .sd-waiting-bottom{display:grid;justify-items:center;gap:8px}.sd-waiting-label{margin:0;padding:8px 16px;border:1px solid #c4a56b44;border-radius:10px;background:#071820ed;color:#e5d7b5;max-width:100%;font-size:12px;text-align:center;line-height:1.5}.sd-waiting-label.error{color:#ffb4b4}
      .sd-table-action{padding:8px 14px;border:1px solid #b9a16c88;border-radius:10px;background:#081b23e8;color:#edf5ee;font:600 12px system-ui;cursor:pointer}
      @media(max-height:450px) and (orientation:landscape){#sd-waiting{padding:52px 12px 8px;grid-template-columns:125px minmax(0,1fr) 125px;grid-template-rows:1fr}.sd-waiting-player{max-width:125px;grid-template-columns:30px minmax(0,1fr);padding:4px;gap:4px}.sd-waiting-player img{width:30px;height:30px}.sd-waiting-top{align-content:center}.sd-waiting-bottom{align-content:center}.sd-waiting-label{font-size:10px}}
    `;document.head.appendChild(style);
    root=el('section','');root.id='sd-waiting';root.dataset.game=game;root.setAttribute('aria-label','مشهد اللعبة بانتظار اللاعبين');
    opponents=el('div','sd-waiting-top');const stage=el('div','sd-waiting-stage');loading=el('p','sd-waiting-loading','جارٍ تحميل مشهد اللعبة…');stage.append(loading);
    const bottom=el('div','sd-waiting-bottom');own=el('div','sd-waiting-own');label=el('p','sd-waiting-label','بانتظار انضمام الخصم…');label.setAttribute('role','status');
    const controls=el('div','sd-waiting-top');controls.id='sd-table-controls';
    bottom.append(own,label,controls);root.append(opponents,stage,bottom);document.body.appendChild(root);
  }
  function playerNode(player){
    const button=el('button','sd-waiting-player');button.type='button';button.dataset.seat=String(player.seat);button.dataset.connected=String(player.connected!==false);
    button.setAttribute('aria-label',`بطاقة ${player.name}`);
    const img=el('img','');img.alt='';img.src=player.accountId?`/api/avatar/${encodeURIComponent(player.accountId)}`:'/images/default-avatar.png';img.onerror=()=>{img.onerror=null;img.src='/images/default-avatar.png';};
    const identity=el('span','sd-waiting-identity'),name=el('span','sd-waiting-name',player.name);name.title=player.name;identity.append(name,el('small','sd-waiting-status',player.connected===false?'غير متصل':'متصل'));button.append(img,identity);
    button.onclick=()=>{if(window.SamiDevMobile?.postMessage&&player.accountId)window.SamiDevMobile.postMessage(JSON.stringify({type:'open_player_profile',userId:player.accountId}));else window.SamiDevPlayerProfileUI?.openSeat?.(player.seat);};return button;
  }
  function show(){if(complete)return;build();root.hidden=false;document.body.classList.add('sd-waiting');}
  function update(message){
    if(complete)return;show();const state=window.SamiDevNetwork.state;
    const roster=(message?.roster||state.roster||[]).filter(p=>p&&p.name);
    // The native scene owns the occupied/empty avatar slots; no second profile view.
    opponents.hidden=true;own.hidden=true;
    label.textContent=message?.started?'جارٍ تجهيز المباراة…':'بانتظار انضمام الخصم…';
    const controls=document.getElementById('sd-table-controls');controls.replaceChildren();
    if(!window.SamiDevMobile?.postMessage&&!state.begun&&state.ownerSeat===state.seat){
      const send=(action,targetSeat)=>{if(!window.SamiDevNetwork.send({type:'manage_table',action,targetSeat:targetSeat??-1}))window.SamiDevWaitingRoom.fail('انقطع الاتصال؛ أعد المحاولة بعد عودته');};
      const close=el('button','sd-table-action','إغلاق الطاولة');close.type='button';
      close.onclick=()=>{if(confirm('إغلاق الطاولة وإعادة اللاعبين إلى المساحة؟'))send('close');};controls.append(close);
      for(const player of roster.filter(p=>p.seat!==state.seat)){
        const kick=el('button','sd-table-action','إخراج '+player.name);kick.type='button';
        kick.onclick=()=>{if(confirm('إخراج '+player.name+' قبل بدء اللعب؟'))send('kick',player.seat);};controls.append(kick);
      }
    }

  }
  window.SamiDevWaitingRoom={show,sceneReady(){show();root.classList.add('scene-ready');root.dataset.renderer='native';},progress(text){show();if(label)label.textContent=text;},fail(text){show();label.textContent=text;label.classList.add('error');},ready(){complete=true;themeObserver?.disconnect();root?.remove();document.body.classList.remove('sd-waiting');}};
  window.SamiDevNetwork.on('assignment',update);window.SamiDevNetwork.on('room_state',update);
})();
