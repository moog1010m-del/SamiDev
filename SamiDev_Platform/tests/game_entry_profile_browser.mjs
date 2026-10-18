import assert from 'node:assert/strict';import fs from 'node:fs';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL,out='/workspace/artifacts/plazr/entry-profile';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
 const contexts=[],pages=[];
 for(let i=0;i<2;i++){const c=await browser.newContext({viewport:{width:1280,height:900}});contexts.push(c);await c.request.post(base+'/api/auth/login',{data:{username:`perf_pool_${i}`,password:'Test-password-123'}});pages.push(await c.newPage());}
 const [owner,guest]=pages;
 const changed=await owner.request.patch(base+'/api/profile',{data:{bio:'ألعب للمتعة ⚡\nأهلًا بالجميع'}});assert.equal(changed.status(),200);assert.equal((await changed.json()).user.freeRenameAvailable,true);
 await owner.request.post(base+'/api/store/buy',{data:{itemId:'badge_shard'}});await owner.request.post(base+'/api/store/equip',{data:{itemId:'badge_shard'}});
 await owner.goto(base+'/platform/');await owner.locator('#profile-identity-handle').waitFor({state:'attached'});assert.equal(await owner.locator('#profile-identity-handle').textContent(),'ألعب للمتعة ⚡\nأهلًا بالجميع');
 await owner.goto(base+'/platform/?community=majlis');await guest.goto(base+'/platform/?community=majlis');
 await owner.locator('#community-chat-input').fill('الملصق بجانب الاسم');await owner.locator('#community-chat-form').evaluate(f=>f.requestSubmit());
 const row=owner.locator('.community-chat-message').filter({hasText:'الملصق بجانب الاسم'});await row.waitFor();
 const sticker=await row.locator('.community-chat-sticker').boundingBox(),name=await row.locator('.community-chat-profile-name').boundingBox();assert(sticker.x>=name.x+name.width);assert(sticker.x-name.x-name.width<=4);
 await owner.locator('#open-create').click();await owner.locator('[data-create-game=pool]').click();await owner.locator('#create-go').click();await owner.waitForFunction(()=>document.querySelector('#sd-game-host')?.contentWindow.__samidevGameState?.performance.frames>0,{},{timeout:45000});
 const room=await owner.frameLocator('#sd-game-host').locator('body').evaluate(()=>SamiDevNetwork.state.roomId);
 await guest.locator(`.join-room[data-room="${room}"]`).waitFor();let ticketCalls=0,release,rejectTicket=true;const gate=new Promise(resolve=>release=resolve);
 await guest.route('**/api/game-ticket',async route=>{ticketCalls++;if(rejectTicket){await route.fulfill({status:409,contentType:'application/json',body:JSON.stringify({ok:false,error:'ENTRY_TEST_FAILURE',message:'تعذر فتح الطاولة'})});return;}await gate;await route.continue();});
 await guest.locator(`.join-room[data-room="${room}"]`).click();await guest.locator('[data-entry-cancel]').click();assert.equal(ticketCalls,0);assert.equal(await guest.locator('#sd-game-host').count(),0);
 await guest.locator(`.join-room[data-room="${room}"]`).click();await guest.locator('[data-entry-confirm]').click();await guest.locator('.game-entry-error').waitFor();assert.equal(ticketCalls,1);assert.equal(await guest.locator('#sd-game-host').count(),0);await guest.locator('[data-entry-cancel]').click();rejectTicket=false;
 await guest.locator(`.join-room[data-room="${room}"]`).click();await guest.evaluate(()=>window.__sameEntry=document.querySelector('#game-entry-overlay'));
 await guest.screenshot({path:out+'/confirm-desktop.png'});await guest.locator('[data-entry-confirm]').click();await guest.locator('.game-entry-loading').waitFor();
 assert(await guest.evaluate(()=>__sameEntry===document.querySelector('#game-entry-overlay')));assert.equal(await guest.locator('#game-entry-overlay').evaluate(el=>getComputedStyle(el).backdropFilter),'none');assert.equal(ticketCalls,2);
 await guest.screenshot({path:out+'/loading-desktop.png'});await guest.setViewportSize({width:390,height:844});await guest.screenshot({path:out+'/loading-phone.png'});
 release();await guest.waitForFunction(()=>document.querySelector('#sd-game-host')?.contentWindow.__samidevGameState?.performance.frames>0,{},{timeout:45000});assert.equal(await guest.locator('#game-entry-overlay').count(),0);
 assert.equal(await guest.locator('#sd-game-host').evaluate(el=>getComputedStyle(el).opacity),'1');
 for(const c of contexts)await c.close();console.log('GAME_ENTRY_PROFILE_PASS: cancel sends nothing; same dialog loads; single ticket; no blur; closes on real frame; bio persists; right-side 3px badge');
}finally{await browser.close();}
