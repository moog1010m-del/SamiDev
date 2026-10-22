(() => {
  'use strict';
  const games = [['carrom','الكيرم'],['crazy8','بلازر أونو'],['pool','البلياردو'],['tablesoccer','الكورة']];
  const previews = new Set(['/images/effects/plazr-water-preview.webp','badge_shard','badge_ember','badge_moonstone','banner_dunes','banner_garden','banner_canyon','chat_turquoise','chat_mist','chat_ember'].map(id=>'/platform/assets/cosmetics/'+id+'.webp'));
  for(const asset of ['/images/cues/classic-preview.webp','/images/cues/moon-preview.webp','/images/themes/classic-preview.webp','/images/themes/cat-preview.webp','/images/themes/pool-midnight-preview.webp','/images/themes/pool-emerald-preview.webp','/games/crazy8/images/table-background.webp','/games/tablesoccer/images/thumbnail-standard.png'])previews.add(asset);
  let current = window.SamiDevGames.current().id, state, pending = false, previousFocus, requestEpoch = 0;
  const node = (tag, className, value) => { const e=document.createElement(tag); if(className)e.className=className; if(value)e.textContent=value; return e; };
  const trigger=node('button','sd-inventory-trigger');trigger.innerHTML='<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round" aria-hidden="true"><path d="m12 3 8 4.5v9L12 21l-8-4.5v-9L12 3Z"/><path d="m4 7.5 8 4.5 8-4.5M12 12v9M8 5.3l8 4.5"/></svg>';trigger.setAttribute('aria-label','مقتنياتي');trigger.title='مقتنياتي';trigger.type='button';trigger.setAttribute('aria-haspopup','dialog');
  const overlay=node('div','sd-inventory');overlay.hidden=true;
  const panel=node('section','sd-inventory-panel');panel.setAttribute('role','dialog');panel.setAttribute('aria-modal','true');panel.setAttribute('aria-labelledby','sd-inventory-title');panel.tabIndex=-1;
  const header=node('div','sd-inventory-header'), heading=node('h2',null,'مقتنياتي');heading.id='sd-inventory-title';
  const close=node('button',null,'×');close.setAttribute('aria-label','إغلاق المقتنيات');header.append(heading,close);
  const tabs=node('div','sd-inventory-tabs'),status=node('p','sd-inventory-status');status.setAttribute('role','status');
  const body=node('div','sd-inventory-body'),note=node('div','sd-inventory-note','هنا مقتنيات اللعبة الحالية فقط. ثيم البلياردو والمضرب ومؤثر الجيب تظهر للجميع في دور صاحبها.');
  // The active room owns the inventory context; never expose other games' items.
  const activeGame = () => window.SamiDevGames.current().id;
  current = activeGame();
  for(const [id,label] of games){const b=node('button',null,label);b.dataset.game=id;b.disabled=true;tabs.append(b);}
  function syncGame(){current=activeGame();for(const b of tabs.children)b.hidden=b.dataset.game!==current;}
  panel.append(header,tabs,status,body,note);overlay.append(panel);document.body.append(trigger,overlay);if(document.getElementById('sd-room-ui'))trigger.hidden=true;
  async function request(path, options={}) {const response=await fetch(path,{credentials:'same-origin',cache:'no-store',...options});const data=await response.json();if(!response.ok || data.ok===false)throw Error(data.message||'تعذر تحميل المقتنيات');return data;}
  function render(){
    syncGame();for(const b of tabs.children)b.setAttribute('aria-pressed',String(b.dataset.game===current));body.replaceChildren();
    if(!state)return;const items=(Array.isArray(state.catalog)?state.catalog:[]).filter(x=>x && x.gameId===current && !x.default && (x.owned===true||x.availableToAll===true));
    if(!items.length){body.append(node('p',null,'لا توجد مقتنيات متاحة لهذه اللعبة حاليًا.'));return;}
    const grid=node('div','sd-inventory-grid');
    for(const item of items){const card=node('article','sd-inventory-card');if(window.SamiDevStickerArt?.productMarkup){const preview=document.createElement('template');preview.innerHTML=window.SamiDevStickerArt.productMarkup(item);card.append(preview.content.cloneNode(true));}else if(previews.has(item.asset)){const img=node('img');img.src=item.asset;img.alt=item.name;img.loading='lazy';card.append(img);}
      const info=node('div'),title=node('h3',null,item.name),desc=node('p',null,item.description);
      const equipped=state.equipped?.[item.slot]===item.id;card.classList.toggle('is-equipped',equipped);const button=node('button',equipped?'':'sd-inventory-equip',equipped?'إزالة':'استخدام');button.disabled=pending;
      button.onclick=async()=>{const gameAtClick=activeGame();if(pending||overlay.hidden||(item.gameId&&item.gameId!==gameAtClick))return;const targetId=equipped?(state.catalog||[]).find(x=>x.slot===item.slot&&x.default)?.id:item.id;if(!targetId){status.textContent='تعذر تحديد الإعداد الافتراضي';return;}const epoch=++requestEpoch;pending=true;render();status.textContent='جارٍ حفظ اختيارك…';try{await request('/api/store/equip',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({itemId:targetId,gameId:item.gameId||''})});const fresh=await request('/api/store');if(epoch!==requestEpoch||overlay.hidden||activeGame()!==gameAtClick)return;state=fresh;if(gameAtClick==='pool')window.SamiDevNetwork?.send({type:'refresh_cosmetics'});status.textContent=item.gameId==='pool'?'تم الحفظ؛ تظهر مقتنياتك في دورك.':'تم حفظ اختيارك للمرة القادمة.';}catch(e){if(epoch===requestEpoch&&!overlay.hidden)status.textContent=e.message;}finally{if(epoch===requestEpoch){pending=false;if(!overlay.hidden)render();}}};
      info.append(title,desc,button);card.append(info);grid.append(card);
    }body.append(grid);
  }
  function hide(){++requestEpoch;pending=false;overlay.hidden=true;previousFocus?.focus();}
  async function open(){syncGame();const gameAtOpen=current,epoch=++requestEpoch;previousFocus=document.activeElement;overlay.hidden=false;panel.focus();state=null;status.textContent='تحميل مقتنياتك…';render();try{const fresh=await request('/api/store');if(epoch!==requestEpoch||overlay.hidden||activeGame()!==gameAtOpen)return;state=fresh;status.textContent='';render();}catch(e){if(epoch===requestEpoch&&!overlay.hidden)status.textContent=e.message;}}
  trigger.onclick=open;close.onclick=hide;overlay.onclick=e=>{if(e.target===overlay)hide();};
  overlay.addEventListener('keydown',e=>{if(e.key==='Escape'){e.preventDefault();hide();}if(e.key==='Tab'){const list=[...panel.querySelectorAll('button:not(:disabled)')];const first=list[0],last=list.at(-1);if(e.shiftKey&&(document.activeElement===first||document.activeElement===panel)){e.preventDefault();last?.focus();}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus();}}});
  window.SamiDevInventory={open,close:hide};
})();
