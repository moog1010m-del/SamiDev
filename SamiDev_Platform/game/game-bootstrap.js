(() => {
 'use strict';
 const ids={carrom:'/',pool:'/games/pool/',crazy8:'/games/crazy8/',tablesoccer:'/games/tablesoccer/'};
 let attempt=null;
 function script(src){return new Promise((resolve,reject)=>{const el=document.createElement('script');el.src=src;el.async=false;el.onload=resolve;el.onerror=()=>reject(Error('تعذر تحميل ملفات اللعبة'));document.body.append(el);});}
 async function start(id,query){
  if(!Object.hasOwn(ids,id))throw Error('لعبة غير معروفة');
  if(attempt)return attempt;
  attempt=(async()=>{
   const origin=window.__SAMIDEV_APP_ORIGIN||location.origin;
   const response=await fetch(origin+'/runtime-games.json',{credentials:'same-origin'});if(!response.ok)throw Error('تعذر تحميل إعدادات اللعبة');
   const data=(await response.json())[id];if(!data||data.root!==ids[id])throw Error('إعدادات اللعبة غير صالحة');
   const root=new URL(data.root,origin);
   window.__SAMIDEV_ASSET_ROOT=root.href;
   window.__SAMIDEV_GAME_ID=id;
   // Only embedded SPA frames need a query override. Standalone/native pages
   // must retain the room URL updates used by their reload/resume lifecycle.
   if(window.__SAMIDEV_EMBEDDED_GAME)window.__SAMIDEV_QUERY=String(query).replace(/^\?/,'');
   window.__dictEn=data.dictionary;window.__assetImages=data.images;
   const style=document.createElement('style');style.textContent='html,body{margin:0;width:100%;height:100%;overflow:hidden;background:#171717}#game{position:fixed;inset:0;width:100vw;height:100vh;display:block}#status{position:fixed;z-index:10;left:16px;right:16px;top:16px;padding:12px 14px;border-radius:10px;background:#fff;color:#111;font:14px/1.5 Arial;white-space:pre-wrap}';document.head.append(style);
   if(!document.getElementById('game')){const canvas=document.createElement('canvas');canvas.id='game';document.body.append(canvas);}
   if(!document.getElementById('status')){const status=document.createElement('div');status.id='status';status.textContent='جارٍ تجهيز اللعبة…';document.body.append(status);}
   for(const href of data.styles){const url=new URL(href,root);if(url.origin!==origin)throw Error('مصدر ملفات غير مسموح');const link=document.createElement('link');link.rel='stylesheet';link.href=url.href;document.head.append(link);}
   // Fetch independent scripts together while preserving their execution order.
   for(const src of data.scripts){const url=new URL(src,root);if(url.origin!==origin)throw Error('مصدر ملفات غير مسموح');if(window.SamiDevMobile&&url.pathname==='/chat-ui.js')continue;const link=document.createElement('link');link.rel='preload';link.as='script';link.href=url.href;document.head.append(link);}
   for(const src of data.scripts){const url=new URL(src,root);if(window.SamiDevMobile&&url.pathname==='/chat-ui.js')continue;if(url.origin!==origin)throw Error('مصدر ملفات غير مسموح');await script(url.href);if(url.pathname==='/browser-runtime.js')window.SamiDevGameRuntime?.preloadResources().catch(()=>{});}
   // WebView page-finished can precede the asynchronous bootstrap. Let the
   // native host reapply its visibility/audio state once the bridge exists.
   window.SamiDevMobile?.postMessage(JSON.stringify({type:'game_runtime_ready'}));
  })();
  return attempt;
 }
 window.SamiDevGameBootstrap={start};
 if(!window.__SAMIDEV_EMBEDDED_GAME){
  const id=Object.keys(ids).find(id=>id!=='carrom'&&location.pathname.startsWith(ids[id]))||'carrom';
  const run=()=>start(id,location.search).catch(error=>{const p=document.createElement('p');p.textContent=error.message;document.body.append(p);});
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',run,{once:true});else run();
 }
})();
