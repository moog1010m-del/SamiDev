'use strict';
const CACHE='samidev-game-assets-'+VERSION;
const pending=new Map();
async function asset(path){
 const cache=await caches.open(CACHE),key=new URL(path,self.location.origin).href;
 const hit=await cache.match(key);if(hit)return hit;
 if(pending.has(path))return (await pending.get(path)).clone();
 const task=(async()=>{
  const response=await fetch(key,{cache:'no-store',credentials:'omit',redirect:'error'});
  if(!response.ok||response.type==='opaque')throw Error('Asset unavailable');
  const bytes=await response.clone().arrayBuffer();
  const digest=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),n=>n.toString(16).padStart(2,'0')).join('');
  if(digest!==CONTRACT.files[path])throw Error('Asset version mismatch');
  try{await cache.put(key,response.clone());}catch{/* Quota/private-mode failure must not refetch a valid download. */}
  return response;
 })();pending.set(path,task);
 try{return (await task).clone();}finally{pending.delete(path);}
}
self.addEventListener('activate',event=>event.waitUntil((async()=>{
 for(const key of await caches.keys())if(key.startsWith('samidev-game-assets-')&&key!==CACHE)await caches.delete(key);
 await self.clients.claim();
})()));
// Updates deliberately wait for existing tabs to close: never mix game builds.
self.addEventListener('fetch',event=>{
 const url=new URL(event.request.url);
 if(event.request.method!=='GET'||url.origin!==self.location.origin||!Object.hasOwn(CONTRACT.files,url.pathname)||event.request.headers.has('range'))return;
 event.respondWith(asset(url.pathname).catch(()=>fetch(event.request)));
});
let warming=false,paused=false;
self.addEventListener('message',event=>{
 if(event.data?.type==='pause-warming'){paused=true;return;}
 if(event.data?.type!=='warm-games')return;
 paused=false;
 if(warming)return;
 warming=true;
 event.waitUntil((async()=>{
  const order=[event.data.preferred,...Object.keys(CONTRACT.groups)].filter((id,i,a)=>CONTRACT.groups[id]&&a.indexOf(id)===i);
  const paths=[...new Set(order.flatMap(id=>CONTRACT.groups[id]))];
  // Two downloads, no game runtime, physics, rendering, or game connections.
  await Promise.all([0,1].map(async()=>{while(paths.length&&!paused){const path=paths.shift();try{await asset(path);}catch{/* Real entry retries unavailable assets. */}}}));
 })().finally(()=>{warming=false;}));
});
