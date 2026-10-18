(() => {
 'use strict';
 if(!('serviceWorker' in navigator)||!isSecureContext||window.SamiDevMobile||window.__SAMIDEV_MOBILE_APP)return;
 const connection=navigator.connection;
 async function warm(){
  try{
   const registration=await navigator.serviceWorker.register('/asset-worker.js',{scope:'/',updateViaCache:'none'});
   await navigator.serviceWorker.ready;
   if(connection?.saveData||/^(slow-)?2g$/.test(connection?.effectiveType||''))return;
   const send=()=>{
    const worker=registration.active||navigator.serviceWorker.controller;
    if(document.hidden||(document.body.classList.contains('sd-web-game')||document.body.classList.contains('sd-game-opening'))){worker?.postMessage({type:'pause-warming'});return;}
    let preferred;try{preferred=localStorage.getItem('samidev_last_game');}catch{}
    worker?.postMessage({type:'warm-games',preferred});
   };
   new MutationObserver(send).observe(document.body,{attributes:true,attributeFilter:['class']});
   document.addEventListener('visibilitychange',send);
   send();
  }catch{/* Unsupported browsers and private storage retain normal game loading. */}
 }
 window.addEventListener('load',()=>{if('requestIdleCallback' in window)requestIdleCallback(warm,{timeout:5000});else setTimeout(warm,1500);},{once:true});
})();
