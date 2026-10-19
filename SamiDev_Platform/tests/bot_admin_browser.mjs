import assert from 'node:assert/strict';
import fs from 'node:fs';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL;
assert.equal(new URL(base).hostname,'127.0.0.1');
const out='/workspace/artifacts/plazr/bot-admin';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
try{
 const context=await browser.newContext();await context.addCookies([{name:'samidev_session',value:process.env.SAMIDEV_TEST_ADMIN_SESSION,url:base}]);
 const page=await context.newPage();const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/platform/');await page.locator('#app').waitFor({state:'visible'});
 for(const viewport of [{width:1440,height:1000},{width:390,height:844}]){
  await page.setViewportSize(viewport);
  await page.locator('[data-page=admin]:visible').first().click();await page.locator('#admin-tab-bots').click();await page.locator('#admin-bots-open').click();
  const dialog=page.locator('.bot-admin-dialog');await dialog.locator('[data-bot]').first().waitFor();
  assert(await dialog.evaluate(el=>el.matches(':modal')&&el.parentNode===document.body));
  assert.match(await dialog.innerText(),/غير متصل حاليًا/);assert(await dialog.locator('[data-bot]').count()>=200);
  await dialog.locator('[name=filterRoom]').selectOption('majlis');
  const filtered=await dialog.locator('[data-bot]').count();assert(filtered>0&&filtered<200);
  await dialog.locator('[data-bot]').first().click();
  const form=dialog.locator('[data-editor]');await form.locator('[name=username]').fill('Preview_Bot');
  await form.locator('[name=bio]').fill('تجربة لوحة الإدارة');await form.locator('[name=enabled]').uncheck();
  await form.locator('[type=submit]').click();await dialog.locator('[data-status]').filter({hasText:'تم حفظ الحساب'}).waitFor();
  assert.equal(await form.locator('[name=username]').inputValue(),'Preview_Bot');assert.equal(await form.locator('[name=bio]').inputValue(),'تجربة لوحة الإدارة');
  for(const theme of ['dark','light']){
   await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
   const box=await dialog.boundingBox();assert(box.x>=0&&box.y>=0&&box.x+box.width<=viewport.width+1&&box.y+box.height<=viewport.height+1);
   assert(await dialog.evaluate(el=>el.scrollWidth<=el.clientWidth));
   await page.screenshot({path:`${out}/bots-${viewport.width}-${theme}.png`});
  }
  await dialog.locator('[data-close]').click();await dialog.waitFor({state:'detached'});
 }
 assert.deepEqual(errors,[]);
 console.log('BOT_ADMIN_BROWSER_PASS: admin modal; 200 accounts; room filter; persisted form edits; mobile/desktop; light/dark; no page errors');
}finally{await browser.close()}
