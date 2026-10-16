import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import {fileURLToPath} from 'node:url';
const root=path.resolve(path.dirname(fileURLToPath(import.meta.url)),'../game');
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
try{
 const page=await browser.newPage();
 await page.route('http://127.0.0.1:19876/**',route=>{
  const name=new URL(route.request().url()).pathname;
  if(name==='/')return route.fulfill({contentType:'text/html',body:'<meta charset="utf-8"><link rel="stylesheet" href="/profile-details.css"><div id="profile"></div><script src="/profile-details.js"></script>'});
  return route.fulfill({contentType:name.endsWith('.js')?'application/javascript':'text/css',body:fs.readFileSync(root+name)});
 });
 await page.goto('http://127.0.0.1:19876/');
 const user={collectionOwnedCount:2,collectionTotalCount:10,showcaseItems:[],gameStatistics:[{gameId:'pool',played:1,wins:0,level:1},{gameId:'carrom',played:0,wins:0,level:1}]};
 for(const width of [320,390,1440]){
  await page.setViewportSize({width,height:900});
  await page.evaluate(user=>window.SamiDevProfileDetails.render(document.querySelector('#profile'),user,{own:true}),user);
  assert.equal(await page.locator('.sd-rank-row').count(),1);
  assert.equal(await page.locator('.sd-rank-row').getAttribute('data-game'),'pool');
  const bar=page.locator('.sd-collection-progress');assert.equal(await bar.getAttribute('aria-valuenow'),'2');assert.equal(await bar.getAttribute('aria-valuemax'),'10');
  assert.equal(await bar.locator('span').evaluate(el=>Math.round(el.getBoundingClientRect().width/el.parentElement.getBoundingClientRect().width*100)),20);
  assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
 }
 await page.evaluate(user=>window.SamiDevProfileDetails.render(document.querySelector('#profile'),{...user,gameStatistics:[]}),user);
 assert(!await page.locator('.sd-game-statistics').isVisible());
 console.log('PROFILE_COLLECTION_BROWSER_PASS: real progress, played games only, empty history, responsive');
}finally{await browser.close();}
