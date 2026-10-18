import assert from 'node:assert/strict';
import fs from 'node:fs';
const out='/workspace/artifacts/samidev-room-polish';fs.mkdirSync(out,{recursive:true});
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL;
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
try{
 const context=await browser.newContext({viewport:{width:1440,height:1000}}),page=await context.newPage(),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/platform/');await page.locator('#own-profile-details .sd-collection-progress').waitFor();
 assert.equal(await page.locator('#own-profile-card .profile-cover').evaluate(el=>getComputedStyle(el).backgroundImage),'none');
 assert.equal(await page.locator('#own-profile-card .profile-cover').evaluate(el=>getComputedStyle(el).backgroundColor),'rgb(0, 0, 0)');
 await page.evaluate(()=>{const el=document.querySelector('#own-profile-card .profile-cover');SamiDevCosmetics.cover(el,'banner_dunes');});
 assert((await page.locator('#own-profile-card .profile-cover').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('banner_dunes.webp'));
 // Exercise real room markup/renderers without an unrelated multiplayer fixture.
 await page.evaluate(()=>{document.querySelector('#community-room').classList.remove('hidden');document.querySelector('#community-home')?.classList.add('hidden');document.body.classList.add('community-mode');document.querySelector('.community-layout').dataset.mobileTab='chat';});
 const exit=await page.locator('#exit-community').boundingBox(),plus=await page.locator('#open-create').boundingBox();
 assert.equal(await page.locator('#exit-community').evaluate(el=>getComputedStyle(el).color),'rgb(231, 101, 101)');
 assert.equal(exit.width,44);assert.equal(exit.height,44);assert.equal(plus.width,44);assert(Math.abs(exit.y-plus.y)<1);assert(Math.abs(exit.x-plus.x)<60);
 const input=page.locator('#community-chat-input');await input.fill('أول سطر\nثاني سطر\nثالث سطر\nرابع سطر\nخامس سطر');
 assert.equal(await input.evaluate(el=>getComputedStyle(el).fontSize),'16px');assert((await input.boundingBox()).height<=112);assert((await input.boundingBox()).height>=100);
 const fixture={catalog:[{id:'owned',slot:'name_badge',owned:true,name:'مملوك',asset:'/platform/assets/stickers/samidev-stickers.png#cell-0'},{id:'locked',slot:'name_badge',owned:false,name:'مقفل',asset:''}]};
 async function openPicker(){await page.evaluate(data=>SamiDevCosmetics.pickStickers(data,()=>{}, {anchor:document.querySelector('#community-stickers'),host:document.querySelector('#community-panel-chat')}),fixture);}
 await openPicker();assert.equal(await page.locator('dialog[open]').count(),0);assert.equal(await page.locator('.sd-sticker-grid button').count(),1);
 const picker=await page.locator('.sd-chat-sticker-picker').boundingBox(),anchor=await page.locator('#community-stickers').boundingBox();assert(picker.y+picker.height<=anchor.y);assert(picker.width<=320);
 await page.screenshot({path:out+'/desktop-stickers.png',fullPage:false});
 await page.keyboard.press('Escape');assert.equal(await page.locator('.sd-chat-sticker-picker').count(),0);
 await page.setViewportSize({width:390,height:844});await openPicker();
 assert(await page.locator('.sd-sticker-panel-mobile').isVisible());assert(!await page.locator('#community-chat-messages').isVisible());assert(await page.locator('#community-chat-form').isVisible());
 await page.screenshot({path:out+'/phone-stickers.png',fullPage:false});
 await page.locator('.sd-chat-sticker-picker header button').click();assert(await page.locator('#community-chat-messages').isVisible());
 await input.fill('رسالة');await input.focus();assert.equal(await page.evaluate(()=>visualViewport.scale),1);assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 assert((await page.locator('meta[name=viewport]').getAttribute('content')).includes('maximum-scale=1'));
 // First registration must control the page and cache a verified static response.
 await page.waitForFunction(()=>navigator.serviceWorker.controller,{timeout:15000});
 await page.evaluate(async()=>{await fetch('/game-bootstrap.js');});
 const keys=await page.evaluate(()=>caches.keys());assert(keys.some(k=>k.startsWith('samidev-game-assets-')));
 let hits=0;page.on('response',r=>{if(new URL(r.url()).pathname==='/game-bootstrap.js'&&r.fromServiceWorker())hits++;});
 await page.evaluate(async()=>{await fetch('/game-bootstrap.js?repeat=1');});assert.equal(hits,1);
 await context.setOffline(true);
 assert((await page.evaluate(async()=>await (await fetch('/game-bootstrap.js?offline=1')).text())).includes('SamiDevGameBootstrap'));
 assert.equal(await page.evaluate(async()=>{try{await fetch('/api/me');return true;}catch{return false;}}),false);
 await context.setOffline(false);
 assert.equal(await page.evaluate(async()=>{for(const key of await caches.keys()){const cache=await caches.open(key);for(const req of await cache.keys())if(new URL(req.url).pathname.startsWith('/api/'))return true;}return false;}),false);
 const phoneContext=await browser.newContext({viewport:{width:390,height:844},isMobile:true,hasTouch:true});
 const phone=await phoneContext.newPage();await phone.goto(base+'/platform/');await phone.locator('#own-profile-details .sd-collection-progress').waitFor({state:'attached'});
 await phone.evaluate(()=>{document.querySelector('#community-room').classList.remove('hidden');document.querySelector('#community-home')?.classList.add('hidden');document.body.classList.add('community-mode');document.querySelector('.community-layout').dataset.mobileTab='chat';});
 const width=await phone.evaluate(()=>innerWidth);await phone.locator('#community-chat-input').fill('رسالة من الهاتف');await phone.locator('#community-chat-input').focus();
 assert.equal(await phone.evaluate(()=>visualViewport.scale),1);assert.equal(await phone.evaluate(()=>innerWidth),width);
 await phoneContext.close();
 assert.deepEqual(errors,[]);console.log('ROOM_COMPOSER_PASS: black/custom cover, adjacent 44px actions, four-line composer, desktop/mobile owned sticker picker, stable phone viewport, verified static cache and API exclusion');
 await context.close();
}finally{await browser.close();}
