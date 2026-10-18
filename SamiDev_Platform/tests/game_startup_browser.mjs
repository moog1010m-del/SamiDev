import assert from 'node:assert/strict';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL,browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
 const context=await browser.newContext(),page=await context.newPage();
 await context.request.post(base+'/api/auth/login',{data:{username:'perf_pool_0',password:'Test-password-123'}});
 await page.goto(base+'/platform/?community=majlis');await page.locator('#community-room').waitFor();
 for(let pass=0;pass<2;pass++){
  await page.locator('#open-create').click();await page.locator('[data-create-game="pool"]').click();
  await page.evaluate(()=>{window.__entryViolation=false;const observe=()=>{const f=document.querySelector('#sd-game-host');if(f){const drawn=f.contentWindow.__samidevGameState?.performance.frames>0;if(drawn)return;if(getComputedStyle(f).opacity!=='0')window.__entryViolation=true;}requestAnimationFrame(observe);};requestAnimationFrame(observe);});
  const start=Date.now();await page.locator('#create-go').click();
  await page.waitForFunction(()=>document.querySelector('#sd-game-host')?.contentWindow.__samidevGameState?.performance.frames>0,{},{timeout:45000});
  const frame=page.frames().find(f=>f.parentFrame());
  console.log(JSON.stringify({pass,firstFrameMs:Date.now()-start,...await frame.evaluate(()=>({stages:window.__samidevStartup,slowest:performance.getEntriesByType('resource').sort((a,b)=>b.duration-a.duration).slice(0,6).map(r=>({file:new URL(r.name).pathname,ms:Math.round(r.duration)}))}))}));
  if(process.env.SAMIDEV_STARTUP_ASSERT==='1'){assert.equal(await page.evaluate(()=>__entryViolation),false,'no blank iframe is exposed before the first rendered frame');}
  if(process.env.SAMIDEV_STARTUP_ASSERT==='1')assert.equal(await page.locator('#sd-game-host').evaluate(el=>getComputedStyle(el).opacity),'1');
  await frame.locator('#sd-room-menu-button').click();await frame.locator('#sd-info').click();page.once('dialog',d=>d.accept());await frame.locator('[data-table-action="close"]').click();await page.locator('#sd-game-host').waitFor({state:'detached'});
 }
 await context.close();
}finally{await browser.close();}
