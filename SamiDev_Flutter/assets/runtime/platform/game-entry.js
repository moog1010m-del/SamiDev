(() => {
 'use strict';
 let current=null;
 const names={pool:'البلياردو',carrom:'الكيرم',crazy8:'أونو',tablesoccer:'كرة الطاولة'};
 const artwork={pool:'pool',carrom:'carrom',crazy8:'cards',tablesoccer:'football'};
 function finish(){
  if(!current)return;
  const old=current;current=null;old.element.remove();document.removeEventListener('keydown',old.key);
  old.resolve?.(false);if(old.origin?.isConnected&&!document.body.classList.contains('sd-web-game'))old.origin.focus({preventScroll:true});
 }
 function make({game='carrom',room='',description='',watch=false}={}){
  const element=document.createElement('div');element.className='game-entry-overlay';element.id='game-entry-overlay';
  element.innerHTML='<section class="game-entry-sheet" role="dialog" aria-modal="true" aria-labelledby="game-entry-title"><header><img class="game-entry-art" alt="" width="58" height="58"><div><small class="game-entry-room"></small><h3 id="game-entry-title"></h3></div></header><p class="game-entry-description"></p><div class="game-entry-loading" role="status" aria-live="polite" hidden><span class="game-entry-spinner" aria-hidden="true"></span><span>نجهّز طاولتك…</span><small>بتدخل تلقائيًا عند جاهزيتها</small></div><p class="game-entry-error" role="alert" hidden></p><footer><button type="button" class="primary" data-entry-confirm></button><button type="button" class="ghost" data-entry-cancel>إلغاء</button></footer></section>';
  const sheet=element.firstElementChild;
  sheet.querySelector('img').src='/room-sprites/'+(artwork[game]||'carrom')+'.png';
  sheet.querySelector('h3').textContent=names[game]||'المباراة';
  sheet.querySelector('.game-entry-room').textContent=room?'الطاولة '+room:'طاولة جديدة';
  sheet.querySelector('.game-entry-description').textContent=description|| (watch?'تبي تدخل لمشاهدة المباراة؟':'جاهز تنضم للطاولة؟');
  sheet.querySelector('[data-entry-confirm]').textContent=watch?'مشاهدة':'انضم';
  const state={element,origin:document.activeElement,busy:false,resolve:null};current=state;
  const cancel=()=>{if(!state.busy)finish();};
  sheet.querySelector('[data-entry-cancel]').onclick=cancel;
  element.onclick=e=>{if(e.target===element)cancel();};
  state.key=e=>{
   if(e.key==='Escape'){e.preventDefault();cancel();}
   if(e.key==='Tab'){const buttons=[...sheet.querySelectorAll('button:not(:disabled)')].filter(b=>!b.hidden);if(!buttons.length){e.preventDefault();return;}if(e.shiftKey&&document.activeElement===buttons[0]){e.preventDefault();buttons.at(-1).focus();}else if(!e.shiftKey&&document.activeElement===buttons.at(-1)){e.preventDefault();buttons[0].focus();}}
  };
  document.addEventListener('keydown',state.key);document.body.append(element);return state;
 }
 function confirm(options){
  if(current)return Promise.resolve(false);
  const state=make(options);
  return new Promise(resolve=>{state.resolve=resolve;state.element.querySelector('[data-entry-confirm]').onclick=()=>{state.resolve=null;loading();resolve(true);};state.element.querySelector('[data-entry-cancel]').focus({preventScroll:true});});
 }
 function loading(options){
  const state=current||make(options);state.busy=true;
  state.element.querySelector('footer').hidden=true;
  state.element.querySelector('.game-entry-loading').hidden=false;
  state.element.querySelector('.game-entry-description').hidden=true;
  state.element.querySelector('.game-entry-error').hidden=true;
  const sheet=state.element.firstElementChild;sheet.setAttribute('aria-busy','true');sheet.tabIndex=-1;sheet.focus({preventScroll:true});
 }
 function fail(error){
  if(!current)return;const state=current;state.busy=false;state.element.firstElementChild.removeAttribute('aria-busy');
  state.element.querySelector('.game-entry-loading').hidden=true;
  const message=state.element.querySelector('.game-entry-error');message.hidden=false;message.textContent=error?.message||'تعذر فتح الطاولة. حاول مجددًا.';
  state.element.querySelector('footer').hidden=false;state.element.querySelector('[data-entry-confirm]').hidden=true;
  const cancel=state.element.querySelector('[data-entry-cancel]');cancel.textContent='رجوع';cancel.focus({preventScroll:true});
 }
 window.PlazrGameEntry={confirm,loading,finish,fail};
})();
