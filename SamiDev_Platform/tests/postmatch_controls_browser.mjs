import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
try{
 const page=await browser.newPage({viewport:{width:1200,height:800}});const errors=[];page.on('pageerror',e=>errors.push(e.message));
 await page.route('https://fixture.test/**',r=>r.fulfill({contentType:'text/html',body:'<canvas id="game" width="1200" height="800"></canvas>'}));
 await page.goto('https://fixture.test/');
 await page.evaluate(()=>{
  window.__over=false;window.__returns=0;window.__replays=0;
  window.__SAMIDEV_APP_HOST={returnToPlatform:async()=>window.__returns++};
  window.SamiDevGameUI={isGameOver:()=>window.__over};
  window.SamiDevGames={current:()=>({id:'pool'})};
  window.SamiDevNetwork={state:{roomId:'TEST',communityId:'majlis',seat:0,capacity:2,begun:true,settings:{},roster:[{seat:0,accountId:'me'},{seat:1,accountId:'opponent',name:'friend'}]},on(){},leaveRoom:async()=>({ok:true})};
  const scene={gameOverPopup:{visible:true,bestShotButton:{visible:true}},shotOfTheGameShowing:false,showShotOfTheGame(){window.__replays++;this.shotOfTheGameShowing=true;this.gameOverPopup.visible=false;}};
  window.__samidevGameState={gameLogic:{sceneMgr:scene,shotOfTheGame:{seat:0}}};
  window.fetch=async()=>({ok:true,json:async()=>({ok:true,user:{id:'opponent',displayName:'friend'}})});
 });
 for(const file of ['room-menu.js','player-profile-ui.js'])await page.addScriptTag({path:fileURLToPath(new URL('../game/'+file,import.meta.url))});
 await page.click('#sd-room-menu-button');await page.click('#sd-exit');assert(await page.locator('#sd-exit-modal').evaluate(e=>e.classList.contains('open')),'live match still asks before resignation');await page.click('#sd-exit-cancel');
 await page.evaluate(()=>window.__over=true);
 await page.waitForSelector('#sd-match-replay button');await page.click('#sd-match-replay button');
 await page.waitForTimeout(1600);assert(!await page.locator('#sdpp-rating-layer').evaluate(e=>e.classList.contains('open')),'rating must wait until replay ends');
 await page.evaluate(()=>{const s=window.__samidevGameState.gameLogic.sceneMgr;s.shotOfTheGameShowing=false;s.gameOverPopup.visible=true;window.__replays=0;});
 await page.waitForSelector('.sdpp-rating-actions button');await page.click('[data-like="1"]');
 await page.waitForTimeout(2200);assert.equal(await page.evaluate(()=>window.__returns),0,'rating never auto exits');
 await page.click('#sd-match-replay button');assert.equal(await page.evaluate(()=>window.__replays),1,'replay uses native animation');
 await page.waitForTimeout(550);assert(await page.locator('#sd-match-replay').isHidden(),'toolbar stays out of the replay');
 await page.click('#sd-room-menu-button');await page.click('#sd-exit');await page.waitForFunction(()=>window.__returns===1);assert(!await page.locator('#sd-exit-modal').evaluate(e=>e.classList.contains('open')),'finished match leaves in one click');
 assert.deepEqual(errors,[]);console.log('POSTMATCH_CONTROLS_BROWSER_PASS');
}finally{await browser.close();}
