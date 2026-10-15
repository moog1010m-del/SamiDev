import assert from 'node:assert/strict';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL;
assert(['127.0.0.1','localhost'].includes(new URL(base).hostname));
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
try{
 const context=await browser.newContext({viewport:{width:390,height:844},extraHTTPHeaders:{'X-Forwarded-Proto':'https'}});
 await context.addCookies([{name:'samidev_session',value:process.env.SAMIDEV_POLICY_ADMIN_COOKIE,url:base}]);
 const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/platform/?community=majlis');await page.locator('#community-room').waitFor({state:'visible'});
 // Open the actual public profile through the production click binding.
 await page.evaluate(id=>{const button=document.createElement('button');button.dataset.publicProfile=id;button.textContent='review';document.body.append(button);button.click();button.remove();},process.env.SAMIDEV_POLICY_MEMBER);
 await page.locator('#community-profile-moderation').getByRole('button',{name:'كتم ١٠ دقائق',exact:true}).waitFor();
 assert(await page.getByRole('button',{name:'تعيين مشرف لهذه المساحة',exact:true}).isVisible());
 page.once('dialog',dialog=>dialog.accept());
 await page.locator('#community-profile-moderation').getByRole('button',{name:'كتم ١٠ دقائق',exact:true}).click();
 await page.waitForFunction(()=>document.querySelector('#toast').textContent.includes('تم تنفيذ الإجراء'));
 const ticket=await page.evaluate(()=>fetch('/api/game-ticket',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({communityId:'majlis'})}).then(r=>r.json()));
 await page.goto(base+'/games/pool/index.html?online=1&action=create&gameType=6&community=majlis&ticket='+encodeURIComponent(ticket.ticket));
 const close=page.locator('#sd-table-controls').getByRole('button',{name:'إغلاق الطاولة',exact:true});
 await close.waitFor({state:'visible',timeout:30000});
 page.once('dialog',dialog=>dialog.accept());await close.click();
 await page.waitForURL('**/platform/**');
 await page.waitForFunction(()=>document.querySelector('#toast')?.textContent.includes('أغلق منشئ'));
 assert.deepEqual(errors,[]);console.log('ROOM_POLICY_BROWSER_PASS');
}finally{await browser.close();}
