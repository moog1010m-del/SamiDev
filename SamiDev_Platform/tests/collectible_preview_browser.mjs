import assert from 'node:assert/strict';
import fs from 'node:fs';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL,out='/workspace/artifacts/plazr/collectible-preview';
assert.equal(new URL(base).hostname,'127.0.0.1');fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
try {
 const page=await browser.newPage({viewport:{width:1546,height:1114}}),errors=[];
 page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/platform/');await page.locator('#own-profile-details').waitFor();
 const store=await (await page.request.get(base+'/api/store')).json();
 const me=await (await page.request.get(base+'/api/me')).json();
 // Visual fixtures represent an owned exclusive and event item, never a real grant or purchase.
 const items=[
  {id:'badge_steward',name:'بوصلة المجلس',slot:'name_badge',asset:'/platform/assets/stickers/badge_steward-v3.png',quantity:1,description:'عنصر مخصص لمشرفي المساحات.',availability:{kind:'moderator',purchasable:false,label:'خاص بمشرفي المساحات؛ لا يُباع في المتجر.'}},
  {...store.catalog.find(item=>item.id==='badge_shard'),quantity:1},
  {id:'event-fixture',name:'تذكار الفعالية',slot:'name_badge',asset:'/platform/assets/stickers/badge_moonstone-v3.png',quantity:1,description:'تذكار فعالية تجريبية لاختبار العرض فقط. '.repeat(18),availability:{kind:'event',purchasable:false,label:'مكافأة فعالية: لقاء اللاعبين. غير متاح حاليًا للشراء.'}},
 ];
 // Keep the synthetic showcase stable when the application refreshes the public profile.
 await page.route('**/api/public-profile/*',route=>route.fulfill({json:{ok:true,user:{...me.user,showcaseItems:items,collectionOwnedCount:3,collectionTotalCount:3}}}));
 for(const viewport of [{width:1546,height:1114},{width:390,height:844},{width:390,height:480}]){
  await page.setViewportSize(viewport);
  if(viewport.width<821)await page.locator('.bottom-nav [data-page=profile]').click();
  await page.evaluate(({user,items})=>{
   window.__previewUser={...user,showcaseItems:items};window.__previewUses=0;
   window.__previewRender=()=>SamiDevProfileDetails.render(document.querySelector('#own-profile-details'),window.__previewUser,{own:true,onUse:async()=>{window.__previewUses++;return true}});
   window.__previewRender();
   document.querySelector('#home-profile').style.transform='translateZ(0)';
  },{user:me.user,items});
  for(const theme of ['light','dark']){
   await page.evaluate(t=>{document.documentElement.dataset.theme=t;window.__previewRender();},theme);
   await page.locator('#own-profile-details .sd-owned-card').first().click();
   const dialog=page.locator('dialog.sd-item-detail');await dialog.waitFor();
   assert(await dialog.evaluate(el=>el.matches(':modal')&&el.parentElement===document.body));
   assert.match(await dialog.innerText(),/خاص بمشرفي المساحات/);
   assert(!/شراء/.test(await dialog.locator('button').allTextContents().then(x=>x.join(' '))));
   assert.equal(await dialog.locator('.sd-item-name-preview strong').innerText(),me.user.username);
   assert.equal(await dialog.evaluate(el=>getComputedStyle(el,'::backdrop').backdropFilter),'none');
   const before=await dialog.boundingBox();
   await page.evaluate(()=>{window.__samePreview=document.querySelector('dialog.sd-item-detail');for(let i=0;i<5;i++)window.__previewRender();});
   assert(await dialog.evaluate(el=>el===window.__samePreview));
   const after=await dialog.boundingBox();assert.deepEqual(after,before,'profile refresh must not move or recreate the dialog');
   assert(Math.abs(after.x+after.width/2-viewport.width/2)<=1);
   assert(after.y>=0&&after.y+after.height<=viewport.height);assert(after.height<=560,'preview must remain a compact card');
   const art=await dialog.locator('.sd-item-art').boundingBox(),title=await dialog.locator('h4').boundingBox(),foot=await dialog.locator('footer').boundingBox();
   const image=await dialog.locator('.sd-item-art>img').boundingBox();assert(image.height<=170&&image.y>=art.y&&image.y+image.height<=art.y+art.height,'actual high-resolution image must stay inside art region');
   assert(art.y+art.height<=title.y,'art may not overlap title');assert(title.y+title.height<=foot.y);
   await dialog.locator('.sd-item-use').click();assert.equal(await dialog.locator('.sd-item-use').innerText(),'مفعّل الآن');
   await page.screenshot({path:`${out}/exclusive-${viewport.width}-${viewport.height}-${theme}.png`});
   await page.keyboard.press('Escape');await page.locator('dialog.sd-item-detail').waitFor({state:'detached'});
  }
  await page.evaluate(()=>window.__previewRender());
  await page.locator('#own-profile-details .sd-owned-card').nth(2).click();
  const dialog=page.locator('dialog.sd-item-detail');
  assert.match(await dialog.innerText(),/مكافأة فعالية/);
  assert(await dialog.locator('footer').isVisible());
  assert((await dialog.locator('footer').boundingBox()).y+(await dialog.locator('footer').boundingBox()).height<=viewport.height);
  await dialog.locator('.sd-item-close').click();
 }
 // Stale/exclusive catalog fixtures must never become a free purchase offer.
 const moderator={...items[0],owned:true,retired:true,price:0,category:'profile',availableToAll:false,default:false};
 const event={...items[2],owned:false,retired:true,price:100,category:'profile',availableToAll:false,default:false};
 await page.route('**/api/store',route=>route.fulfill({json:{...store,catalog:[moderator,event,...store.catalog],inventory:[moderator.id]}}));
 await page.setViewportSize({width:1546,height:1114});
 await page.locator('[data-page=store]:visible').first().click();await page.locator('[data-category=profile]').click();
 await page.locator('[data-item-id=badge_steward]').click();
 assert.match(await page.locator('.store-product-availability').innerText(),/مشرفي المساحات/);
 assert.equal(await page.locator('[data-product-action]').innerText(),'استخدام');
 assert.doesNotMatch(await page.locator('.store-product-sheet footer').innerText(),/مجاني|كوينز/);
 await page.locator('[data-product-close]').click();
 await page.locator('[data-item-id=event-fixture]').click();
 assert.equal(await page.locator('[data-product-action]').count(),0);
 assert.match(await page.locator('.store-product-availability').innerText(),/غير متاح حاليًا للشراء/);
 await page.locator('[data-product-close]').click();
 assert.deepEqual(errors,[]);
 console.log('COLLECTIBLE_PREVIEW_PASS: top-layer isolation; no refresh flicker; bounded art; identity/description; moderator/event notice; no purchase; use; escape; light/dark/mobile/short viewport');
}finally{await browser.close()}
