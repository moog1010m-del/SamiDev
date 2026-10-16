import assert from 'node:assert/strict';
import fs from 'node:fs';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL;
assert(['localhost','127.0.0.1'].includes(new URL(base).hostname));
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
try{
 const contexts=[],pages=[],errors=[];
 for(const value of [process.env.SAMIDEV_POLICY_ADMIN_COOKIE,process.env.SAMIDEV_POLICY_MEMBER_COOKIE]){
  const context=await browser.newContext({viewport:{width:1440,height:1000},extraHTTPHeaders:{'X-Forwarded-Proto':'https'}});contexts.push(context);
  await context.addCookies([{name:'samidev_session',value,url:base}]);
  const page=await context.newPage();pages.push(page);page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/platform/');await page.locator('#home-profile #own-profile-card').waitFor({state:'visible'});
  const dimensions=()=>{const card=document.querySelector('#own-profile-card'),name=card.querySelector('#profile-name');return {width:card.getBoundingClientRect().width,cover:card.querySelector('.profile-cover').getBoundingClientRect().height,avatar:card.querySelector('.profile-avatar').getBoundingClientRect().width,name:name.textContent,nameClipped:name.scrollWidth>name.clientWidth+1,details:getComputedStyle(card.querySelector('#own-profile-details')).display};};
  const home=await page.evaluate(dimensions);assert(home.width>=340&&home.width<=400);assert(!home.nameClipped);assert.notEqual(home.details,'none');
  await page.locator('.topbar-nav [data-page=profile]').click();
  const profile=await page.evaluate(dimensions);assert.equal(home.name,profile.name);assert.equal(home.details,profile.details);assert(profile.width>home.width);assert(!profile.nameClipped);
  await page.locator('.topbar-nav [data-page=lobby]').click();
  await page.locator('#profile-settings-btn').click();await page.locator('[data-settings-tab=notifications]').click();
  await page.locator('#system-notifications').waitFor({state:'visible'});await page.locator('[data-settings-tab=account]').click();
  assert(!await page.locator('#account-settings-btn').isVisible());assert(!await page.locator('#settings-auth-slot').isVisible());assert(await page.locator('#account-saved').isVisible());await page.keyboard.press('Escape');
  assert(!await page.locator('#platform-settings').isVisible());
  const connected=page.waitForResponse(r=>r.url().endsWith('/diwan/events')&&r.status()===200);
  await page.goto(base+'/platform/?community=diwan');await page.locator('#community-room').waitFor({state:'visible'});
  await connected;
  // Eliminate periodic chat refresh as an explanation for successful delivery.
  const snapshot=await page.evaluate(()=>fetch('/api/communities/diwan').then(r=>r.json()));snapshot.messages=[];
  await page.route('**/api/communities/diwan',route=>route.fulfill({contentType:'application/json',body:JSON.stringify(snapshot)}));
 }
 const [sender,receiver]=pages;
 let held=true;
 await sender.route('**/api/communities/diwan/chat',async route=>{if(held)await new Promise(r=>setTimeout(r,900));await route.continue();});
 const text='live_'+Date.now();
 await sender.locator('#community-chat-input').fill(text);
 const begun=Date.now();await sender.locator('#community-chat-form').evaluate(f=>f.requestSubmit());
 const own=sender.locator('.community-chat-message').filter({hasText:text});
 await own.waitFor({state:'visible',timeout:500});assert(Date.now()-begun<800,'sender should not wait for HTTP');
 assert((await own.innerText()).includes('جارٍ الإرسال'));
 const other=receiver.locator('.community-chat-message').filter({hasText:text});
 await other.waitFor({state:'visible',timeout:4000});
 await sender.waitForFunction(t=>Array.from(document.querySelectorAll('.community-chat-message')).some(row=>row.textContent.includes(t)&&!row.textContent.includes('جارٍ الإرسال')),text);
 assert.equal(await sender.locator('.community-chat-message').filter({hasText:text}).count(),1);
 assert.deepEqual(await other.locator('.community-chat-meta').evaluate(el=>Array.from(el.children).slice(0,3).map(n=>n.tagName)),['STRONG','SPAN','TIME']);
 const header=await other.locator('.community-chat-meta').evaluate(el=>Array.from(el.children).slice(0,3).map(n=>n.getBoundingClientRect().x));
 assert(header[0]>header[1]&&header[1]>header[2],'RTL order is name, sticker, then time');
 // A rejected send stays visible with a retry action and never pretends delivered.
 held=false;await sender.unroute('**/api/communities/diwan/chat');
 await sender.route('**/api/communities/diwan/chat',route=>route.fulfill({status:503,contentType:'application/json',body:'{"ok":false,"message":"fixture unavailable"}'}));
 const retryText='retry_'+Date.now();await sender.locator('#community-chat-input').fill(retryText);await sender.locator('#community-chat-form').evaluate(f=>f.requestSubmit());
 const failed=sender.locator('.community-chat-message').filter({hasText:retryText});await failed.getByRole('button',{name:'إعادة المحاولة',exact:true}).waitFor();
 await sender.unroute('**/api/communities/diwan/chat');await failed.getByRole('button',{name:'إعادة المحاولة',exact:true}).click();
 await receiver.locator('.community-chat-message').filter({hasText:retryText}).waitFor({timeout:4000});
 await sender.setViewportSize({width:390,height:844});await receiver.setViewportSize({width:390,height:844});
 assert.equal(await sender.locator('#room-settings-btn').count(),0);
 assert(await sender.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await sender.locator('#community-tab-chat').click();await receiver.locator('#community-tab-chat').click();
 const position=async row=>row.evaluate(el=>{const box=el.parentElement.getBoundingClientRect(),r=el.getBoundingClientRect();return {left:r.left-box.left,right:box.right-r.right};});
 const ownPosition=await position(own),otherPosition=await position(other);
 assert(ownPosition.right<ownPosition.left,'own message on right');assert(otherPosition.left<otherPosition.right,'other message on left');
 for(const height of [844,520]){
  await sender.setViewportSize({width:390,height});
  const layout=await sender.evaluate(()=>{const r=s=>document.querySelector(s).getBoundingClientRect();return {bottom:r('#community-chat-form').bottom,height:r('#community-chat-messages').height,scroll:document.documentElement.scrollHeight};});
  assert(layout.height>100);assert(layout.bottom<=height+1);assert(layout.bottom>=height-2,JSON.stringify(layout));assert(layout.scroll<=height+1,'room must not scroll the page');
 }
 await sender.setViewportSize({width:390,height:844});
 await sender.locator('#community-chat-messages').evaluate(box=>{for(const id of ['chat_mist','chat_turquoise','chat_ember']){const p=document.createElement('p');p.textContent='رسالة قصيرة ثم رسالة أطول للتأكد من تعبئة الفقاعة';window.SamiDevCosmetics.bubble(p,id);box.append(p);}box.scrollTop=box.scrollHeight;});
 await sender.screenshot({path:'/tmp/samidev-phone-room.png'});
 const out='/tmp/samidev-settings-live';fs.mkdirSync(out,{recursive:true});
 await sender.evaluate(()=>sessionStorage.removeItem('samidev_return_community'));
 await sender.goto(base+'/platform/');await sender.locator('.bottom-nav [data-page=profile]').waitFor();
 assert(!await sender.locator('#home-profile').isVisible());assert.equal(await sender.locator('.mobile-header').count(),0);
 await sender.locator('.bottom-nav [data-page=profile]').click();await sender.locator('#profile-settings-btn').click();assert(await sender.locator('#platform-settings').isVisible());await sender.locator('#settings-close').click();
 await sender.locator('.bottom-nav [data-page=lobby]').click();
 await sender.setViewportSize({width:1440,height:1000});await sender.screenshot({path:out+'/home.png',fullPage:true});
 await sender.locator('#profile-settings-btn').click();await sender.screenshot({path:out+'/settings.png',fullPage:true});
 await sender.locator('#settings-close').click();
 await sender.evaluate(()=>{window.nativeMessages=[];window.SamiDevMobile={postMessage:value=>window.nativeMessages.push(JSON.parse(value))};});
 await sender.locator('#profile-settings-btn').click();
 assert.equal(await sender.evaluate(()=>window.nativeMessages.at(-1).type),'open_settings');assert(!await sender.locator('#platform-settings').isVisible());
 assert.deepEqual(errors,[]);console.log('PLATFORM_SETTINGS_LIVE_BROWSER_PASS');
}finally{await browser.close();}
