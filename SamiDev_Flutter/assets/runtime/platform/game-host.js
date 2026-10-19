(() => {
 'use strict';
 let active=null,opening=false;
 const origin=location.origin;
 async function close(){
  const current=active;if(!current)return;active=null;clearTimeout(current.timeout);current.rejectReady?.(Error('أُغلقت الطاولة'));window.PlazrGameEntry?.finish();
  try{current.frame.contentWindow.SamiDevGameRuntime?.dispose();}catch(_){}
  current.frame.remove();document.body.classList.remove('sd-web-game','sd-game-opening');
  document.getElementById('app')?.removeAttribute('inert');document.getElementById('open-create')?.removeAttribute('aria-busy');
  await current.onReturn?.();
 }
 async function open(id,params,{onReturn,onAssignment}={}){
  if(!['carrom','pool','crazy8','tablesoccer'].includes(id))throw Error('لعبة غير معروفة');
  if(opening||active)throw Error('أغلق المباراة الحالية أولًا');
  opening=true;window.PlazrGameEntry?.loading({game:id,room:params.get('room')||'',watch:params.get('action')==='watch'});
  try{localStorage.setItem("samidev_last_game",id);}catch{}
  const frame=document.createElement('iframe');frame.id='sd-game-host';frame.title=window.SamiDevGames.get(id).name;frame.allow='autoplay; fullscreen';
  frame.style.cssText='position:fixed;inset:0;width:100%;height:100%;border:0;z-index:20000;background:#171717;opacity:0;pointer-events:none';
  frame.src='about:blank';
  document.body.classList.remove('sd-web-game');document.body.classList.add('sd-game-opening');document.getElementById('app')?.setAttribute('inert','');document.getElementById('open-create')?.setAttribute('aria-busy','true');document.body.append(frame);
  let acceptReady,rejectReady;const ready=new Promise((resolve,reject)=>{acceptReady=resolve;rejectReady=reject;});ready.catch(()=>{});
  const timeout=setTimeout(()=>rejectReady(Error('تعذر فتح الطاولة. حاول مجددًا.')),45000);
  active={frame,id,onReturn,onAssignment,assigned:false,surface:false,rejectReady,timeout};
  try{
   const child=frame.contentWindow,doc=frame.contentDocument;
   doc.open();doc.write('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,minimum-scale=1,maximum-scale=1,user-scalable=no,viewport-fit=cover"></head><body></body></html>');doc.close();
   child.__SAMIDEV_EMBEDDED_GAME=true;child.__SAMIDEV_APP_ORIGIN=origin;
   const reveal=()=>{if(active?.frame!==frame)return;active.surface=true;if(params.get('online')==='1'&&!active.assigned)return;clearTimeout(timeout);acceptReady();window.PlazrGameEntry?.finish();frame.style.opacity='1';frame.style.pointerEvents='auto';document.body.classList.remove('sd-game-opening');document.body.classList.add('sd-web-game');document.getElementById('app')?.removeAttribute('inert');document.getElementById('open-create')?.removeAttribute('aria-busy');child.focus();};
   const fail=error=>{if(active?.frame!==frame||frame.style.opacity!=='0')return;clearTimeout(timeout);rejectReady(Object.assign(new Error(error?.code==='MATCH_COOLDOWN'?'حاول بعد دقيقة':'تعذر فتح الطاولة. حاول مجددًا.'),{code:error?.code}));};
   child.addEventListener('error',()=>fail());
   child.__SAMIDEV_APP_HOST={surfaceReady:reveal,startupError:fail,returnToPlatform:close,assigned:message=>{if(active?.frame!==frame||!message?.roomId)return;active.assigned=true;onAssignment?.(message);if(active.surface)reveal();},
    reconnect:()=>{if(active?.frame===frame)return reconnect();},
    openGame:async(gid,q)=>{const response=await fetch('/api/game-ticket',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({communityId:q.get('community')||'majlis'})});if(!response.ok)throw Error('تعذر تجديد الاتصال');q.set('ticket',(await response.json()).ticket);await close();return open(gid,q,{onReturn,onAssignment});}};
   const bootstrap=doc.createElement('script');bootstrap.src=origin+'/game-bootstrap.js';
   await new Promise((resolve,reject)=>{bootstrap.onload=resolve;bootstrap.onerror=()=>reject(Error('تعذر تجهيز اللعبة'));doc.body.append(bootstrap);});
   await child.SamiDevGameBootstrap.start(id,params.toString());
   await ready;
   if(frame.style.opacity==='1')child.focus();
  }catch(error){try{await close();}catch(_){}window.PlazrGameEntry?.fail(error);throw error;}finally{clearTimeout(timeout);opening=false;}
 }
 async function reconnect(){
  const current=active;if(!current||opening)return;
  const state=current.frame.contentWindow.SamiDevNetwork?.state;if(!state?.roomId)return;
  const response=await fetch('/api/game-ticket',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({communityId:state.communityId||'majlis'})});
  if(!response.ok)throw Error('تعذر تجديد الاتصال');
  const params=new URLSearchParams({online:'1',action:state.spectator?'watch':'join',room:state.roomId,community:state.communityId||'majlis',ticket:(await response.json()).ticket});
  if(state.token)params.set('token',state.token);
  if(active!==current)return;
  active=null;current.frame.contentWindow.SamiDevGameRuntime?.dispose();current.frame.remove();
  return open(current.id,params,current);
 }
 window.SamiDevGameHost={open,close,get active(){return active;}};
 const style=document.createElement('style');style.textContent='body.sd-web-game #app,body.sd-web-game #create-modal{display:none!important}';document.head.append(style);
})();
