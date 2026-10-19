import assert from 'node:assert/strict';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL;
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try {
 for(const game of ['pool','carrom','crazy8','tablesoccer']) {
  const context=await browser.newContext({viewport:{width:390,height:844}});
  try {
   const response=await context.request.post(base+'/api/auth/login',{data:{username:'entry_'+game,password:'Test-password-123'}});
   const user=(await response.json()).user;assert(user?.id);
   await context.request.post(base+'/__test/entry-cooldown',{data:{uid:user.id,enabled:true}});
   const page=await context.newPage();await page.goto(base+'/platform/?community=majlis');
   const lobby=page.url();
   async function create(){await page.locator('#open-create').click();await page.locator(`[data-create-game=${game}]`).click();await page.locator('#create-go').click();}
   await create();
   await page.waitForFunction(()=>document.querySelector('#toast')?.textContent==='حاول بعد دقيقة'&&document.querySelector('#toast').classList.contains('show'),{},{timeout:45000});
   assert.equal(page.url(),lobby);assert.equal(await page.locator('#sd-game-host').count(),0);
   assert.equal(await page.locator('#game-entry-overlay').count(),0);
   assert.equal(await page.locator('body.sd-web-game,body.sd-game-opening,#app[inert]').count(),0);
   assert(!await page.locator('#toast').textContent().then(t=>/\d|ثانية/.test(t)));
   // Simulate expiry; don't spend four actual minutes in a regression test.
   await context.request.post(base+'/__test/entry-cooldown',{data:{uid:user.id,enabled:false}});
   await create();
   await page.waitForFunction(()=>document.querySelector('#sd-game-host')?.style.opacity==='1',{},{timeout:45000});
   const admitted=await page.locator('#sd-game-host').evaluate(frame=>({room:frame.contentWindow.SamiDevNetwork.state.roomId,frames:frame.contentWindow.__samidevGameState.performance.frames}));
   assert(admitted.room&&admitted.frames>0);
   assert.equal(await page.locator('#game-entry-overlay').count(),0);
   const guestContext=await browser.newContext({viewport:{width:390,height:844}});
   try {
    const login=await guestContext.request.post(base+'/api/auth/login',{data:{username:'join_'+game,password:'Test-password-123'}});
    const guestUser=(await login.json()).user;assert(guestUser?.id);
    await guestContext.request.post(base+'/__test/entry-cooldown',{data:{uid:guestUser.id,enabled:true}});
    const guest=await guestContext.newPage();await guest.goto(base+'/platform/?community=majlis');
    const guestLobby=guest.url();
    const join=async()=>{await guest.locator(`.join-room[data-room="${admitted.room}"]`).click();await guest.locator('[data-entry-confirm]').click();};
    await join();await guest.waitForFunction(()=>document.querySelector('#toast')?.textContent==='حاول بعد دقيقة'&&document.querySelector('#toast').classList.contains('show'),{},{timeout:45000});
    assert.equal(guest.url(),guestLobby);assert.equal(await guest.locator('#sd-game-host,#game-entry-overlay,#app[inert]').count(),0);
    await guestContext.request.post(base+'/__test/entry-cooldown',{data:{uid:guestUser.id,enabled:false}});
    await join();await guest.waitForFunction(()=>document.querySelector('#sd-game-host')?.style.opacity==='1',{},{timeout:45000});
    assert.equal(await guest.locator('#sd-game-host').evaluate(frame=>frame.contentWindow.SamiDevNetwork.state.roomId),admitted.room);
    console.log(JSON.stringify({game,joinRejectKeepsLobby:true,joinRetryAdmitted:true}));
   } finally {await guestContext.close();}
   await page.evaluate(()=>SamiDevGameHost.close());
   console.log(JSON.stringify({game,rejectionKeepsLobby:true,floatingMinuteNotice:true,retryAfterSimulatedExpiry:true,admittedBeforeReveal:true}));
  } finally {await context.close();}
 }
} finally {await browser.close();}
