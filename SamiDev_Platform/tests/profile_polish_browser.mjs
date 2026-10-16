import assert from 'node:assert/strict';
import fs from 'node:fs';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL;assert.equal(new URL(base).hostname,'127.0.0.1');
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
const out='/workspace/artifacts/samidev-profile-polish';fs.mkdirSync(out,{recursive:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/platform/');await page.locator('#own-profile-details .sd-collection-progress').waitFor();
 const me=await (await page.request.get(base+'/api/me')).json();
 const profile=await (await page.request.get(base+'/api/public-profile/'+me.user.id)).json();
 assert(profile.user.collectionTotalCount>0);
 assert.equal(await page.locator('#own-profile-details .sd-collection-progress').getAttribute('aria-valuemax'),String(profile.user.collectionTotalCount));
 assert.equal(await page.locator('#own-profile-details .sd-collection-progress').getAttribute('aria-valuenow'),String(profile.user.collectionOwnedCount));
 assert(!await page.locator('#own-profile-card .profile-sprite-calendar').isVisible());assert(!await page.locator('#own-profile-card .profile-sprite-trophy').isVisible());
 assert((await page.locator('#profile-photo-btn .profile-sprite-camera').evaluate(el=>getComputedStyle(el).maskImage)).includes('camera.svg'));
 assert.equal(await page.locator('#profile-photo-btn .profile-sprite-camera').evaluate(el=>getComputedStyle(el).backgroundImage),'none');
 assert((await page.locator('#profile-edit-toggle span').evaluate(el=>getComputedStyle(el).maskImage)).includes('edit.svg'));
 const thresholds=[[0,0],[1,1],[99,1],[100,2],[499,2],[500,3],[999,3],[1000,4],[9999,4],[10000,5],[49999,5],[50000,6],[1000000,6]];
 for(const [score,tier]of thresholds)assert.equal(await page.evaluate(score=>SamiDevProfileDetails.reputationTier(score),score),tier);
 // Gallery exercises exact shared production renderers; data below is visual fixture data only.
 await page.evaluate(user=>{
  const gallery=document.createElement('section');gallery.id='art-gallery';gallery.style='padding:24px;display:flex;gap:20px;flex-wrap:wrap;background:#f1f6f6;color:#273d43;margin:20px';
  for(const score of [0,1,100,500,1000,10000,50000]){const tile=document.createElement('div');tile.style='display:grid;justify-items:center;gap:8px';tile.innerHTML=SamiDevProfileDetails.flameMarkup(score)+`<small>${score}</small>`;gallery.append(tile);}
  const starRow=document.createElement('div');starRow.id='star-gallery';starRow.style='display:flex;gap:12px;width:100%';
  for(const level of [1,11,21,31,41,51,61,71,81,91]){const tile=document.createElement('div');tile.style='position:relative;width:52px;height:58px';tile.innerHTML=SamiDevProfileDetails.rankMarkup(level);starRow.append(tile);}gallery.append(starRow);document.body.append(gallery);
  user.gameStatistics=[{gameId:'pool',played:150,wins:100,level:31,progress:.4,rankName:'نجم',winsToNextLevel:20}];
  SamiDevProfileDetails.render(document.querySelector('#own-profile-details'),user,{own:true});
  SamiDevProfileDetails.renderReputation(document.querySelector('#profile-reputation').previousElementSibling,50000);
 },profile.user);
 assert.equal(await page.locator('#star-gallery .sd-rank-star').count(),10);
 for(let tier=0;tier<10;tier++)assert.equal(await page.locator('#star-gallery .sd-rank-star').nth(tier).getAttribute('data-tier'),String(tier));
 assert(!await page.locator('#own-profile-card .profile-sticker').isVisible(),'no default name sticker');
 const flame=await page.locator('#own-profile-card .sd-reputation-flame').boundingBox();assert(flame.width>=30&&flame.height>=34);
 const halo=page.locator('#own-profile-card .sd-flame-halo');assert.equal(await halo.evaluate(el=>getComputedStyle(el).animationName),'sd-flame-breathe');
 await page.emulateMedia({reducedMotion:'reduce'});assert.equal(await halo.evaluate(el=>getComputedStyle(el).animationName),'none');await page.emulateMedia({reducedMotion:'no-preference'});
 await page.screenshot({path:out+'/desktop-light.png',fullPage:true});
 await page.locator('#art-gallery').screenshot({path:out+'/stars-and-reputation.png'});
 await page.locator('#desktop-theme').click();await page.screenshot({path:out+'/desktop-dark.png',fullPage:true});
 await page.locator('#art-gallery').evaluate(el=>el.remove());
 await page.setViewportSize({width:390,height:844});await page.locator('.bottom-nav [data-page=profile]').click();
 assert(await page.locator('#own-profile-card').isVisible());assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 await page.screenshot({path:out+'/phone.png',fullPage:true});
 assert.deepEqual(errors,[]);
 console.log('PROFILE_POLISH_PASS: actual catalog denominator without purchase; camera/edit line icons; ten star tiers; reputation thresholds; sizes; reduced motion; light/dark/phone');
}finally{await browser.close();}
