(() => {
 'use strict';
 if(!('serviceWorker' in navigator)||!isSecureContext||window.SamiDevMobile||window.__SAMIDEV_MOBILE_APP)return;
 async function warm(){
  try{
   const registration=await navigator.serviceWorker.register('/asset-worker.js',{scope:'/',updateViaCache:'none'});
   await navigator.serviceWorker.ready;
   // Cache requested assets on demand. Never download the complete catalogue
   // just because the lobby is open. Also pause an older active worker while
   // its replacement waits for existing game tabs to close.
   const pause=()=>{
    const workers=new Set([registration.active,registration.waiting,navigator.serviceWorker.controller]);
    for(const worker of workers)worker?.postMessage({type:'pause-warming'});
   };
   navigator.serviceWorker.addEventListener('controllerchange',pause);
   document.addEventListener('visibilitychange',pause);
   pause();
  }catch{/* Unsupported browsers and private storage retain normal game loading. */}
 }
 window.addEventListener('load',()=>{if('requestIdleCallback' in window)requestIdleCallback(warm,{timeout:5000});else setTimeout(warm,1500);},{once:true});
})();
