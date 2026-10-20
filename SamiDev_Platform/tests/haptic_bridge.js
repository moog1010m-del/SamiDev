const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm');
const source=fs.readFileSync(require('node:path').join(__dirname,'../game/browser-runtime.js'),'utf8');
const code=source.slice(source.indexOf('  // Native games pass amplitude'),source.indexOf('  const hostBridge = {'));
function fixture(native=false,browser=true){
 const vibrations=[],messages=[],events={};let now=100;
 const context={state:{disposed:false},hostBridge:{game_preferences:{}},document:{hidden:false,addEventListener:(n,f)=>events[n]=f},navigator:browser?{vibrate:v=>vibrations.push(v)}:{},performance:{now:()=>now},window:{}};
 if(native)context.window.SamiDevMobile={postMessage:s=>messages.push(JSON.parse(s))};
 vm.runInNewContext(code,context);return {context,h:context.window.SamiDevGameHaptics,vibrations,messages,events,tick:()=>now+=100};
}
const f=fixture();assert(f.h.supported());f.h.pulse(1,5);assert.equal(f.vibrations[0],5,'stock click uses duration, not amplitude');
f.tick();f.h.pattern([.5,0,.7],[50,50,25]);assert.deepEqual(JSON.parse(JSON.stringify(f.vibrations.at(-1))),[50,50,25]);
f.tick();f.h.pattern([.2,.4,0,0,.9],[10,20,10,5,30]);assert.deepEqual(JSON.parse(JSON.stringify(f.vibrations.at(-1))),[30,15,30]);
f.tick();f.h.pattern([0,.5],[20,30]);assert.deepEqual(JSON.parse(JSON.stringify(f.vibrations.at(-1))),[0,20,30]);
f.tick();f.h.pulse(24);assert.equal(f.vibrations.at(-1),24,'legacy duration remains valid');
let count=f.vibrations.length;f.h.pulse(1,20);assert.equal(f.vibrations.length,count,'burst throttled');
f.tick();for(const [a,d] of [[[NaN],[20]],[[1],[-5]],[[1],[Infinity]],[[1,1],[10]],[[1,1,1,1,1],[500,500,500,500,500]],[[0],[100]]])f.h.pattern(a,d);
assert.equal(f.vibrations.length,count,'malformed/unbounded/silent patterns rejected');
f.context.hostBridge.game_preferences['@SamiDev/haptic']={enabled:false};f.h.pulse(1,30);assert.equal(f.vibrations.length,count,'game preference respected');
f.context.hostBridge.game_preferences['@SamiDev/haptic']={enabled:true,intensity:0};f.h.pulse(1,30);assert.equal(f.vibrations.length,count);
f.context.hostBridge.game_preferences={};f.context.window.__SAMIDEV_AUDIO_SUSPENDED=true;f.h.pulse(1,30);assert.equal(f.vibrations.length,count);f.context.window.__SAMIDEV_AUDIO_SUSPENDED=false;
f.context.document.hidden=true;f.events.visibilitychange();assert.equal(f.vibrations.at(-1),0,'hide cancels');count=f.vibrations.length;f.h.pulse(1,30);assert.equal(f.vibrations.length,count);
const n=fixture(true,false);assert(n.h.supported(),'native channel works without navigator.vibrate');n.h.pulse(.75,60);assert.deepEqual(n.messages,[{type:'game_haptic',amplitudes:[.75],durations:[60]}]);assert.equal(n.vibrations.length,0,'one transport only');
n.h.cancel();assert.equal(n.messages.at(-1).action,'cancel');n.tick();n.h.pattern([1,0,.4],[20,50,30]);assert.deepEqual(n.messages.at(-1),{type:'game_haptic',amplitudes:[1,0,.4],durations:[20,50,30]});
assert(!fixture(false,false).h.supported(),'unsupported browser is a silent no-op');
console.log('HAPTIC_BRIDGE_PASS: amplitude/duration, pauses, merging, native channel, preferences, lifecycle cancellation, bounds and burst control');
