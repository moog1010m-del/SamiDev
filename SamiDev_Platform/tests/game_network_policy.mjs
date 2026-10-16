import assert from 'node:assert/strict';
import fs from 'node:fs';
import vm from 'node:vm';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL;assert.equal(new URL(base).hostname,'127.0.0.1');
const network=fs.readFileSync(new URL('../game/samidev-network.js',import.meta.url),'utf8');
const start=network.indexOf('  function socketUrl('),end=network.indexOf('\n  function send(',start);
for(const origin of ['https://game.test','http://127.0.0.1:9000']){
 const context={URL,URLSearchParams,location:{href:origin+'/games/pool/index.html',search:'?ticket=private-fixture'},window:{__SAMIDEV_WS_URL:'wss://outside.invalid/steal'}};
 vm.createContext(context);vm.runInContext(network.slice(start,end)+';this.result=socketUrl();',context);
 const socket=new URL(context.result);assert.equal(socket.host,new URL(origin).host);assert.equal(socket.pathname,'/ws');assert.equal(socket.searchParams.get('ticket'),'private-fixture');
}
const browser=await chromium.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
try{
 const context=await browser.newContext(),page=await context.newPage(),external=[],violations=[];
 await context.route('**/*',route=>{const u=new URL(route.request().url());if(u.origin!==base&&['http:','https:'].includes(u.protocol)){external.push(u.origin);return route.abort();}return route.continue();});
 await page.exposeFunction('auditViolation',directive=>violations.push(directive));
 await page.addInitScript(()=>document.addEventListener('securitypolicyviolation',event=>window.auditViolation(event.effectiveDirective)));
 const response=await page.goto(base+'/index.html?play=1&live=0');
 const csp=response.headers()['content-security-policy'];assert(csp.includes("connect-src 'self';"));assert(!csp.includes('googleapis.com'));
 await page.waitForFunction(()=>!!window.__gameLogic,{},{timeout:25000});
 await page.evaluate(async()=>{
  await fetch('https://identitytoolkit.googleapis.com/game-resource-fixture').catch(()=>{});
  const image=new Image();image.src='https://outside.invalid/pixel.png';
  const audio=new Audio('https://outside.invalid/sound.mp3');audio.load();
  window.audio.load('https://outside.invalid/effect.mp3');
 }).then(()=>assert.fail('asset loader must reject remote audio'),error=>assert(error.message.includes('External game assets')));
 await page.waitForTimeout(200);
 assert.equal(external.length,0,'CSP must block requests before external contact');
 assert(violations.includes('connect-src'));assert(violations.includes('img-src'));
 const source=fs.readFileSync(new URL('../game/browser-runtime.js',import.meta.url),'utf8');
 const a=source.indexOf('  const norm ='),b=source.indexOf('\n\n  function syncText',a);
 const sandbox={};vm.createContext(sandbox);vm.runInContext(source.slice(a,b)+';this.normalize=norm;',sandbox);
 for(const url of ['https://outside.invalid/a','//outside.invalid/a','\\\\outside.invalid/a',' data:image/svg+xml,x','data:text/html,x','javascript:alert(1)','\thttps://outside.invalid/a'])assert.throws(()=>sandbox.normalize(url));
 assert.equal(sandbox.normalize('~/pool/images/a.webp'),'images/a.webp');assert.equal(sandbox.normalize('/images/default-avatar.png'),'/images/default-avatar.png');
 const auth=await context.request.get(base+'/platform/index.html');const authCsp=auth.headers()['content-security-policy'];
 assert(authCsp.includes('https://identitytoolkit.googleapis.com'));assert(authCsp.includes('https://securetoken.googleapis.com'));assert(authCsp.includes('https://network-policy-test.firebaseapp.com'));
 console.log('GAME_NETWORK_POLICY_PASS: same-origin sockets, no override ticket leakage, remote assets blocked, auth preserved');
}finally{await browser.close();}
