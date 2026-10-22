/* Plazr result presentation. Ranking and best-shot replay remain native. */
(()=>{'use strict';
 function ranking(logic){const raw=logic.gameOverState?.order||[];return raw.flatMap((group,index)=>(Array.isArray(group)?group:[group]).filter(Number.isInteger).map(seat=>({seat,rank:index+1})));}
 function create({canvas,getLogic,getRoster,onInvalidate}){
  let root=null,card=null,rows=null,replay=null,again=null,disposed=false,collapsed=false,lastSignature='',nativePopup=null,nativeVisible=null;
  const style=document.createElement('style');style.textContent=`
  .plazr-result{--surface:#fff;--ink:#284044;--muted:#718381;--line:#d3dfdc;--panel:#f0f5f3;position:fixed;z-index:30;display:grid;place-items:center;box-sizing:border-box;padding:20px;background:#07191c44;font-family:system-ui,sans-serif;direction:rtl;color:var(--ink)}
  .plazr-result[data-theme=dark]{--surface:#12242b;--ink:#ecf2ec;--muted:#9dafaf;--line:#334b50;--panel:#1c3339;background:#03101466}
  .plazr-result[hidden],.plazr-result-reopen[hidden]{display:none!important}
  .plazr-result-card{position:relative;width:min(380px,100%);max-height:100%;overflow:auto;border:1px solid #b9a574;border-radius:16px;background:var(--surface);box-shadow:0 18px 50px #0004;text-align:center;box-sizing:border-box}
  .plazr-result-head{padding:20px 35px 16px;background:linear-gradient(110deg,#c5ad6b20,#cfba7d0b);border-bottom:1px solid var(--line)}
  .plazr-result-head small{color:var(--muted);font-size:11px}.plazr-result-head h2{font-size:23px;margin:5px 0 0;color:var(--ink)}
  .plazr-result-close{position:absolute;left:10px;top:10px;border:0;background:transparent;color:var(--muted);font-size:24px;cursor:pointer}
  .plazr-result-rows{padding:12px 18px;display:grid;gap:8px}.plazr-result-player{display:flex;align-items:center;gap:12px;text-align:start;padding:10px 12px;border:1px solid var(--line);border-radius:10px;background:var(--panel)}
  .plazr-result-player:first-child{border-color:#b8a06a}.plazr-result-player img{width:42px;height:42px;object-fit:cover;border-radius:50%;border:1px solid var(--line)}
  .plazr-result-player b{font-size:15px;overflow-wrap:anywhere;flex:1}.plazr-result-rank{color:#b19047;font-size:20px;font-weight:750}
  .plazr-result-replay{margin:0 18px 15px;padding:14px;border:1px solid var(--line);border-radius:11px;background:var(--panel)}.plazr-result-replay strong{display:block;font-size:14px}.plazr-result-replay small{display:block;color:var(--muted);font-size:11px;margin:6px 0 12px;line-height:1.5}
  .plazr-result button{font-family:inherit}.plazr-result-watch{border:1px solid #bda36a;border-radius:7px;padding:9px 20px;background:linear-gradient(#dfcc96,#c6ac70);color:#253d40;font-size:13px;font-weight:700;cursor:pointer}.plazr-result-watch:disabled{opacity:.5;cursor:default}
  .plazr-result-return{margin:0 18px 18px;padding:9px 14px;border:1px solid var(--line);border-radius:7px;background:none;color:var(--ink);cursor:pointer;font-size:12px}
  .plazr-result-reopen{position:fixed;z-index:29;bottom:18px;left:18px;border:1px solid #a98e52;border-radius:8px;padding:9px 14px;background:#17333b;color:#f0dfb4;font:13px system-ui;cursor:pointer}
  `;document.head.appendChild(style);
  function build(){
   root=document.createElement('div');root.className='plazr-result';root.setAttribute('role','dialog');root.setAttribute('aria-label','نتيجة المباراة');root.hidden=true;
   card=document.createElement('section');card.className='plazr-result-card';
   const header=document.createElement('header');header.className='plazr-result-head';header.innerHTML='<small>PLAZR · بلازر</small><h2>انتهت المباراة</h2>';
   const close=document.createElement('button');close.className='plazr-result-close';close.type='button';close.textContent='×';close.setAttribute('aria-label','عرض الطاولة');close.onclick=()=>{collapsed=true;root.hidden=true;again.hidden=false;};header.append(close);
   rows=document.createElement('div');rows.className='plazr-result-rows';rows.setAttribute('aria-label','ترتيب اللاعبين');
   const feature=document.createElement('section');feature.className='plazr-result-replay';feature.innerHTML='<strong>أفضل لقطة في المباراة</strong><small></small>';
   replay=document.createElement('button');replay.type='button';replay.className='plazr-result-watch';replay.textContent='▶ مشاهدة اللقطة';replay.onclick=()=>{const s=getLogic()?.sceneMgr;if(!s?.showShotOfTheGame||s.shotOfTheGameShowing)return;root.hidden=true;s.showShotOfTheGame();onInvalidate();};feature.append(replay);
   const back=document.createElement('button');back.className='plazr-result-return';back.type='button';back.textContent='العودة للمساحة';back.onclick=()=>window.SamiDevRoomUI?.returnToCommunity?.();
   card.append(header,rows,feature,back);root.append(card);document.body.append(root);
   again=document.createElement('button');again.className='plazr-result-reopen';again.type='button';again.textContent='نتيجة المباراة';again.hidden=true;again.onclick=()=>{collapsed=false;onInvalidate();};document.body.append(again);
  }
  function frame(){
   if(disposed)return;const g=getLogic(),s=g?.sceneMgr;
   if(!g?.gameOver||!s?.gameOverPopup){if(root)root.hidden=true;if(again)again.hidden=true;return;}
   if(!root)build();
   if(nativePopup!==s.gameOverPopup){
    nativePopup=s.gameOverPopup;nativeVisible=Object.getOwnPropertyDescriptor(nativePopup,'visible');
    // Native replay writes visible=true when finishing; keep only the new card.
    Object.defineProperty(nativePopup,'visible',{configurable:true,get:()=>false,set:()=>{}});
   }
   s.gameOverPopup.enableInput?.(false);
   const playing=!!s.shotOfTheGameShowing||!!g.animatingShotOfTheGame;
   root.hidden=playing||collapsed;again.hidden=playing||!collapsed;
   const rect=canvas.getBoundingClientRect();Object.assign(root.style,{left:rect.left+'px',top:rect.top+'px',width:rect.width+'px',height:rect.height+'px'});
   let theme='dark';try{theme=window.parent.document.documentElement.dataset.theme||localStorage.getItem('samidev_theme')||'dark';}catch(_){}root.dataset.theme=theme;
   const players=getRoster()||[],order=ranking(g),shot=g.shotOfTheGame;
   const signature=JSON.stringify([order,players.map(p=>[p.seat,p.name,p.accountId]),shot?.seat,shot?.score]);
   if(signature!==lastSignature){lastSignature=signature;rows.replaceChildren();
    for(const p of order){const user=players.find(u=>u.seat===p.seat),row=document.createElement('div');row.className='plazr-result-player';const rank=document.createElement('span');rank.className='plazr-result-rank';rank.textContent=String(p.rank);const image=document.createElement('img');image.alt='';image.src=user?.accountId?'/api/avatar/'+encodeURIComponent(user.accountId):'/images/default-avatar-v2.png';image.onerror=()=>{image.onerror=null;image.src='/images/default-avatar-v2.png';};const name=document.createElement('b');name.dir='auto';name.textContent=user?.name||g.sceneMgr?.avatars?.get?.(p.seat)?.oldNameTextContents||'اللاعب '+(p.seat+1);row.append(rank,image,name);rows.append(row);}
    const available=Number.isInteger(shot?.seat)&&shot.seat>=0&&!!shot.ballPositions?.length;replay.disabled=!available;
    card.querySelector('.plazr-result-replay small').textContent=available?'أعد مشاهدة أفضل ضربة مسجلة خلال هذه المباراة':'لا توجد لقطة مسجلة في هذه المباراة';
   }
  }
  return {frame,dispose(){disposed=true;if(nativePopup){if(nativeVisible)Object.defineProperty(nativePopup,'visible',nativeVisible);else delete nativePopup.visible;}root?.remove();again?.remove();style.remove();}};
 }
 window.PlazrPoolResult={create,ranking};
})();
