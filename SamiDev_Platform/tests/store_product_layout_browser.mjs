import assert from 'node:assert/strict';import fs from 'node:fs';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL,out='/workspace/artifacts/samidev-product-layout';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/platform/');await page.locator('#own-profile-details .sd-collection-progress').waitFor();
 await page.locator('[data-page=store]:visible').first().click();await page.locator('[data-category=profile]').click();
 for(const viewport of [{width:1440,height:1000},{width:390,height:844},{width:390,height:520}]){
  await page.setViewportSize(viewport);
  const item=page.locator('[data-item-id=badge_shard]');
  for(let turn=0;turn<5&&!await item.count();turn++)await page.locator('#store-pagination button').filter({hasText:'التالي'}).click();
  await item.click();
  await page.locator('.store-product-sheet').waitFor();
  for(const theme of ['light','dark']){
   await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
   const sheet=await page.locator('.store-product-sheet').boundingBox(),art=await page.locator('.store-product-art').boundingBox(),title=await page.locator('#store-product-title').boundingBox(),buy=await page.locator('[data-product-action]').boundingBox();
   assert(sheet.height<=viewport.height-20);assert(art.y+art.height<=title.y);assert(title.y+title.height<=buy.y);assert(buy.y+buy.height<=sheet.y+sheet.height);
   assert(await page.locator('.store-product-art').evaluate(el=>{const child=el.firstElementChild,r=el.getBoundingClientRect(),c=child.getBoundingClientRect();return c.width<=r.width&&c.height<=r.height;}));
   assert.equal(await page.locator('.store-product-sheet').evaluate(el=>el.scrollHeight>el.clientHeight),false);
   await page.screenshot({path:`${out}/product-${viewport.width}-${viewport.height}-${theme}.png`});
  }
  await page.locator('[data-product-close]').click();
 }
 assert.deepEqual(errors,[]);console.log('STORE_PRODUCT_LAYOUT_PASS: bounded artwork; separated name/details; visible purchase area; desktop/mobile/short viewport; light/dark');
}finally{await browser.close();}
