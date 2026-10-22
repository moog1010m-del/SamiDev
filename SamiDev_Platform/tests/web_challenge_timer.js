const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../game/platform/platform.js'),'utf8');
const start=source.indexOf('const deadline=performance.now()+Math.max(0,(c.expires-serverNow)*1000)');
const end=source.indexOf('tick();challengeCountdownTimer=setInterval(tick,100);',start);
assert(start>0&&end>start);
let now=500,polled=0;const number={},button={},style={};const context={performance:{now:()=>now},c:{expires:1030},serverNow:1000,card:{isConnected:true,querySelectorAll:()=>[button]},clock:{style:{setProperty:(k,v)=>style[k]=v}},number,clearInterval(){},challengeCountdownTimer:1,pollWebChallenge:()=>polled++};
vm.createContext(context);vm.runInContext(source.slice(start,end)+';globalThis.tick=tick;',context);
context.tick();assert.equal(number.textContent,'30');now+=1000;context.tick();assert.equal(number.textContent,'29');now+=29000;context.tick();assert.equal(number.textContent,'0');assert.equal(style['--remaining'],'0');assert.equal(button.disabled,true);assert.equal(polled,1);
console.log('CHALLENGE_TIMER_PASS: 30 -> 29 -> 0; ring drains; expired actions disabled; server refresh');
