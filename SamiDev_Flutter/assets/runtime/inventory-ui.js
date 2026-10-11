(() => {
  'use strict';
  const games = [['carrom','الكيرم'],['crazy8','كريزي 8'],['pool','البلياردو'],['tablesoccer','الكورة']];
  const previews = new Set(['/images/cues/classic-preview.webp','/images/cues/moon-preview.webp','/images/themes/classic-preview.webp','/images/themes/cat-preview.webp','/images/themes/pool-midnight-preview.webp','/images/themes/pool-emerald-preview.webp','/games/crazy8/images/table-background.webp','/games/tablesoccer/images/thumbnail-standard.png']);
  let current = window.SamiDevGames.current().id, state, pending = false, previousFocus, requestEpoch = 0;
  const node = (tag, className, value) => { const e=document.createElement(tag); if(className)e.className=className; if(value)e.textContent=value; return e; };
  const trigger=node('button','sd-inventory-trigger','مقتنياتي');trigger.type='button';trigger.setAttribute('aria-haspopup','dialog');
  const overlay=node('div','sd-inventory');overlay.hidden=true;
  const panel=node('section','sd-inventory-panel');panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');panel.setAttribute('aria-labelledby','sd-inventory-title');panel.tabIndex=-1;
  const header=node('div','sd-inventory-header'), heading=node('h2',null,'مقتنياتي');heading.id='sd-inventory-title';
  const close=node('button',null,'×');close.setAttribute('aria-label','إغلاق المقتنيات');header.append(heading,close);
  const tabs=node('div','sd-inventory-tabs'),status=node('p','sd-inventory-status');status.setAttribute('role','status');
  const body=node('div','sd-inventory-body'),note=node('div','sd-inventory-note','ثيم البلياردو والمضرب يظهران للجميع في دور صاحبهما. بقية المقتنيات تُطبّق عند دخول اللعبة من جديد.');
  // The active room owns the inventory context; never expose other games' items.
  const activeGame = () => window.SamiDevGames.current().id;
  current = activeGame();
  for(const [id,label] of games){const b=node('button',null,label);b.dataset.game=id;b.disabled=true;tabs.append(b);}
  function syncGame(){current=activeGame();for(const b of tabs.children)b.hidden=b.dataset.game!==current;}
  panel.append(header,tabs,status,body,note);overlay.append(panel);document.body.append(trigger,overlay);if(document.getElementById('sd-room-ui'))trigger.hidden=true;
  async function request(path, options={}) {const response=await fetch(path,{credentials:'same-origin',cache:'no-store',...options});const data=await response.json();if(!response.ok || data.ok===false)throw Error(data.message||'تعذر تحميل المقتنيات');return data;}
  function render(){
    syncGame();for(const b of tabs.children)b.setAttribute('aria-pressed',String(b.dataset.game===current));body.replaceChildren();
    if(!state)return;const items=(Array.isArray(state.catalog)?state.catalog:[]).filter(x=>x && x.gameId===current && x.owned===true);
    if(!items.length){body.append(node('p',null,'لا توجد مقتنيات متاحة لهذه اللعبة حاليًا.'));return;}
    const grid=node('div','sd-inventory-grid');
    for(const item of items){const card=node('article','sd-inventory-card');if(previews.has(item.asset)){const img=node('img');img.src=item.asset;img.alt='';img.loading='lazy';card.append(img);}
      const info=node('div'),title=node('h3',null,item.name),desc=node('p',null,item.description);
      const equipped=state.equipped?.[item.slot]===item.id;const button=node('button',equipped?'':'sd-inventory-equip',equipped?'مستخدم الآن':'استخدام');button.disabled=pending||equipped;
      button.onclick=async()=>{const gameAtClick=activeGame();if(pending||overlay.hidden||item.gameId!==gameAtClick)return;const epoch=++requestEpoch;pending=true;render();status.textContent='جارٍ حفظ اختيارك…';try{await request('/api/store/equip',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({itemId:item.id,gameId:gameAtClick})});const fresh=await request('/api/store');if(epoch!==requestEpoch||overlay.hidden||activeGame()!==gameAtClick)return;state=fresh;if(gameAtClick==='pool')window.SamiDevNetwork?.send({type:'refresh_cosmetics'});status.textContent=item.gameId==='pool'?'تم الحفظ؛ تظهر مقتنياتك في دورك.':'تم حفظ اختيارك للمرة القادمة.';}catch(e){if(epoch===requestEpoch&&!overlay.hidden)status.textContent=e.message;}finally{if(epoch===requestEpoch){pending=false;if(!overlay.hidden)render();}}};
      info.append(title,desc,button);card.append(info);grid.append(card);
    }body.append(grid);
  }
  function hide(){++requestEpoch;pending=false;overlay.hidden=true;previousFocus?.focus();}
  async function open(){syncGame();const gameAtOpen=current,epoch=++requestEpoch;previousFocus=document.activeElement;overlay.hidden=false;panel.focus();state=null;status.textContent='تحميل مقتنياتك…';render();try{const fresh=await request('/api/store');if(epoch!==requestEpoch||overlay.hidden||activeGame()!==gameAtOpen)return;state=fresh;status.textContent='';render();}catch(e){if(epoch===requestEpoch&&!overlay.hidden)status.textContent=e.message;}}
  trigger.onclick=open;close.onclick=hide;overlay.onclick=e=>{if(e.target===overlay)hide();};
  overlay.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();hide();}if(e.key==='Tab'){const list=[...panel.querySelectorAll('button:not(:disabled)')];const first=list[0],last=list.at(-1);if(e.shiftKey&&(document.activeElement===first||document.activeElement===panel)){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}}});
  window.SamiDevInventory={open,close:hide};
})();
