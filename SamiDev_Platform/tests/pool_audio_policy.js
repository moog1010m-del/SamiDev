'use strict';
const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const source=fs.readFileSync(require('node:path').join(__dirname,'../game/browser-runtime.js'),'utf8');
const segment=source.slice(source.indexOf('  const audios ='),source.indexOf('  function translate(args)'));
function setup(pool){let now=0;const instances=[];class Audio{constructor(uri){this.uri=uri;this.count=0;instances.push(this);}play(){this.count++;return Promise.resolve();}pause(){}}const window={};const hostBridge={game_preferences:{}};vm.runInNewContext(segment,{window,Audio,hostBridge,norm:u=>u,isPool:pool,performance:{now:()=>now},Map,Math});return {audio:window.audio,instances,window,hostBridge,tick:n=>now+=n};}
const pool=setup(true),hard=pool.audio.load('/games/pool/sounds/ball1.m4a'),soft=pool.audio.load('/games/pool/sounds/ball_soft2.m4a'),rail=pool.audio.load('/games/pool/sounds/rail1.m4a');
pool.audio.play(soft,.3);assert.equal(pool.instances[1].count,0,'tiny rubbing contacts stay silent');
pool.audio.play(hard,1);assert.equal(pool.instances[0].volume,.4);assert.equal(pool.instances[0].count,1);
pool.audio.play(soft,1);assert.equal(pool.instances[1].count,0,'one collision-family voice per 45 ms');
pool.tick(46);pool.audio.play(soft,1);assert.equal(pool.instances[1].volume,.2);assert.equal(pool.instances[1].count,1);
pool.audio.play(rail,.75);assert.equal(pool.instances[2].volume,.75,'rail effect is unchanged');
pool.audio.suspend();pool.tick(50);pool.audio.play(hard,1);assert.equal(pool.instances[0].count,1);pool.audio.resume();pool.hostBridge.game_preferences.mute=true;pool.audio.play(hard,1);assert.equal(pool.instances[0].count,1);
const other=setup(false),id=other.audio.load('/games/carrom/sounds/ball1.m4a');other.audio.play(id,1);assert.equal(other.instances[0].volume,1,'other games keep their gain');
console.log('POOL_AUDIO_PASS: weak contact gate, reduced gain, burst limit, rail preservation, mute/suspend, other-game isolation');
