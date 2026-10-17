(() => {
 'use strict';
 let active=null,opening=false;
 const origin=location.origin;
 async function close(){
  const current=active;if(!current)return;active=null;
  try{current.frame.contentWindow.SamiDevGameRuntime?.dispose();}catch(_){}
  current.frame.remove();document.body.classList.remove('sd-web-game');
  await current.onReturn?.();
 }
 async function open(id,params,{onReturn,onAssignment}={}){
  if(!['carrom','pool','crazy8','tablesoccer'].includes(id))throw Error('لعبة غير معروفة');
  if(opening||active)throw Error('أغلق المباراة الحالية أولًا');
  opening=true;
  const frame=document.createElement('iframe');frame.id='sd-game-host';frame.title=window.SamiDevGames.get(id).name;frame.allow='autoplay; fullscreen';
  frame.style.cssText='position:fixed;inset:0;width:100%;height:100%;border:0;z-index:20000;background:#171717';
  frame.src='about:blank';
  document.body.classList.add('sd-web-game');document.body.append(frame);
  active={frame,id,onReturn,onAssignment};
  try{
   const child=frame.contentWindow,doc=frame.contentDocument;
   doc.open();doc.write('<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"></head><body></body></html>');doc.close();
   child.__SAMIDEV_EMBEDDED_GAME=true;child.__SAMIDEV_APP_ORIGIN=origin;
   child.__SAMIDEV_APP_HOST={returnToPlatform:close,assigned:message=>onAssignment?.(message),
    reconnect:()=>{if(active?.frame===frame)return reconnect();},
    openGame:async(gid,q)=>{const response=await fetch('/api/game-ticket',{method:'POST',credentials:'same-origin',headers:{'Content-Type':'application/json'},body:JSON.stringify({communityId:q.get('community')||'majlis'})});if(!response.ok)throw Error('تعذر تجديد الاتصال');q.set('ticket',(await response.json()).ticket);await close();return open(gid,q,{onReturn,onAssignment});}};
   const bootstrap=doc.createElement('script');bootstrap.src=origin+'/game-bootstrap.js';
   await new Promise((resolve,reject)=>{bootstrap.onload=resolve;bootstrap.onerror=()=>reject(Error('تعذر تجهيز اللعبة'));doc.body.append(bootstrap);});
   await child.SamiDevGameBootstrap.start(id,params.toString());
   child.focus();
  }catch(error){await close();throw error;}finally{opening=false;}
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
