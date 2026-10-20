import fs from 'node:fs/promises';
import assert from 'node:assert/strict';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const origin=process.env.SAMIDEV_TEST_BASE_URL;assert(['localhost','127.0.0.1'].includes(new URL(origin).hostname));
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
const axe=await fs.readFile(process.env.SAMIDEV_AXE_PATH||'/workspace/.samidev-ui-tools/node_modules/axe-core/axe.min.js','utf8');const results=[];
try{
 for(const width of [390,1366])for(const theme of ['light','dark']){
  const context=await browser.newContext({viewport:{width,height:920},hasTouch:width<600,serviceWorkers:'block'});const page=await context.newPage();const failures=[];page.on('response',r=>{if(r.status()>=400)failures.push([r.status(),new URL(r.url()).pathname]);});
  for(const state of ['home','room','profile']){
   if(state!=='profile'){await page.goto(origin+'/platform/'+(state==='room'?'?community=majlis':''));await page.locator(state==='home'?'#app':'#community-room').waitFor({state:'visible'});}
   await page.evaluate(t=>document.documentElement.dataset.theme=t,theme);
   if(state==='profile'){await page.evaluate(async()=>{const d=await fetch('/api/users/search?q=Audit_Peer').then(r=>r.json());const user=(d.users||[])[0];if(user)window.SamiDevMobilePlatform.openProfile(user.id);});await page.locator('#community-profile-modal.open').waitFor();await page.locator('#community-profile-loading').waitFor({state:'hidden'});}
   await page.evaluate(axe);const result=await page.evaluate(async()=>{const r=await window.axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa','best-practice']}});return r.violations.map(v=>({id:v.id,impact:v.impact,description:v.description,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary,html:n.html.slice(0,280)}))}));});
   const unexpected=result.filter(v=>v.id!=='meta-viewport');assert.deepEqual(unexpected,[],JSON.stringify({width,theme,state,unexpected}));
   assert.equal(result.filter(v=>v.id==='meta-viewport').length,1,'zoom prevention remains an explicit reported exception, not a hidden audit');
   const viewport=await page.locator('meta[name="viewport"]').getAttribute('content');assert(viewport.includes('user-scalable=no')&&viewport.includes('maximum-scale=1'));
   assert((await page.locator('meta[name="robots"]').getAttribute('content')).includes('noindex'),'lobby indexing policy preserved');
   assert(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'no horizontal overflow');
   if(state==='home'){
    await page.locator('.community-card').first().waitFor();await page.evaluate(()=>{window.__qualityCard=document.querySelector('.community-card');window.__qualityFlag=window.__qualityCard.querySelector('img');window.__qualityCard.focus();});
    await page.route('**/api/communities',async route=>{const response=await route.fetch(),body=await response.json();body.communities[0].onlineCount=42;await route.fulfill({response,json:body});});
    await page.waitForFunction(()=>document.querySelector('.community-card [data-community-online]')?.textContent==='42');
    assert(await page.evaluate(()=>window.__qualityCard===document.querySelector('.community-card')&&window.__qualityFlag===window.__qualityCard.querySelector('img')&&document.activeElement===window.__qualityCard),'poll updates counters without replacing images or keyboard focus');
    await page.unroute('**/api/communities');
   }
   results.push({width,theme,state,violations:result});console.log(JSON.stringify({width,theme,state,violations:result}));
  }
  assert.deepEqual(failures,[],'guest startup and ordinary lobby requests should not fail');
  await context.close();
 }
 const out=process.env.SAMIDEV_TEST_ARTIFACTS||'/workspace/artifacts/plazr/lobby-quality';await fs.mkdir(out,{recursive:true});await fs.writeFile(out+'/'+'verified'+'-axe.json',JSON.stringify(results,null,2));
}finally{await browser.close();}
