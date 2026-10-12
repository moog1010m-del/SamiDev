// Real Chromium purchase UI, using a journey account's legitimately earned wallet.
// Input contains a disposable fixture cookie; never log it or place it in argv.
import assert from 'node:assert/strict';
import fs from 'node:fs';
let input='';for await(const chunk of process.stdin)input+=chunk;
const config=JSON.parse(input);
assert.equal(new URL(config.base).hostname,'127.0.0.1');
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const browser=await chromium.launch({executablePath:process.env.SAMIDEV_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
const errors=[];let buys=0;
try{
 const context=await browser.newContext({viewport:{width:390,height:844},hasTouch:true,isMobile:true,
  extraHTTPHeaders:{'X-Forwarded-Proto':'https','X-Real-IP':config.ip}});
 await context.addCookies([{name:'samidev_session',value:config.cookie,url:config.base,httpOnly:true,secure:true,sameSite:'Lax'}]);
 const page=await context.newPage();page.on('pageerror',error=>errors.push(error.message));
 page.on('request',request=>{if(request.method()==='POST'&&request.url().endsWith('/api/store/buy'))buys++;});
 const read=async()=>{const r=await context.request.get(config.base+'/api/store');assert.equal(r.status(),200);return r.json();};
 await page.goto(config.base+'/platform/');await page.locator('#app').waitFor({state:'visible',timeout:15000});
 const before=await read();assert.equal(before.coins,config.coins);assert(before.coins>=50);
 await page.locator('.bottom-btn[data-page="store"]').click();await page.locator('.store-item-card').first().waitFor();
 assert.equal(await page.locator('.store-item-card').count(),6);
 assert.equal(await page.locator('.store-catalog').evaluate(node=>getComputedStyle(node).gridTemplateColumns.split(' ').length),2);
 await page.locator('[data-item-id="profile_star"]').click();assert.equal(buys,0);
 await page.locator('[data-product-action]').click();assert.equal(buys,0);
 await page.locator('[data-product-back]').click();await page.locator('[data-product-close]').click();
 assert.equal((await read()).coins,before.coins,'preview/cancel never charges');
 await page.locator('[data-item-id="profile_star"]').click();await page.locator('[data-product-action]').click();
 fs.mkdirSync(config.output,{recursive:true});await page.screenshot({path:config.output+'/confirmation.png'});
 await page.locator('[data-product-confirm]').evaluate(button=>{button.click();button.click();});
 await page.waitForFunction(expected=>document.querySelector('.store-star-count')?.textContent.includes('تملك '+expected),before.starsCount+1);
 const after=await read();assert.equal(buys,1);assert.equal(after.starsCount,before.starsCount+1);assert.equal(after.coins,before.coins-50);
 await page.locator('[data-product-close]').click();
 assert.equal(await page.locator('.lobby-profile-star:not([hidden])').count(),after.starsCount);
 assert.deepEqual(errors,[]);
 const result={ok:true,price:50,starsDelta:1,coins:after.coins,
  checks:['real earned wallet','six mobile products in two columns','preview/cancel never charge','explicit confirmation','double click sends one purchase','profile updates actual stars'],
  tlsScope:'secure cookie on trusted loopback; simulated HTTPS forwarding, not real production TLS'};
 fs.writeFileSync(config.output+'/report.json',JSON.stringify(result,null,2));console.log(JSON.stringify(result));
}finally{await browser.close();}
