import assert from 'node:assert/strict';
import fs from 'node:fs/promises';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const origin=process.env.SAMIDEV_TEST_BASE_URL;assert(['localhost','127.0.0.1'].includes(new URL(origin).hostname));
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
try{
 for(const [i,width] of [390,1366].entries()){
  const context=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'}),page=await context.newPage();
  await page.goto(origin+'/platform/');await page.locator('#app').waitFor({state:'visible'});
  const peer=await page.evaluate(async name=>{const d=await fetch('/api/users/search?q='+name).then(r=>r.json());return d.users[0];},'Report_Peer'+i);assert(peer?.id);
  await page.evaluate(id=>window.SamiDevMobilePlatform.openProfile(id),peer.id);await page.locator('#community-profile-loading').waitFor({state:'hidden'});
  await page.locator('#community-profile-report').click();await page.locator('dialog.plazr-safety').waitFor();
  await page.locator('[data-reason=harassment]').click();assert(await page.locator('dialog input[type=checkbox]').isChecked());
  assert(await page.locator('dialog.plazr-safety').evaluate(d=>d.scrollWidth<=d.clientWidth+1));
  await fs.mkdir('/workspace/artifacts/plazr/report-review',{recursive:true});await page.screenshot({path:'/workspace/artifacts/plazr/report-review/sheet-'+width+'.png'});
  const response=page.waitForResponse(r=>r.request().method()==='POST'&&new URL(r.url()).pathname.endsWith('/report'));
  await page.getByRole('button',{name:'إرسال البلاغ',exact:true}).click();assert.equal((await response).status(),200);await page.locator('dialog.plazr-safety').waitFor({state:'hidden'});
  const admin=await browser.newContext({viewport:{width,height:900},serviceWorkers:'block'});await admin.addCookies([{name:'samidev_session',value:process.env.SAMIDEV_TEST_ADMIN_COOKIE,url:origin}]);
  const panel=await admin.newPage();panel.on('dialog',d=>d.accept());await panel.goto(origin+'/platform/');await panel.locator('#app').waitFor({state:'visible'});await panel.evaluate(()=>window.SamiDevMobilePlatform.navigate('admin'));await panel.locator('[data-admin-tab=reports]').click();
  const report=panel.locator('.admin-report').filter({hasText:'Report_Peer'+i}).first();await report.getByRole('button',{name:'تجاهل',exact:true}).waitFor();
  await report.getByRole('button',{name:'تجاهل',exact:true}).click();await report.getByText('تم تجاهل البلاغ',{exact:false}).waitFor();
  const result=await context.request.post(origin+'/api/users/'+peer.id+'/report',{data:{reason:'cheating',block:false}});assert.equal(result.status(),200);
  await panel.reload();await panel.locator('#app').waitFor({state:'visible'});await panel.evaluate(()=>window.SamiDevMobilePlatform.navigate('admin'));await panel.locator('[data-admin-tab=reports]').click();
  const pending=panel.locator('.admin-report').filter({hasText:'Report_Peer'+i}).filter({has:panel.getByRole('button',{name:'اتخاذ إجراء',exact:true})});
  await pending.getByRole('button',{name:'اتخاذ إجراء',exact:true}).click();await panel.locator('.admin-report').filter({hasText:'Report_Peer'+i}).getByText('تم اتخاذ إجراء',{exact:false}).waitFor();
  await admin.close();await context.close();
 }
 console.log('REPORT_REVIEW_BROWSER_PASS: phone/desktop reason selection, block+report, dismiss and confirmed ban');
}finally{await browser.close();}
