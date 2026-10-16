import assert from 'node:assert/strict';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL;
assert(['127.0.0.1','localhost'].includes(new URL(base).hostname));
const cookies=process.env.SAMIDEV_TEST_COOKIES.split('|');
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
try{
  const pages=[],errors=[];
  for(const token of cookies){
    const context=await browser.newContext({viewport:{width:390,height:844}});
    await context.addCookies([{name:'samidev_session',value:token,url:base,httpOnly:true}]);
    const page=await context.newPage();page.on('pageerror',e=>errors.push(e.message));
    await page.route('**/platform/vendor/google-auth.js',route=>route.fulfill({contentType:'application/javascript',body:'export async function authenticateGoogle(){throw Error("Not used in this test");}'}));
    await page.goto(base+'/platform/');await page.locator('#app').waitFor();pages.push(page);
  }
  const [main,remote,googleOnly]=pages;
  const open=async(page,tab)=>{
    if(!await page.locator('#platform-settings').isVisible()){
      await page.locator('.bottom-nav [data-page=profile]').click();await page.locator('#profile-settings-btn').click();
    }
    await page.locator(`[data-settings-tab=${tab}]`).click();
  };
  let reset=0,wrongIdentity=true;
  await main.route(/^https:\/\/identitytoolkit\.googleapis\.com\//,async route=>{
    assert(!route.request().headers().cookie);
    const body=route.request().postDataJSON();
    assert.equal(body.email,'token-a@example.test');
    let result={};
    if(route.request().url().includes('sendOobCode')){assert.equal(body.requestType,'PASSWORD_RESET');reset++;}
    else {assert.equal(body.password,'Actual-password-123456');result={idToken:wrongIdentity?'token-b':'token-a',refreshToken:'memory-only'};}
    await route.fulfill({contentType:'application/json',body:JSON.stringify(result)});
  });
  await open(main,'account');await main.locator('#account-summary').getByText('token-a@example.test',{exact:true}).waitFor();
  assert(!await main.locator('#settings-auth-slot').isVisible());assert(!await main.locator('#account-settings-btn').isVisible());
  assert.equal(await main.locator('[data-settings-panel=account] input:visible').count(),0);
  await main.locator('#account-password-reset').click();await main.waitForFunction(()=>document.querySelector('#account-security-status').textContent.includes('أرسلنا'));
  assert.equal(reset,1);await main.screenshot({path:'/tmp/samidev-account-mobile.png',fullPage:true});
  for(const width of [320,390,1440]){
    await main.setViewportSize({width,height:844});assert(await main.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
  }
  await main.setViewportSize({width:390,height:844});
  await open(googleOnly,'account');await googleOnly.locator('#account-summary').getByText('token-b@example.test',{exact:true}).waitFor();
  assert(!await googleOnly.locator('#account-password-reset').isVisible());assert(await googleOnly.getByText('تُدار كلمة مرور Google من حسابك لدى Google.').isVisible());
  await open(main,'devices');await main.locator('.account-device').first().waitFor();
  assert.equal(await main.locator('.account-device').count(),2);assert(await main.getByText('iPhone · هذا الجهاز',{exact:true}).isVisible());
  await main.screenshot({path:'/tmp/samidev-devices-mobile.png',fullPage:true});
  const remoteRow=main.locator('.account-device').filter({hasText:'Windows'});
  const otherDevice=(await googleOnly.evaluate(()=>fetch('/api/account/devices').then(r=>r.json()))).devices[0].id;
  const denied=await main.evaluate(async id=>{const r=await fetch('/api/account/devices/'+id,{method:'DELETE'});return r.status;},otherDevice);assert.equal(denied,404);
  main.once('dialog',d=>d.accept());await remoteRow.getByRole('button').click();
  await main.waitForFunction(()=>document.querySelectorAll('.account-device').length===1);
  assert.equal(await remote.evaluate(()=>fetch('/api/me').then(r=>r.status)),401);
  assert.equal(await googleOnly.evaluate(()=>fetch('/api/me').then(r=>r.status)),200);
  await open(main,'account');await main.locator('#account-summary').getByText('token-a@example.test',{exact:true}).waitFor();
  await main.locator('#account-delete').click();await main.locator('#delete-password').fill('Actual-password-123456');await main.locator('#delete-confirm').click();
  await main.locator('#delete-account-error').getByText('أكد الدخول إلى نفس الحساب مجددًا قبل الحذف',{exact:true}).waitFor();
  assert.equal(await main.evaluate(()=>fetch('/api/me').then(r=>r.status)),200);
  assert.equal(await main.locator('#delete-password').inputValue(),'');
  wrongIdentity=false;
  await main.locator('#delete-password').fill('Actual-password-123456');
  main.once('dialog',d=>d.accept());await main.locator('#delete-confirm').click();
  await main.waitForFunction(()=>document.querySelector('#side-name').textContent.startsWith('Guest_'));
  assert(!await main.locator('#delete-account-dialog').isVisible());
  assert(!await main.evaluate(()=>JSON.stringify({...localStorage,...sessionStorage}).includes('memory-only')));
  await main.unroute('**/platform/vendor/google-auth.js');
  await main.route('**/platform/vendor/google-auth.js',route=>route.fulfill({contentType:'application/javascript',body:'export async function authenticateGoogle(){return {idToken:"token-b",refreshToken:"not-persisted"};}'}));
  const external=await main.goto(base+'/platform/account-deletion.html');assert.equal(external.status(),200);
  assert(await main.getByRole('link',{name:'فتح إعدادات الحساب'}).isVisible());
  await main.locator('#public-delete-google').click();await main.locator('#deletion-confirmation').waitFor();
  assert.equal(await main.locator('#deletion-account-name').textContent(),'Google_Player · token-b@example.test');
  assert(await main.locator('#public-delete-confirm').isDisabled());
  await main.locator('#public-delete-ack').check();await main.locator('#public-delete-confirm').click();
  await main.waitForFunction(()=>document.querySelector('#deletion-status').textContent.includes('حُذف حساب SamiDev'));
  assert.equal(await googleOnly.evaluate(()=>fetch('/api/me').then(r=>r.status)),401);
  assert(!await main.evaluate(()=>JSON.stringify({...localStorage,...sessionStorage}).includes('not-persisted')));
  assert.deepEqual(errors,[]);
  console.log('ACCOUNT_SETTINGS_BROWSER_PASS: no login form, password email, owned device revocation, fresh matching identity deletion, 320/390/1440px');
}finally{await browser.close();}
