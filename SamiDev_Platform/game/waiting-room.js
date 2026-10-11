(() => {
  'use strict';
  // A visual waiting table only. Dealing, physics, turns and runtimeReady still
  // wait for the authoritative start message in browser-runtime.js.
  const game=window.SamiDevGames.current().id;
  let root,board,opponents,own,label,resizeObserver,themeObserver,complete=false,carromTheme='classic';
  function el(tag,className,text){const n=document.createElement(tag);n.className=className;if(text!==undefined)n.textContent=text;return n;}
  function build(){
    if(root)return;
    const style=el('style','');style.textContent=`
      body.sd-waiting #status,body.sd-waiting #mode-menu-button{display:none!important}
      #sd-waiting{position:fixed;inset:0;z-index:20;display:grid;grid-template-rows:82px minmax(0,1fr) 100px;gap:8px;padding:60px 14px 10px;box-sizing:border-box;background:radial-gradient(ellipse at 50% 35%,#153e49 0%,#101e2b 55%,#080f19 100%);color:#fff;font:15px system-ui,sans-serif;direction:rtl}
      #sd-waiting[hidden]{display:none}
      #sd-waiting.light{background:#e8ecef;color:#152732}
      .sd-waiting-top,.sd-waiting-bottom{display:flex;justify-content:center;align-items:center;gap:8px;min-width:0}
      .sd-waiting-bottom{flex-direction:column;gap:4px}
      .sd-waiting-player{display:flex;align-items:center;gap:8px;border:0;background:transparent;color:inherit;font:600 15px system-ui;max-width:min(42vw,220px);padding:5px 9px;cursor:pointer;border-radius:16px;background:#0c2132b8;border:1px solid #c39a4b55;text-align:right;min-width:0}
      .sd-waiting-player span{display:block;min-width:0;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;unicode-bidi:plaintext}
      .sd-waiting-player img{width:48px;height:48px;flex:0 0 48px;border-radius:50%;border:2px solid #bb9b56;object-fit:cover}
      /* V33: player identity remains readable on narrow and landscape screens. */
      .sd-waiting-top,.sd-waiting-own{position:relative;z-index:2;max-width:100%;min-width:0}
      .sd-waiting-player{box-sizing:border-box;flex:0 1 auto;min-width:0;max-width:min(44vw,230px);box-shadow:0 6px 22px #0008;isolation:isolate;overflow:hidden}
      .sd-waiting-player span{flex:1 1 auto;min-width:0;max-width:100%;line-height:1.35;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
      .sd-waiting-player img{display:block;flex-shrink:0;aspect-ratio:1;max-width:48px}
      #sd-waiting .sd-waiting-player{min-width:0;max-width:100%;overflow:hidden;box-sizing:border-box}
      #sd-waiting .sd-waiting-player span{display:block;min-width:0;max-width:100%;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;unicode-bidi:plaintext}
      #sd-waiting .sd-waiting-player img{flex-shrink:0;object-fit:cover}
      #sd-waiting[data-game="pool"]{background:radial-gradient(ellipse at 50% 30%,#245744 0%,#132b29 58%,#0a181b 100%)}
      #sd-waiting[data-game="pool"] .sd-waiting-player{background:linear-gradient(145deg,#153e43ed,#091c2bec);border-color:#d5ac65a8}
      @media(max-width:600px){.sd-waiting-player{max-width:44vw;padding:4px 6px;gap:5px;font-size:12px}.sd-waiting-player img{width:36px;height:36px;flex-basis:36px}.sd-waiting-top{gap:4px;flex-wrap:wrap}}
      @media(max-height:460px) and (orientation:landscape){#sd-waiting{padding-top:44px;padding-bottom:4px;grid-template-columns:115px minmax(0,1fr) 120px;gap:3px}.sd-waiting-player{max-width:112px;flex-direction:column;font-size:11px;padding:3px}.sd-waiting-player img{width:32px;height:32px;flex-basis:32px}.sd-waiting-label{font-size:10px}}
      /* Keep avatar and long RTL names in independent flex tracks. */
      #sd-waiting .sd-waiting-player{display:flex;flex-direction:row;justify-content:flex-start;align-items:center;gap:8px;width:min(44vw,230px);max-width:100%;min-width:0;overflow:hidden}
      #sd-waiting .sd-waiting-player img{width:clamp(32px,9vw,48px);height:clamp(32px,9vw,48px);flex:0 0 clamp(32px,9vw,48px);box-sizing:border-box}
      #sd-waiting .sd-waiting-player span{flex:1 1 0;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;direction:rtl;text-align:start}
      #sd-waiting .sd-waiting-top{display:flex;flex-wrap:wrap;align-content:center;justify-content:center;min-width:0}
      @media(max-width:400px){#sd-waiting .sd-waiting-top .sd-waiting-player{flex-direction:row;gap:5px}}
      @media(max-height:460px) and (orientation:landscape){#sd-waiting .sd-waiting-player{width:112px;max-width:112px;flex-direction:column;gap:2px}#sd-waiting .sd-waiting-player span{text-align:center;width:100%}}
      /* Separate identity and board from decorative background, including small RTL screens. */
      #sd-waiting[data-game="pool"] .sd-waiting-stage:before{background:linear-gradient(180deg,#07151ecc,#102b35b8);opacity:1;border-radius:18px}
      #sd-waiting .sd-waiting-mirror{position:relative;z-index:1;isolation:isolate}
      #sd-waiting .sd-waiting-top,#sd-waiting .sd-waiting-bottom{z-index:2;min-width:0}
      #sd-waiting .sd-waiting-player{position:relative;overflow:hidden;min-width:0}
      #sd-waiting .sd-waiting-player img{position:relative;z-index:1;flex-shrink:0}
      #sd-waiting .sd-waiting-player span{position:relative;z-index:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;unicode-bidi:plaintext}
      /* V36: predictable identity rows, no overlap between avatar, name and status. */
      #sd-waiting .sd-waiting-player{width:min(100%,260px);max-width:100%;min-height:58px;display:grid;grid-template-columns:44px minmax(0,1fr);grid-template-rows:auto;align-items:center;column-gap:10px;padding:6px 10px;direction:rtl;overflow:visible}
      #sd-waiting .sd-waiting-player img{grid-column:1;grid-row:1;width:44px;height:44px;max-width:none;min-width:0;flex:none;border-radius:50%}
      #sd-waiting .sd-waiting-player .sd-waiting-identity{grid-column:2;grid-row:1;min-width:0;display:flex;flex-direction:column;align-items:stretch;gap:3px;overflow:hidden}
      #sd-waiting .sd-waiting-player .sd-waiting-name{display:block;max-width:100%;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.4;direction:rtl;text-align:right;unicode-bidi:plaintext}
      #sd-waiting .sd-waiting-player .sd-waiting-status{display:block;font-size:10px;font-weight:500;line-height:1.3;white-space:nowrap;color:#b6d7ce;text-align:right}
      #sd-waiting .sd-waiting-player[data-connected="false"] .sd-waiting-status{color:#d4b0a8}
      #sd-waiting .sd-waiting-top{flex-wrap:wrap;gap:8px;align-items:center}
      #sd-waiting .sd-waiting-own{max-width:100%;display:flex;justify-content:center}
      @media(max-width:600px){#sd-waiting{padding-inline:8px}#sd-waiting .sd-waiting-player{width:min(100%,205px);min-height:48px;grid-template-columns:36px minmax(0,1fr);gap:6px;padding:4px 7px;font-size:12px}#sd-waiting .sd-waiting-player img{width:36px;height:36px}}
      @media(max-height:460px) and (orientation:landscape){#sd-waiting .sd-waiting-player{width:116px;max-width:100%;display:flex;flex-direction:column;gap:3px;padding:4px}#sd-waiting .sd-waiting-player img{width:30px;height:30px}#sd-waiting .sd-waiting-player .sd-waiting-identity{width:100%;text-align:center}#sd-waiting .sd-waiting-player .sd-waiting-name,#sd-waiting .sd-waiting-player .sd-waiting-status{text-align:center}}
      .sd-waiting-player[data-connected="false"]{opacity:.65}
      #sd-waiting .sd-waiting-stage:before{display:none!important}
      .sd-waiting-stage{position:relative;min-height:0;display:flex;align-items:center;justify-content:center;overflow:hidden}
      .sd-waiting-board{position:relative;width:100%;height:100%;object-fit:contain;display:block}
      .sd-waiting-mirror{display:grid;direction:ltr;gap:0;aspect-ratio:866/1546;max-width:100%;height:100%;width:auto}
      .sd-waiting-mirror.pool{grid-template:1fr 1fr / 1fr 1fr}
      .sd-waiting-mirror.soccer{grid-template:1fr / 1fr 1fr;aspect-ratio:850/1394}
      .sd-waiting-mirror img{display:block;width:100%;height:100%;min-height:0;min-width:0}
      .sd-waiting-mirror.pool img:nth-child(2),.sd-waiting-mirror.soccer img:nth-child(2){transform:scaleX(-1)}
      .sd-waiting-mirror.pool img:nth-child(3){transform:scaleY(-1)}
      .sd-waiting-mirror.pool img:nth-child(4){transform:scale(-1)}
      .sd-waiting-stage:before{content:"";position:absolute;inset:4px;background:linear-gradient(#06121a55,#06121aaa),url("/room-sprites/pool.png") center/cover no-repeat;border:1px solid #cda75b44;border-radius:24px;opacity:.24;pointer-events:none}#sd-waiting[data-game="carrom"] .sd-waiting-stage:before{background-image:linear-gradient(#06121a55,#06121aaa),url("/room-sprites/carrom.png")}#sd-waiting[data-game="crazy8"] .sd-waiting-stage:before{background-image:linear-gradient(#06121a55,#06121aaa),url("/room-sprites/cards.png")}.sd-waiting-label{font-size:12px;line-height:1.5;text-align:center;max-width:100%;opacity:.8;margin:0}
      .sd-waiting-label.error{color:#e34c4c;opacity:1}
      #sd-waiting[data-game="crazy8"] .sd-waiting-board{object-fit:cover;border-radius:30px;max-width:860px}
      @media(min-aspect-ratio:1/1){#sd-waiting{grid-template-columns:150px minmax(0,1fr) 170px;grid-template-rows:minmax(0,1fr);padding-top:64px}.sd-waiting-top{flex-direction:column}.sd-waiting-player{flex-direction:column;text-align:center}.sd-waiting-top,.sd-waiting-bottom{flex-wrap:wrap}}
      @media(max-width:400px){.sd-waiting-top .sd-waiting-player{flex-direction:column;font-size:12px;gap:2px}.sd-waiting-top .sd-waiting-player img{width:38px;height:38px;flex-basis:38px}}
    `;document.head.appendChild(style);
    root=el('section','');root.id='sd-waiting';root.dataset.game=game;root.setAttribute('aria-label','الطاولة بانتظار اللاعبين');
    opponents=el('div','sd-waiting-top');board=el('div','sd-waiting-stage');
    const bottom=el('div','sd-waiting-bottom');own=el('div','sd-waiting-own');label=el('p','sd-waiting-label','بانتظار انضمام الخصم…');label.setAttribute('role','status');
    bottom.append(own,label);root.append(opponents,board,bottom);document.body.appendChild(root);
    const updateTheme=()=>root.classList.toggle('light',document.documentElement.dataset.theme==='light');
    updateTheme();themeObserver=new MutationObserver(updateTheme);themeObserver.observe(document.documentElement,{attributes:true,attributeFilter:['data-theme']});
    resizeObserver=new ResizeObserver(fitBoard);resizeObserver.observe(board);
    renderBoard({});
  }
  function fitBoard(){
    const mirror=board?.querySelector('.sd-waiting-mirror');if(!mirror||!board.clientWidth||!board.clientHeight)return;
    const ratio=game==='pool'?866/1546:850/1394;const width=Math.min(board.clientWidth,board.clientHeight*ratio);
    mirror.style.width=`${width}px`;mirror.style.height=`${width/ratio}px`;
  }
  function renderBoard(message){
    if(!board)return;
    const st=window.SamiDevNetwork.state;
    const theme=message?.cosmetics?.[String(st.seat)]?.pool_theme==='pool_emerald'?'pool-emerald':'pool-emerald';
    let key=game==='pool'?theme:game==='carrom'?carromTheme:game;
    if(board.dataset.asset===key)return;board.dataset.asset=key;board.replaceChildren();
    if(game==='pool'||game==='tablesoccer'){
      const mirrored=el('div',`sd-waiting-mirror ${game==='pool'?'pool':'soccer'}`);
      const source=game==='pool'?`/images/themes/${theme}.webp`:'/games/tablesoccer/images/field-img-standard.png';
      for(let i=0;i<(game==='pool'?4:2);i++){const image=el('img','');image.src=source;image.alt='';mirrored.append(image);}board.append(mirrored);
    }else{
      const image=el('img','sd-waiting-board');image.src=game==='carrom'?`/images/themes/${carromTheme}-preview.webp`:'/games/crazy8/images/table-background.webp';image.alt='';board.append(image);
    }
    fitBoard();
  }
  function playerNode(player){
    const button=el('button','sd-waiting-player');button.type='button';button.dataset.seat=String(player.seat);button.dataset.connected=String(player.connected!==false);
    button.setAttribute('aria-label',`بطاقة ${player.name}`);
    const img=el('img','');img.alt='';img.src=player.accountId?`/api/avatar/${encodeURIComponent(player.accountId)}`:'/images/default-avatar.png';
    img.onerror=()=>{img.onerror=null;img.src='/images/default-avatar.png';};
    const identity=el('span','sd-waiting-identity');const playerName=el('span','sd-waiting-name',player.name);playerName.title=player.name;const status=el('small','sd-waiting-status',player.connected===false?'غير متصل':'متصل');identity.append(playerName,status);button.append(img,identity);
    button.onclick=()=>{
      if(window.SamiDevMobile?.postMessage&&player.accountId){window.SamiDevMobile.postMessage(JSON.stringify({type:'open_player_profile',userId:player.accountId}));}
      else window.SamiDevPlayerProfileUI?.openSeat?.(player.seat);
    };return button;
  }
  function update(message){
    if(complete)return;show();const st=window.SamiDevNetwork.state;
    // Only actual occupied server seats. No placeholder opponent/name/avatar.
    own.replaceChildren();opponents.replaceChildren();
    for(const player of st.roster||[]){if(!player?.name)continue;(Number(player.seat)===Number(st.seat)?own:opponents).append(playerNode(player));}
    renderBoard(message);
    label.textContent=st.started?'تجهيز الطاولة…':'بانتظار انضمام الخصم…';
  }
  function show(){if(complete)return;build();root.hidden=false;document.body.classList.add('sd-waiting');}
  window.SamiDevWaitingRoom={
    show,
    progress(text){show();if(!complete)label.textContent=/انتظار|بانتظار|Player|الغرفة/.test(String(text))?'بانتظار انضمام الخصم…':String(text);},
    ready(){complete=true;resizeObserver?.disconnect();themeObserver?.disconnect();if(root)root.remove();document.body.classList.remove('sd-waiting');},
    fail(text){if(!root)return;label.textContent=String(text);label.classList.add('error');},
  };
  window.SamiDevNetwork.on('assignment',update);
  window.SamiDevNetwork.on('room_state',update);
  // Match the account's equipped carrom skin; a failed optional lookup never
  // delays the table or weakens authentication/authoritative game startup.
  if(game==='carrom')window.SamiDevNetwork.on('assignment',()=>{
    fetch('/api/store',{credentials:'same-origin'}).then(r=>r.ok?r.json():null).then(data=>{
      carromTheme=data?.equipped?.carrom_theme==='carrom_cat'?'cat':'classic';if(!complete)renderBoard({});
    }).catch(()=>{});
  });
})();
