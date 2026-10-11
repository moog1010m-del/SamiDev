'use strict';
const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const source=fs.readFileSync(path.join(__dirname,'../game/carrom-themes.js'),'utf8');
function setup(fetcher){const context={window:{},fetch:fetcher,setTimeout,clearTimeout,AbortController};vm.runInNewContext(source,context);return context.window.SamiDevCarromThemes;}
const valid={equipped:{carrom_theme:'carrom_cat'},catalog:[{id:'carrom_cat',slot:'carrom_theme',owned:true}]};
(async()=>{
 const themes=setup();
 assert.equal((await themes.resolve()).id,'carrom_classic');
 assert.equal(themes.fromSnapshot(valid).id,'carrom_cat');
 for(const payload of [{}, {equipped:{carrom_theme:'__proto__'}}, {equipped:{carrom_theme:'../../bad'},catalog:[{id:'../../bad',slot:'carrom_theme',owned:true}]}, {...valid,catalog:[{id:'carrom_cat',slot:'other',owned:true}]}, {...valid,catalog:[{id:'carrom_cat',slot:'carrom_theme',owned:false}]}])assert.equal(themes.fromSnapshot(payload).id,'carrom_classic');
 const remote=setup(async(url,options)=>{assert.equal(url,'/api/store');assert.equal(options.credentials,'same-origin');assert.equal(options.cache,'no-store');return {ok:true,json:async()=>valid};});
 assert.equal((await remote.resolve()).id,'carrom_cat');
 assert.equal((await setup(async()=>({ok:false})).resolve()).id,'carrom_classic');
 assert.equal((await setup(async()=>{throw Error('offline')}).resolve()).id,'carrom_classic');
 assert.equal((await setup(async()=>({ok:true,json:async()=>{throw Error('bad json')}})).resolve()).id,'carrom_classic');
 let aborted=false;
 assert.equal((await setup((url,{signal})=>new Promise((resolve,reject)=>signal.addEventListener('abort',()=>{aborted=true;reject(Error('abort'))}))).resolve()).id,'carrom_classic');
 assert(aborted,'timeout must abort the pending store request');
 console.log('carrom_theme_selection: OK (server selection, allowlist, ownership, guest/offline fallback, timeout)');
})().catch(error=>{console.error(error);process.exitCode=1;});
