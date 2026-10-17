import assert from 'node:assert/strict';
import fs from 'node:fs';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const cfg=JSON.parse(fs.readFileSync(process.env.SAMIDEV_CHAT_BENCH_CONFIG,'utf8'));
const browser=await chromium.launch({executablePath:process.env.SAMIDEV_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox']});
const samples=[],errors=[],run='BENCH_'+Date.now();
const observations=[];
const percentile=(rows,p)=>rows.length?[...rows].sort((a,b)=>a-b)[Math.ceil(p*rows.length)-1]:null;
let failure=null;
try{
 for(const [room,pair] of Object.entries(cfg.rooms)){
  const pages=[];
  for(let seat=0;seat<2;seat++){
   const {base,token}=pair[seat];assert.equal(new URL(base).hostname,'127.0.0.1');
   const context=await browser.newContext({extraHTTPHeaders:cfg.legacy?{'X-Forwarded-Proto':'https',Origin:cfg.origin||base}:{}});
   if(token)await context.addCookies([{name:'samidev_session',value:token,url:base,httpOnly:true,sameSite:'Lax'}]);
   else {
    const auth=await context.request.post(base+'/api/auth/guest',{headers:{Origin:cfg.origin||base},data:{}});assert.equal(auth.status(),200);
    const token=/samidev_session=([^;]+)/.exec(auth.headers()['set-cookie']||'')?.[1];
    if(token)await context.addCookies([{name:'samidev_session',value:token,url:base,httpOnly:true,sameSite:'Lax'}]);
   }
   const page=await context.newPage();pages.push(page);page.on('pageerror',e=>errors.push(e.message));
   await page.addInitScript(({run,disableLive})=>{
    if(disableLive)window.EventSource=undefined;
    const metrics=window.__chatBench={sent:{},events:{},dom:{},streamStates:[],historyCalls:0};
    const fetch0=window.fetch;
    window.fetch=async function(input,options){
     const url=new URL(typeof input==='string'?input:input.url,location.href);
     let nonce=null;
     if(url.pathname.endsWith('/chat')&&options?.method==='POST'){
      const body=JSON.parse(options.body||'{}');nonce=body.clientMessageId||body.text;
      if(body.text?.startsWith(run))metrics.sent[nonce]={start:Date.now(),text:body.text};else nonce=null;
     }
     if(/^\/api\/communities\/[a-z]+$/.test(url.pathname)&&(!options?.method||options.method==='GET'))metrics.historyCalls++;
     const response=await fetch0.apply(this,arguments);
     if(nonce){metrics.sent[nonce].ack=Date.now();metrics.sent[nonce].status=response.status;}
     return response;
    };
    const Source=window.EventSource;
    if(Source)window.EventSource=class extends Source{
     constructor(...args){super(...args);this.addEventListener('open',()=>metrics.streamStates.push('open'));this.addEventListener('error',()=>metrics.streamStates.push('error'));this.addEventListener('message',e=>{const data=JSON.parse(e.data);if(data.type==='snapshot')metrics.snapshotAt=Date.now();if(data.type==='message'&&data.message?.text?.startsWith(run))metrics.events[data.message.clientMessageId]=Date.now();});}
    };
    new MutationObserver(()=>{
     for(const row of document.querySelectorAll('.community-chat-message')){
      const text=row.querySelector('p')?.textContent;
      if(text?.startsWith(run)&&metrics.dom[text]===undefined)metrics.dom[text]=Date.now();
     }
    }).observe(document,{childList:true,subtree:true});
   },{run,disableLive:cfg.disableLive===true});
   await page.goto(base+'/platform/?community='+room);await page.locator('#community-room').waitFor({timeout:15000});
   if(!cfg.legacy){
    await page.waitForFunction(()=>window.__chatBench.snapshotAt,{},{timeout:15000});
    await page.route('**/api/communities/'+room,route=>route.abort());
   }
  }
  for(let n=0;n<cfg.samplesPerDirection;n++)for(let sender=0;sender<2;sender++){
   const source=pages[sender],target=pages[1-sender],text=`${run} ${room} ${sender} ${n}`;
   await source.locator('#community-chat-input').fill(text);await source.locator('#community-chat-form button[type=submit]').click();
   await target.waitForFunction(text=>window.__chatBench.dom[text]!==undefined,text,{timeout:cfg.legacy?6500:1500,polling:10});
   await source.waitForFunction(text=>Object.values(__chatBench.sent).some(r=>r.text===text&&r.ack!==undefined),text,{timeout:1500,polling:10});
   const sent=await source.evaluate(text=>Object.entries(__chatBench.sent).find(([nonce,r])=>r.text===text),text);
   assert(sent,'instrumentation captured HTTP send');const [nonce,timing]=sent;
   assert.equal(timing.status,200,'server confirmed the message');
   const received=await target.evaluate(({text,nonce})=>({dom:__chatBench.dom[text],event:__chatBench.events[nonce]??null}),{text,nonce});
   const sample={room,direction:sender,nonce,httpMs:timing.ack===undefined?null:timing.ack-timing.start,eventMs:received.event===null?null:received.event-timing.start,domMs:received.dom-timing.start};samples.push(sample);
   if(!cfg.legacy)assert.notEqual(received.event,null,'message must arrive by SSE, not snapshot');
  }
  for(const page of pages){observations.push(await page.evaluate(()=>({streamStates:__chatBench.streamStates,historyCalls:__chatBench.historyCalls})));await page.request.post(new URL('/api/communities/'+room+'/leave',page.url()).href,{headers:{Origin:cfg.origin||new URL(page.url()).origin},data:{}});await page.context().close();}
 }
 assert.deepEqual(errors,[],'no browser script errors');
 assert.equal(samples.length,Object.keys(cfg.rooms).length*2*cfg.samplesPerDirection);
 if(!cfg.legacy)assert(percentile(samples.map(r=>r.domMs),.95)<Number(process.env.SAMIDEV_CHAT_P95_MS||250),'local live p95 exceeds threshold');
 if(cfg.disableLive)assert(percentile(samples.map(r=>r.domMs),.95)>1000,'polling control must expose the multi-second delay');
}catch(e){failure=e.message;}
finally{
 await browser.close();
 const result={ok:failure===null,mode:cfg.disableLive?'current-postgres-polling-only':'current-postgres-two-gateways-no-polling',samples:samples.length,p50Ms:percentile(samples.map(r=>r.domMs),.5),p95Ms:percentile(samples.map(r=>r.domMs),.95),maxMs:Math.max(0,...samples.map(r=>r.domMs)),observations,errors,failure,details:samples};
 fs.writeFileSync(process.env.SAMIDEV_CHAT_BENCH_REPORT,JSON.stringify(result,null,2));
 console.log(JSON.stringify({...result,details:undefined,observations:undefined}));
 if(failure)process.exitCode=1;
}
