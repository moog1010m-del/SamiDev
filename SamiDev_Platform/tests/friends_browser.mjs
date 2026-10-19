import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL;
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
try{
 for(const width of [1366,390]){
  const a=await browser.newContext({viewport:{width,height:900},hasTouch:width<600}),b=await browser.newContext({viewport:{width,height:900},hasTouch:width<600});
  try{
   const post=async(c,path,data)=>{const r=await c.request.post(base+path,{data});const d=await r.json();assert(r.ok(),JSON.stringify(d));return d;};
   const au=(await post(a,'/api/auth/guest',{})).user,bu=(await post(b,'/api/auth/guest',{})).user;
   await post(a,'/api/friends/request',{username:bu.username});await post(b,'/api/friends/respond',{userId:au.id,accept:true});
   const page=await a.newPage(),errors=[];page.on('pageerror',e=>{errors.push(e.message);console.error('PAGE_ERROR',e.message);});
   await page.goto(base+'/platform/');await page.locator('#app').waitFor({state:'visible'});
   await page.locator('#desktop-notifications').evaluate(e=>e.click());
   await page.locator('.pf-tabs button').filter({hasText:'الأصدقاء'}).click();
   await page.locator('.pf-person').filter({hasText:bu.username}).click();
   await page.getByText('لا توجد رسائل حتى الآن…',{exact:true}).waitFor();
   const input=page.getByRole('textbox',{name:'رسالة خاصة'});await input.fill('رسالة تجريبية <img src=x onerror=alert(1)>');await page.getByRole('button',{name:'إرسال',exact:true}).click();
   await page.locator('.pf-message').waitFor();assert.equal(await page.locator('.pf-message img').count(),0);
   await input.fill('مسودة لا تختفي');
   await post(b,'/api/direct/'+au.id+'/messages',{text:'مرحبا يا صديقي',clientMessageId:crypto.randomUUID()});
   await page.getByText('مرحبا يا صديقي',{exact:true}).waitFor();assert.equal(await input.inputValue(),'مسودة لا تختفي');
   await page.locator('.pf-header .pf-icon').first().click();await page.locator('[data-page=lobby]').first().evaluate(e=>e.click());
   await post(b,'/api/direct/'+au.id+'/messages',{text:'تنبيه قابل للسحب',clientMessageId:crypto.randomUUID()});
   const banner=page.locator('.pf-banner');await banner.waitFor();
   await banner.evaluate(el=>Promise.all(el.getAnimations().map(a=>a.finished)));const box=await banner.boundingBox();if(width<600){const cdp=await a.newCDPSession(page);await cdp.send('Input.dispatchTouchEvent',{type:'touchStart',touchPoints:[{x:box.x+100,y:box.y+box.height-10}]});for(let dy=0;dy<100;dy+=12)await cdp.send('Input.dispatchTouchEvent',{type:'touchMove',touchPoints:[{x:box.x+100,y:Math.max(0,box.y+box.height-10-dy)}]});await cdp.send('Input.dispatchTouchEvent',{type:'touchEnd',touchPoints:[]});await cdp.detach();}else{await page.mouse.move(box.x+100,box.y+box.height-10);await page.mouse.down();await page.mouse.move(box.x+100,box.y-45,{steps:8});await page.mouse.up();}await banner.waitFor({state:'detached'});
   await post(a,'/api/direct/'+bu.id+'/mute',{muted:true});await post(b,'/api/direct/'+au.id+'/messages',{text:'هذه مكتومة',clientMessageId:crypto.randomUUID()});await page.waitForTimeout(800);assert.equal(await page.locator('.pf-banner').count(),0);
   await page.locator('#desktop-notifications').evaluate(e=>e.click());await page.locator('.pf-person').first().click();await page.locator('.pf-message').last().waitFor();
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));assert.deepEqual(errors,[]);
   await fs.mkdir('/workspace/artifacts/plazr/friends',{recursive:true});await page.screenshot({path:`/workspace/artifacts/plazr/friends/chat-${width}.png`,fullPage:true});
   await page.evaluate(id=>{window.SamiDevGameHost={active:{}};document.body.classList.add('sd-web-game');window.SamiDevMobilePlatform.openConversation(id);},bu.id);
   await page.locator('.pf-floating').waitFor();await page.locator('.pf-floating .pf-header .pf-icon').first().click();await page.locator('.pf-floating').waitFor({state:'detached'});assert(await page.evaluate(()=>document.body.classList.contains('sd-web-game')));
   console.log(JSON.stringify({width,friendChat:true,textEscaped:true,draftPreserved:true,swipeDismiss:true,mute:true,noOverflow:true}));
  }finally{await a.close();await b.close();}
 }
}finally{await browser.close();}
