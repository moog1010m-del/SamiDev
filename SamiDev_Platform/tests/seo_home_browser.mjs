import assert from 'node:assert/strict';import fs from 'node:fs/promises';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL;
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox']});
try {
 for(const width of [1366,390,320]){
  const context=await browser.newContext({viewport:{width,height:900}});
  try{
   const page=await context.newPage(),calls=[],errors=[],failed=[];
   page.on('request',r=>calls.push(r.url()));page.on('pageerror',e=>errors.push(e.message));page.on('response',r=>{if(r.status()>=400)failed.push(r.status()+':'+r.url());});
   await page.goto(base+'/',{waitUntil:'networkidle'});
   assert.equal(await page.locator('h1').count(),1);assert((await page.locator('h1').textContent()).includes('Plazr'));
   assert.equal(await page.locator('.game-card').count(),4);
   assert.equal(await page.locator('script[src],canvas,iframe').count(),0);
   assert(calls.every(u=>new URL(u).origin===base));assert(!calls.some(u=>/\/api\/|main\.js/.test(u)));
   assert.deepEqual(errors,[]);assert.deepEqual(failed,[]);
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth));
   assert.equal(await page.locator('.hero .play').getAttribute('href'),'/platform/');
   const graph=await page.locator('script[type="application/ld+json"]').evaluate(el=>JSON.parse(el.textContent)['@graph']);
   assert(graph.some(n=>n['@type']==='WebSite'&&n.url==='https://plazr.net/'));
   await fs.mkdir('/workspace/artifacts/plazr/seo',{recursive:true});await page.screenshot({path:`/workspace/artifacts/plazr/seo/home-${width}.png`,fullPage:true});
   console.log(JSON.stringify({width,publicHome:true,noAuthOrGameDownload:true,noOverflow:true}));
  }finally{await context.close();}
 }
}finally{await browser.close();}
