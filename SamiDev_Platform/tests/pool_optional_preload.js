'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.join(__dirname,'../game');
const source=fs.readFileSync(path.join(root,'browser-runtime.js'),'utf8');
const norm=source.slice(source.indexOf('  const norm ='),source.indexOf('  function syncText'));
const load=source.slice(source.indexOf('  async function loadResources(){'),source.indexOf('  async function loadAssetsAndLogic(){'));
async function check(assetRoot){
 const requested=[],index=JSON.parse(fs.readFileSync(path.join(root,'games/pool/__assets.json'),'utf8'));
 const window={__assetImages:[],__SAMIDEV_ASSET_ROOT:assetRoot};
 const context={window,URL,Promise,Map,console,runtimeDebug:false,currentGame:{id:'pool'},isPool:true,isCarrom:false,isCrazy8:false,poolTableMode:null,
  startupMark(){},status:{style:{}},state:{images:new Map()},document:{createElement(){return {};},head:{append(){}}},
  Image:class{set src(value){queueMicrotask(()=>this.onload());}},
  fetch:async url=>{requested.push(url);return {ok:true,json:async()=>index,text:async()=>''};}};
 vm.createContext(context);await vm.runInContext(norm+load+'\nloadResources()',context);
 assert.ok(requested.some(p=>p.endsWith('__assets.json')));
 assert.ok(requested.some(p=>p.endsWith('scene-avatars/player_indicator.atlas')));
 assert.ok(!requested.some(p=>/(?:^|\/)imported\//.test(p)),requested.join('\n'));
 const saved=JSON.parse(window.__textAssets[requested[0]]);
 assert.ok(Object.hasOwn(saved,'pool/imported/8munos3yqj791.atlas'),'Native on-demand index preserved');
 return requested.length;
}
(async()=>console.log(JSON.stringify({ok:true,relativeRequests:await check(undefined),embeddedRequests:await check('http://127.0.0.1:1234/games/pool/')})))().catch(e=>{console.error(e);process.exitCode=1;});
