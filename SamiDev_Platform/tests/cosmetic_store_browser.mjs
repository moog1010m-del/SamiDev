// Real Chromium against isolated cosmetic_store_cluster.py fixtures.
import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import assert from 'node:assert/strict';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const out=process.env.SAMIDEV_TEST_ARTIFACTS||fs.mkdtempSync(path.join(os.tmpdir(),'samidev-cosmetics-'));
fs.mkdirSync(out,{recursive:true});
const base=process.env.SAMIDEV_TEST_BASE_URL;
assert(['127.0.0.1','localhost'].includes(new URL(base).hostname));
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
const errors=[];
async function context(cookie){
  const ctx=await browser.newContext({viewport:{width:390,height:844},extraHTTPHeaders:{'X-Forwarded-Proto':'https'}});
  await ctx.addCookies([{name:'samidev_session',value:cookie,url:base}]);
  const page=await ctx.newPage();page.on('pageerror',error=>errors.push(error.message));return {ctx,page};
}
async function ownCovers(page,asset){
  for(const selector of ['.lobby-profile .lobby-profile-cover','#page-profile .profile-cover']){
    assert((await page.locator(selector).evaluate(el=>getComputedStyle(el).backgroundImage)).includes(asset),selector);
  }
}
async function openStore(page,category){
  await page.locator('[data-page="store"]:visible').first().click();
  await page.locator(`[data-category="${category}"]`).click();
}
try{
  const {page:p}=await context(process.env.SAMIDEV_COSMETIC_COOKIE);
  await p.goto(base+'/platform/');await p.locator('#app').waitFor({state:'visible'});
  await ownCovers(p,'banner_dunes.webp');
  await openStore(p,'chat');await p.locator('[data-item-id="chat_turquoise"]').waitFor();
  assert.equal(await p.locator('.store-chat-preview.sd-decorated-message').count(),3);
  assert.equal(await p.locator('.store-chat-preview .store-chat-preview-meta').count(),0);
  await p.screenshot({path:path.join(out,'chat-store-mobile.png')});
  await p.locator('[data-item-id="chat_mist"]').click();
  assert(await p.locator('.store-product-sheet .sd-decorated-message').isVisible());
  await p.locator('[data-product-action]').click();
  assert(await p.locator('[data-product-confirm]').isVisible());
  await p.screenshot({path:path.join(out,'chat-purchase-preview.png')});
  await p.locator('[data-product-close]').click();await p.locator('[data-category="banners"]').click();
  assert.equal(await p.locator('.store-banner-art').count(),4);
  await p.screenshot({path:path.join(out,'banner-store-mobile.png')});
  await p.goto(base+'/platform/?community=majlis');
  await p.locator('[data-community-tab="chat"]').click();
  await p.locator('.community-chat-bubble.sd-decorated-message').waitFor();
  const longText='رسالة طويلة '+ 'كلمة '.repeat(40);
  await p.locator('#community-chat-input').fill(longText);
  await p.locator('#community-chat-form').evaluate(form=>form.requestSubmit());
  const styled=p.locator('.community-chat-bubble').filter({hasText:'رسالة طويلة'});
  await styled.waitFor();
  const row=styled.locator('xpath=ancestor::article[1]');
  for(const width of [390,1440])for(const theme of ['light','dark']){
    await p.setViewportSize({width,height:900});
    await p.evaluate(theme=>document.documentElement.dataset.theme=theme,theme);
    assert(await p.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
    assert.deepEqual(await row.locator('.community-chat-avatar').evaluate(el=>({width:Math.round(el.getBoundingClientRect().width),height:Math.round(el.getBoundingClientRect().height)})),{width:34,height:34});
    assert.equal(await styled.locator('.community-chat-meta').count(),0);
    const meta=await row.locator('.community-chat-meta').boundingBox(),bubble=await styled.boundingBox();
    assert(meta.y+meta.height<=bubble.y+1,'sender metadata remains above the frame');
    assert.equal(await styled.locator('p').evaluate(el=>getComputedStyle(el).color),'rgb(237, 243, 245)');
    assert((await styled.evaluate(el=>getComputedStyle(el).borderImageSource)).includes('chat_turquoise.webp'));
    const short=p.locator('.community-chat-bubble').filter({hasText:'هذه رسالة مزينة'});
    assert((await short.boundingBox()).width<bubble.width,'short messages fit their own text');
    await p.screenshot({path:path.join(out,`decorated-chat-${width}-${theme}.png`)});
  }
  await row.locator('.community-chat-profile-name').click();
  await p.locator('#community-profile-modal.open').waitFor();
  assert((await p.locator('#community-profile-modal .profile-cover').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('banner_dunes.webp'));
  await p.locator('#community-profile-close').click();await p.locator('#exit-community').click();
  await openStore(p,'banners');await p.locator('[data-item-id="banner_garden"]').click();
  await p.locator('[data-product-action]').click();await p.locator('[data-product-confirm]').click();
  await p.locator('[data-product-action]').waitFor();await p.locator('[data-product-action]').click();
  await p.waitForFunction(()=>getComputedStyle(document.querySelector('.lobby-profile .lobby-profile-cover')).backgroundImage.includes('banner_garden.webp'));
  await p.locator('[data-product-close]').click();await ownCovers(p,'banner_garden.webp');
  // Another account must see the selected banner on the public profile, too.
  const {page:other}=await context(process.env.SAMIDEV_COSMETIC_OTHER_COOKIE);
  await other.goto(base+'/platform/?community=majlis');
  await other.locator('[data-community-tab="chat"]').click();
  const sender=other.locator('.community-chat-message').filter({hasText:'رسالة طويلة'});
  await sender.locator('.community-chat-profile-name').click();
  await other.locator('#community-profile-modal.open').waitFor();
  assert((await other.locator('#community-profile-modal .profile-cover').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('banner_garden.webp'));
  await other.screenshot({path:path.join(out,'public-profile-selected-cover.png')});
  // Returning to the default must replace the previous cover in all own surfaces.
  await p.locator('[data-item-id="banner_default"]').click();await p.locator('[data-product-action]').click();
  await p.waitForFunction(()=>getComputedStyle(document.querySelector('.lobby-profile .lobby-profile-cover')).backgroundImage.includes('samidev-night-cover.png'));
  await p.locator('[data-product-close]').click();await ownCovers(p,'samidev-night-cover.png');
  await other.locator('#community-profile-close').click();await sender.locator('.community-chat-profile-name').click();await other.locator('#community-profile-modal.open').waitFor();assert((await other.locator('#community-profile-modal .profile-cover').evaluate(el=>getComputedStyle(el).backgroundImage)).includes('samidev-night-cover.png'));
  assert.deepEqual(errors,[]);
  console.log('COSMETICS_REAL_BROWSER_PASS');
}finally{await browser.close();}
