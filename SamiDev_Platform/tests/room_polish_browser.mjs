import assert from 'node:assert/strict';
import fs from 'node:fs';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL;assert.equal(new URL(base).hostname,'127.0.0.1');
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const out='/workspace/artifacts/samidev-room-polish';fs.mkdirSync(out,{recursive:true});
let release,held,upstream,errors=[];
try{
 const pages=[];
 for(const [i,username]of ['room_visual_admin','room_visual_member'].entries()){
  const context=await browser.newContext({viewport:{width:1440,height:1000},extraHTTPHeaders:{Origin:base,'X-Real-IP':`10.45.0.${i+1}`}});
  assert.equal((await context.request.post(base+'/api/auth/login',{data:{username,password:'Test-password-123'}})).status(),200);
  const page=await context.newPage();pages.push(page);page.on('pageerror',e=>errors.push(e.message));await page.goto(base+'/platform/');await page.locator('#own-profile-card').waitFor();
 }
 const [admin,member]=pages;
 await admin.locator('#admin-nav').click();await admin.locator('[name=maxTables]').waitFor();
 await admin.waitForFunction(()=>document.querySelector('[name=maxTables]').value!=='');
 await admin.locator('[name=maxTables]').fill('12');await admin.locator('#room-policy-form button[type=submit]').click();await admin.locator('#room-policy-status').filter({hasText:'تم حفظ'}).waitFor();
 assert.equal((await (await admin.request.get(base+'/api/admin/communities/majlis/policy')).json()).settings.maxTables,12);
 for(const page of pages){
  const streamResponse=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/communities/majlis/events');
  await page.goto(base+'/platform/?community=majlis');await page.locator('#community-room').waitFor();
  const response=await streamResponse;
  assert.equal(response.status(),200);
  assert.match(response.headers()['cache-control']||'',/no-transform/,'SSE must preserve the no-transform directive');
 }
 assert.equal(await member.locator('#open-create svg').count(),1);assert.equal(await member.locator('#exit-community svg').count(),1);assert.equal(await member.locator('#community-chat-form button[type=submit] svg').count(),1);
 assert.equal(await member.locator('#own-profile-card .profile-sticker:not([hidden])').count(),0);
 await member.locator('#community-stickers').click();await member.locator('.sd-chat-sticker-picker').waitFor();
 assert.equal(await member.locator('.sd-chat-sticker-picker .sd-sprite-badge').count(),1,'only purchased name stickers, not purchased chat frames');
 await member.locator('.sd-chat-sticker-picker .sd-sprite-badge').click();
 await admin.locator('.community-chat-message .sd-chat-sticker-art').waitFor();
 // Disable history requests: this assertion must pass via SSE, never polling.
 await admin.route('**/api/communities/majlis',route=>route.abort());
 await member.locator('#community-chat-input').fill('رسالة مباشرة');await member.locator('#community-chat-form button[type=submit]').click();
 await admin.locator('.community-chat-message').filter({hasText:'رسالة مباشرة'}).waitFor({timeout:1500});
 await admin.unroute('**/api/communities/majlis');
 // Simulate a connected proxy that stops delivering SSE bytes after snapshot.
 await admin.addInitScript(()=>{const Native=window.EventSource;window.EventSource=class{constructor(url){this.readyState=1;this.inner=new Native(url);this.inner.onmessage=event=>{if(!this.initial){this.initial=true;this.onmessage?.(event);}};}close(){this.readyState=2;this.inner.close();}};});
 await admin.reload();await admin.locator('#community-room').waitFor();
 await admin.locator('.community-chat-message').filter({hasText:'رسالة مباشرة'}).waitFor();
 await member.locator('#community-chat-input').fill('رسالة أثناء صمت البث');await member.locator('#community-chat-form button[type=submit]').click();
 await admin.locator('.community-chat-message').filter({hasText:'رسالة أثناء صمت البث'}).waitFor({timeout:25000});
 assert.equal(await admin.locator('.community-chat-message').filter({hasText:'رسالة أثناء صمت البث'}).count(),1,'silent OPEN stream recovers without refresh or duplicates');
 await member.screenshot({path:out+'/community-desktop.png',fullPage:true});
 for(const width of [320,390]){await member.setViewportSize({width,height:844});await member.locator('#community-tab-chat').click();assert(await member.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));const boxes=await member.locator('#community-chat-input,#community-stickers,#community-chat-form button[type=submit]').evaluateAll(elements=>elements.map(el=>el.getBoundingClientRect().y));assert(Math.max(...boxes)-Math.min(...boxes)<4,'composer controls share one row');}
 await member.screenshot({path:out+'/community-phone.png',fullPage:true});
 // Hold an actual outbound packet, rather than mocking the server acceptance.
 await member.routeWebSocket('**/ws*',socket=>{upstream=socket.connectToServer();socket.onMessage(raw=>{const data=JSON.parse(String(raw));if(data.type==='chat_send'&&data.text==='اختبار التأكيد'){held=raw;return;}upstream.send(raw);});upstream.onMessage(raw=>socket.send(raw));});
 await member.goto(base+'/games/pool/index.html?online=1&action=create&community=majlis');await member.waitForSelector('#sd-waiting.scene-ready',{timeout:30000});const rid=await member.evaluate(()=>SamiDevNetwork.state.roomId);
 await admin.goto(base+'/games/pool/index.html?online=1&action=join&community=majlis&room='+rid);
 for(const page of pages)await page.waitForFunction(()=>SamiDevNetwork.state.begun&&window.__gameLogic?.started&&!__samidevGameState.network.waiting,{},{timeout:30000});
 assert(await member.evaluate(()=>SamiDevNetwork.sendChat('اختبار التأكيد')));
 await member.waitForFunction(()=>document.querySelector('#sd-chat-messages')?.textContent.includes('جارٍ الإرسال'));
 assert(held);assert.equal(await admin.locator('.sd-chat-message').filter({hasText:'اختبار التأكيد'}).count(),0,'unaccepted text is not broadcast');
 upstream.send(held);held=null;
 await member.waitForFunction(()=>!document.querySelector('#sd-chat-messages')?.textContent.includes('جارٍ الإرسال'));
 assert.equal(await member.locator('.sd-chat-message').filter({hasText:'اختبار التأكيد'}).count(),1,'confirmation replaces pending row');
 await admin.locator('.sd-chat-message').filter({hasText:'اختبار التأكيد'}).waitFor();
 assert(await member.locator('.sd-chat-message').filter({hasText:'اختبار التأكيد'}).locator('.sd-decorated-message').count());
 assert(await member.evaluate(()=>SamiDevNetwork.sendSticker('badge_shard','/platform/assets/cosmetics/badge_shard.webp')));
 await admin.locator('.sd-chat-sticker-art').waitFor();
 await admin.screenshot({path:out+'/game-chat.png',fullPage:true});
 assert.deepEqual(errors,[]);
 console.log('ROOM_POLISH_BROWSER_PASS: admin policy persisted; line controls; removed badge; owned-sticker picker + SSE delivery; live text within 1500ms with history requests blocked; silent-stream recovery; two real pool clients; immediate pending and single authoritative confirmation; equipped frame and sticker rendering');
}finally{await browser.close();}
