import assert from 'node:assert/strict';
import fs from 'node:fs';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL;assert.equal(new URL(base).hostname,'127.0.0.1');
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
const out='/workspace/artifacts/samidev-desktop';fs.mkdirSync(out,{recursive:true});
try{
 const page=await browser.newPage({viewport:{width:1440,height:1000}}),errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.goto(base+'/platform/');await page.locator('#home-profile #own-profile-card').waitFor();await page.locator('.community-card').first().waitFor();await page.locator('#own-profile-details .sd-collection-section').waitFor();
 assert.equal(await page.locator('.topbar-nav [data-page=profile]').count(),0);
 assert.equal(await page.locator('.topbar-nav .nav-btn:not(.hidden) svg').count(),3);
 for(const width of [821,900,1024,1280,1440,1920]){
  await page.setViewportSize({width,height:1000});
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),String(width));
  const profile=await page.locator('#home-profile').boundingBox(),spaces=await page.locator('.community-browser').boundingBox(),rail=await page.locator('.desktop-tools').boundingBox();
  assert(profile.x>=spaces.x+spaces.width-1,'profile beside spaces at '+width);assert(rail.x+rail.width<spaces.x,'tools must not cover content');
  assert(!await page.locator('#profile-settings-btn').isVisible());
  assert(await page.locator('#desktop-settings').isVisible());
  if([1440,1920].includes(width))await page.screenshot({path:out+`/spaces-${width}.png`,fullPage:true});
 }
 await page.locator('#desktop-settings').click();await page.locator('#platform-settings-title').filter({hasText:'الإعدادات'}).waitFor();await page.keyboard.press('Escape');
 assert(!await page.locator('#platform-settings').isVisible());assert(await page.locator('#desktop-settings').evaluate(el=>el===document.activeElement));
 await page.locator('#desktop-notifications').click();assert.equal(await page.locator('#platform-settings').getAttribute('data-section'),'notifications');await page.locator('#settings-close').click();
 const theme=await page.locator('html').getAttribute('data-theme');await page.locator('#desktop-theme').click();assert.notEqual(await page.locator('html').getAttribute('data-theme'),theme);
 await page.setViewportSize({width:1440,height:1000});await page.screenshot({path:out+'/spaces-dark.png',fullPage:true});await page.locator('#desktop-theme').click();
 await page.locator('.topbar-nav [data-page=friends]').click();await page.locator('#page-friends').waitFor();await page.locator('#desktop-settings').click();await page.locator('#settings-close').click();
 await page.setViewportSize({width:390,height:844});assert(!await page.locator('.desktop-tools').isVisible());assert(!await page.locator('#home-profile').isVisible());
 await page.locator('.bottom-nav [data-page=profile]').click();assert(await page.locator('#profile-page-slot #own-profile-card').isVisible());await page.locator('#profile-settings-btn').click();await page.locator('#settings-close').click();
 await page.screenshot({path:out+'/profile-phone.png',fullPage:true});
 await page.setViewportSize({width:1440,height:1000});await page.locator('#home-profile #own-profile-card').waitFor();assert(!await page.locator('#page-profile').isVisible());
 assert.equal(await page.locator('#own-profile-card').count(),1);assert.deepEqual(errors,[]);
 console.log('DESKTOP_NAVIGATION_PASS: 821–1920px, one side profile, no profile tab, accessible settings/notifications/theme, phone profile retained');
}finally{await browser.close();}
