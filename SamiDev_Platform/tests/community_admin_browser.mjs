import assert from 'node:assert/strict';
import fs from 'node:fs';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL;assert.equal(new URL(base).hostname,'127.0.0.1');
const out='/workspace/artifacts/plazr/community-admin';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
try{
 const context=await browser.newContext();await context.addCookies([{name:'samidev_session',value:process.env.SAMIDEV_TEST_ADMIN_SESSION,url:base}]);
 const page=await context.newPage(),errors=[];page.on('pageerror',error=>errors.push(error.message));
 await page.goto(base+'/platform/');await page.locator('#app').waitFor({state:'visible'});
 for(const viewport of [{width:1440,height:1000},{width:390,height:844}]){
  await page.setViewportSize(viewport);await page.locator('[data-page=admin]:visible').first().click();
  for(const key of ['overview','users','reports','policies','bots','communities']){
   await page.locator('#admin-tab-'+key).click();
   await page.locator('#admin-panel-'+key).waitFor({state:'visible',timeout:8000});
   assert.equal(await page.locator('[data-admin-panel]:visible').count(),1);
  }
  await page.locator('#admin-community-list [data-community]').first().waitFor();
  await page.locator('#admin-community-new').click();const form=page.locator('#admin-community-editor'),id='browser_'+viewport.width;
  await form.locator('[name=id]').fill(id);await form.locator('[name=name]').fill('Browser Room');
  await form.locator('[name=description]').fill('مساحة اختبار الإدارة');await form.locator('[type=submit]').click();
  try{await page.locator('#admin-community-status').filter({hasText:'تم حفظ المساحة'}).waitFor({timeout:8000});}
  catch(error){console.log(await form.evaluate(f=>({valid:f.checkValidity(),fields:[...f.elements].filter(e=>e.name).map(e=>({name:e.name,value:e.value,valid:e.checkValidity(),message:e.validationMessage}))})));console.log('status:',await page.locator('#admin-community-status').innerText(),'errors:',errors);throw error;}
  const card=page.locator(`[data-community="${id}"]`);await card.waitFor();
  assert(await form.locator('[name=id]').evaluate(element=>element.readOnly));
  await card.locator('[data-toggle]').click();await card.locator('[data-enabled=false]').waitFor();
  let response=await context.request.get(base+'/api/communities');assert(!(await response.json()).communities.some(c=>c.id===id));
  await card.locator('[data-toggle]').click();await card.locator('[data-enabled=true]').waitFor();
  response=await context.request.get(base+'/api/communities');assert((await response.json()).communities.some(c=>c.id===id));
  for(const theme of ['dark','light']){
   await page.evaluate(value=>document.documentElement.dataset.theme=value,theme);
   const overflow=await page.locator('#page-admin').evaluate(element=>({width:element.clientWidth,scroll:element.scrollWidth,items:[...element.querySelectorAll('*')].filter(node=>{const r=node.getBoundingClientRect(),p=element.getBoundingClientRect();return r.width&&((r.left<p.left-1)||(r.right>p.right+1));}).map(node=>({tag:node.tagName,class:node.className,id:node.id,width:node.getBoundingClientRect().width})).slice(0,14)}));
   assert(overflow.scroll<=overflow.width,JSON.stringify({viewport,overflow}));
   await page.screenshot({path:`${out}/communities-${viewport.width}-${theme}.png`,fullPage:true});
  }
 }
 assert.deepEqual(errors,[]);console.log('COMMUNITY_ADMIN_BROWSER_PASS: six tabs; create/edit; disable/re-enable; public filtering; mobile/desktop light/dark; no JS errors');
}finally{await browser.close();}
