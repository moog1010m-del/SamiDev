import assert from 'node:assert/strict';
import fs from 'node:fs';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL;
assert.equal(new URL(base).hostname,'127.0.0.1');
const out='/workspace/artifacts/plazr/collectibles';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
try {
 const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];
 page.on('pageerror',error=>errors.push(error.message));
 const privacy=await page.goto(base+'/platform/privacy.html');
 assert.equal(privacy.status(),200);
 assert.match(privacy.headers()['content-type'],/text\/html;\s*charset=utf-8/i);
 assert.equal(await page.evaluate(()=>document.characterSet),'UTF-8');
 assert.match(await page.locator('h1').innerText(),/سياسة الخصوصية/);
 assert.doesNotMatch(await page.locator('main').innerText(),/\?{3,}|\uFFFD/);
 await page.screenshot({path:out+'/privacy-desktop.png',fullPage:true});
 await page.goto(base+'/platform/');
 await page.locator('#own-profile-details .sd-collection-progress').waitFor();
 const store=await (await page.request.get(base+'/api/store')).json();
 const badges=store.catalog.filter(item=>item.slot==='name_badge');
 assert.equal(badges.length,11);
 const profile=await (await page.request.get(base+'/api/me')).json();
 for(const viewport of [{width:1440,height:1100},{width:390,height:844}]){
  await page.setViewportSize(viewport);
  if(viewport.width<600)await page.locator('.bottom-nav [data-page=profile]').click();
  await page.evaluate(({user,badges})=>{
   user.gameStatistics=[1,10,11,100].map((level,i)=>({gameId:['pool','carrom','crazy8','tablesoccer'][i],level,played:100,wins:50,progress:.4,rankName:'بداية'}));
   user.showcaseItems=badges.map(item=>({...item,quantity:1}));
   user.collectionOwnedCount=badges.length;
   SamiDevProfileDetails.render(document.querySelector('#own-profile-details'),user,{own:true});
  },{user:profile.user,badges});
  const chips=page.locator('#own-profile-details .sd-level-chip');
  assert.equal(await chips.count(),4);
  assert.deepEqual(await chips.locator('b').allTextContents(),['1','10','100','11']); // canonical game order
  for(const number of await chips.locator('b').all()){
   assert(await number.isVisible());
   assert(Number.parseFloat(await number.evaluate(el=>getComputedStyle(el).fontSize))>=16);
  }
  for(const theme of ['light','dark']){
   await page.evaluate(value=>document.documentElement.dataset.theme=value,theme);
   await page.locator('#own-profile-details').screenshot({path:`${out}/profile-${viewport.width}-${theme}.png`});
  }
 }
 const historical=await page.evaluate(()=>[
  SamiDevStickerArt.resolve('/platform/assets/stickers/samidev-stickers.png#cell-3'),
  SamiDevStickerArt.markup('/platform/assets/stickers/samidev-stickers.png#cell-8'),
  SamiDevStickerArt.resolve('/platform/assets/cosmetics/badge_shard.webp')]);
 assert.deepEqual(historical,['/platform/assets/stickers/badge_fox-v2.png','','/platform/assets/stickers/badge_shard-v2.png']);
 await page.setViewportSize({width:1100,height:1050});
 await page.evaluate(badges=>{
  const gallery=document.createElement('section');gallery.id='new-art-gallery';
  gallery.style='position:fixed;inset:0;z-index:9999;overflow:auto;background:#f5f8f8;color:#21383c;padding:35px;font-family:system-ui;direction:rtl';
  gallery.innerHTML='<h1 style="margin:0 0 8px">Plazr · مجموعة العناصر</h1><p style="color:#647579">ملفات مستقلة · بدون ذوات أرواح</p><div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px">'+badges.map(item=>'<article style="text-align:center;background:white;border:1px solid #dce8e7;border-radius:20px;padding:20px"><div style="height:150px;display:grid;place-items:center">'+SamiDevStickerArt.markup(item.asset,'','')+'</div><h3 style="font-size:15px">'+item.name+'</h3><span style="font-size:13px;color:#647579">'+item.price+' كوينز</span></article>').join('')+'</div>';
  document.body.append(gallery);
  gallery.querySelectorAll('img').forEach(img=>{img.loading='eager';img.style='width:145px;height:145px;object-fit:contain'});
 },badges);
 await page.locator('#new-art-gallery img').evaluateAll(images=>Promise.all(images.map(img=>img.decode())));
 assert(await page.locator('#new-art-gallery img').evaluateAll(images=>images.every(img=>img.naturalWidth===256)));
 await page.screenshot({path:out+'/collection.png'});
 assert.deepEqual(errors,[]);
 console.log('PROFILE_ART_BROWSER_PASS: UTF-8 HTTP + Arabic; numeric level chips; light/dark/phone; 11 saleable independent assets; historical URLs');
}finally{await browser.close();}
