// Real account APIs + actual platform scripts under a DOM implementation; no pixel rendering.
import assert from 'node:assert/strict';
import fs from 'node:fs';
const {Window}=await import(process.env.SAMIDEV_HAPPY_DOM_MODULE||'happy-dom');
const base=process.argv[2],events=[];let cookie='';
async function request(route,options={}){
 const r=await fetch(new URL(route,base),{...options,headers:{...options.headers,Cookie:cookie,Origin:base}});
 const cookies=r.headers.getSetCookie();if(cookies.length)cookie=cookies.map(v=>v.split(';')[0]).join('; ');return r;
}
const registration=await request('/api/auth/register',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:'mobile_ui_test',password:'Test-password-123',displayName:'لاعب الاختبار'})});
assert.equal(registration.status,200);const user=(await registration.json()).user;
const win=new Window({url:base+'/platform/'});
try{
 win.document.documentElement.innerHTML=await (await request('/platform/')).text();
 win.fetch=request;win.SamiDevMobile={postMessage:s=>events.push(JSON.parse(s))};win.alert=()=>{};
 for(const script of win.document.querySelectorAll('script[src]'))win.eval(await(await request(script.getAttribute('src'))).text());
 const until=async(fn)=>{for(let i=0;i<100;i++){if(fn())return;await new Promise(r=>setTimeout(r,20));}assert.fail('DOM did not settle');};
 await until(()=>events.some(x=>x.type==='platform_ready'));
 const bridge=win.SamiDevMobilePlatform;assert(bridge);
 bridge.setNativeActive(true);bridge.setTheme('light');assert.equal(win.document.documentElement.dataset.theme,'light');
 bridge.navigate('friends');assert(win.document.querySelector('#page-friends').classList.contains('active'));
 bridge.navigate('store');await until(()=>win.document.querySelector('.store-item-card')||win.document.querySelector('#store-catalog')?.children.length);
 bridge.navigate('profile');assert.equal(win.document.querySelector('#profile-name').textContent,'لاعب الاختبار');
 bridge.openProfile(user.id);await until(()=>win.document.querySelector('#community-profile-modal').classList.contains('open')&&win.document.querySelector('#community-profile-loading').classList.contains('hidden'));
 assert.equal(win.document.querySelector('#community-profile-name').textContent,'لاعب الاختبار');
 win.document.querySelector('#community-profile-close').click();assert(events.some(x=>x.type==='native_home'));
 bridge.closeProfile();bridge.setNativeActive(true);
 // Game toolbar invokes the existing inventory/exit flows instead of duplicate native controls.
 const room=new Window({url:base+'/games/pool/index.html?online=1'});let inventory=0;
 room.SamiDevNetwork={state:{roomId:'ABC123',settings:{gameId:'pool'},roster:[],capacity:2},on(){}};
 room.SamiDevGameUI={isMuted:()=>false,canHelp:()=>false};room.SamiDevInventory={open:()=>inventory++};room.alert=()=>{};
 room.eval(fs.readFileSync(new URL('../game/room-menu.js',import.meta.url),'utf8'));
 room.document.dispatchEvent(new room.Event('DOMContentLoaded'));
 room.document.querySelector('#sd-room-menu-button').click();assert.equal(room.document.querySelector('#sd-help').hidden,true);
 room.document.querySelector('#sd-items').click();assert.equal(inventory,1);
 room.document.querySelector('#sd-room-back-button').click();assert(room.document.querySelector('#sd-exit-modal').classList.contains('open'));
 await room.happyDOM.close();
 console.log('PASS: native platform bridge, authenticated account pages, day theme, public-profile return, shared game menu and inventory/exit actions');
}finally{await win.happyDOM.close();}
