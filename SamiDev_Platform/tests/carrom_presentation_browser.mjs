// Real renderer and touch input; isolated local service only.
import assert from 'node:assert/strict';
import fs from 'node:fs';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL||'http://127.0.0.1:8088';
assert(['127.0.0.1','localhost'].includes(new URL(base).hostname));
const out=process.env.SAMIDEV_TEST_ARTIFACTS||'/tmp/samidev-carrom-presentation';fs.mkdirSync(out,{recursive:true});
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const checks=[];
try{
 for(const [width,height,mobile,players] of [[320,568,true,0],[390,844,true,0],[430,932,true,0],[1440,900,false,0],[390,844,true,1],[1440,900,false,1]]){
  const context=await browser.newContext({viewport:{width,height},hasTouch:mobile,isMobile:mobile,deviceScaleFactor:mobile?3:1});
  // Returning player: skip the unrelated first-run tutorial, not game logic.
  await context.addInitScript(()=>localStorage.setItem('samidev.carrom.game_preferences',JSON.stringify({played:true,tutcomplete:true,ftime:false})));
  const page=await context.newPage(),errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto(base+'/index.html?play=1&players='+players);await page.waitForFunction(()=>window.__gameLogic?.started&&window.__samidevGameState.carromLayout,{},{timeout:30000});
  await page.waitForTimeout(500);
  const contextOptions=await page.evaluate(()=>document.querySelector('canvas').getContext('webgl').getContextAttributes());assert.equal(contextOptions.antialias,!mobile);
  const layout=await page.evaluate(()=>window.__samidevGameState.carromLayout);
  assert(layout.boardWidth<layout.width,'board exceeds viewport width');
  assert(layout.sliderWidth<layout.boardWidth,'slider exceeds board width');
  assert(layout.avatarY-layout.avatarRadius>layout.sliderY+layout.sliderHeight/2,'avatar overlaps slider');
  assert(layout.avatarY+layout.avatarRadius<layout.height,'own avatar clipped');
  assert(layout.sliderY-layout.sliderHeight/2>layout.boardY+layout.boardHeight/2,'slider overlaps board');
  assert.equal(await page.evaluate(()=>SamiDev.translate(['player_turn_me'])),'دورك للعب');
  if(mobile){
   assert(await page.evaluate(()=>window.__samidevGameState.performance.pixelRatio>=1.8));
   const rect=await page.locator('#game').boundingBox();
   const y=rect.y+layout.sliderY/layout.height*rect.height;
   const x=rect.x+rect.width/2;
   const delta=layout.sliderWidth/layout.width*rect.width*.2;
   const before=await page.evaluate(()=>window.__gameLogic.table.getStriKerPos());
   const cdp=await context.newCDPSession(page);
   for(const [type,px] of [['touchStart',x],['touchMove',x+delta],['touchEnd',x+delta]])await cdp.send('Input.dispatchTouchEvent',{type,touchPoints:type==='touchEnd'?[]:[{x:px,y}]});
   await page.waitForTimeout(300);
   const after=await page.evaluate(()=>window.__gameLogic.table.getStriKerPos());
   assert(Math.abs(after-before)>.05,'touch drag did not position striker');
  }
  await page.screenshot({path:out+`/carrom-${width}-${players}.png`});assert.deepEqual(errors,[]);
  checks.push({width,height,mobile,players,layout});await context.close();
 }
 fs.writeFileSync(out+'/report.json',JSON.stringify({ok:true,checks},null,2));console.log(JSON.stringify({ok:true,viewports:checks.length,artifacts:out}));
}finally{await browser.close();}
