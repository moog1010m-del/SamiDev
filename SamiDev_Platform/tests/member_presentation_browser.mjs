import assert from 'node:assert/strict';import fs from 'node:fs';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL,out='/workspace/artifacts/plazr/member-presentation';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1100}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 const members=[{id:'visual-a',username:'Dev',displayName:'Dev',bio:'THIS BIO MUST NOT APPEAR',starsCount:5,reputation:50004,wins:102,nameBadgeAsset:'/platform/assets/stickers/badge_fox-v2.png'},
 {id:'visual-b',username:'Guest_49913816df',displayName:'Guest_49913816df',bio:'HIDDEN BIO',starsCount:0,reputation:0,wins:0},
 {id:'visual-c',username:'Guest_b97306d9d9',displayName:'Guest_b97306d9d9',starsCount:1,reputation:3,wins:2}];
 await page.route('**/api/communities/majlis',route=>route.fulfill({json:{ok:true,community:{id:'majlis',name:'Saudi Arabia',countryCode:'sa'},members,rooms:[],messages:[],capabilities:{}}}));
 await page.goto(base+'/platform/?community=majlis');await page.locator('.community-member').first().waitFor();
 for(const viewport of [{width:1440,height:1100},{width:390,height:844}]){
  await page.setViewportSize(viewport);if(viewport.width<821)await page.locator('#community-tab-members').click();
  const rows=page.locator('.community-member');assert.equal(await rows.count(),3);
  for(let i=0;i<3;i++){
   const row=rows.nth(i),title=row.locator('.community-member-title');
   assert.equal(await title.innerText(),members[i].username);
   assert.equal((await row.innerText()).split(members[i].username).length-1,1);
   assert.doesNotMatch(await row.innerText(),/HIDDEN BIO|THIS BIO/);
   const avatar=await row.locator('.community-member-avatar').boundingBox(),name=await title.boundingBox(),stars=await row.locator('.community-member-stars').boundingBox(),meta=await row.locator('.community-member-meta').boundingBox();
   assert(avatar.width>=60&&avatar.height>=60);assert(avatar.x>name.x);
   assert(meta.y>=stars.y+stars.height&&meta.y>name.y);
   assert(await row.locator('.community-member-meta').isVisible());
   assert.equal(await row.locator('.sd-reputation-flame').getAttribute('data-reputation-tier'),String([6,0,1][i]));
  }
  for(const theme of ['light','dark']){
   await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
   await page.locator('#community-members').screenshot({path:`${out}/members-${viewport.width}-${theme}.png`});
  }
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 }
 assert.deepEqual(errors,[]);console.log('MEMBER_PRESENTATION_PASS: Flutter-style arrangement; single username; hidden bio; earned flames; desktop/mobile/light/dark');
}finally{await browser.close()}
