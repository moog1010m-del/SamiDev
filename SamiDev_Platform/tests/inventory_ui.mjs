// Install happy-dom in the test environment; this is a DOM interaction test, not visual rendering.
const {Window}=await import(process.env.SAMIDEV_HAPPY_DOM_MODULE||'happy-dom');
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
const root=path.resolve(import.meta.dirname,'..');
const source=fs.readFileSync(path.join(root,'game/inventory-ui.js'),'utf8');
const window=new Window({url:'https://game.test/games/pool/index.html'});
const data={ok:true,equipped:{pool_theme:'pool_midnight'},catalog:[
 {id:'pool_midnight',gameId:'pool',name:'ليل المجلس',description:'طاولة',slot:'pool_theme',owned:true,asset:'/images/themes/pool-midnight-preview.webp'},
 {id:'pool_emerald',gameId:'pool',name:'زمرد',description:'طاولة',slot:'pool_theme',owned:true,asset:'/images/themes/pool-emerald-preview.webp'},
 {id:'locked',gameId:'pool',name:'غير مملوك',slot:'pool_theme',owned:false},
 {id:'crazy8_original',gameId:'crazy8',name:'<img src=x onerror=alert(1)>',description:'اختبار نص غير موثوق',slot:'crazy8_theme',owned:true,asset:'https://attacker.test/pixel'},
]};
const posts=[],refreshes=[];window.SamiDevNetwork={send:m=>refreshes.push(m)};
window.SamiDevGames={current:()=>({id:'pool'})};
window.fetch=async (url,options)=>{
 assert.equal(options.credentials,'same-origin');
 if(url==='/api/store/equip'){
  const value=JSON.parse(options.body);assert.deepEqual(Object.keys(value),['itemId']);posts.push(value.itemId);data.equipped.pool_theme=value.itemId;
 }
 return {ok:true,json:async()=>structuredClone(data)};
};
window.eval(source);
const doc=window.document,trigger=doc.querySelector('.sd-inventory-trigger');trigger.focus();
await window.SamiDevInventory.open();
assert.equal(doc.querySelector('.sd-inventory').hidden,false);
assert.equal(doc.querySelectorAll('.sd-inventory-tabs button').length,4);
assert.equal(doc.querySelectorAll('.sd-inventory-card').length,2);
const equip=doc.querySelector('.sd-inventory-equip');await equip.onclick();
assert.deepEqual(posts,['pool_emerald']);assert.match(doc.querySelector('.sd-inventory-status').textContent,/تم الحفظ/);
assert.deepEqual(refreshes.map(x=>x.type),['refresh_cosmetics']);
doc.querySelector('[data-game="crazy8"]').click();
assert.equal(doc.querySelector('.sd-inventory-card img'),null);
assert.match(doc.querySelector('.sd-inventory-card h3').textContent,/<img/);
assert.equal(doc.querySelector('.sd-inventory-card h3').children.length,0);
const buttons=[...doc.querySelectorAll('.sd-inventory-panel button:not(:disabled)')];buttons.at(-1).focus();
doc.querySelector('.sd-inventory').dispatchEvent(new window.KeyboardEvent('keydown',{key:'Tab',bubbles:true,cancelable:true}));
assert.equal(doc.activeElement,buttons[0]);
doc.querySelector('.sd-inventory').dispatchEvent(new window.KeyboardEvent('keydown',{key:'Escape',bubbles:true}));
assert.equal(doc.querySelector('.sd-inventory').hidden,true);assert.equal(doc.activeElement,trigger);
console.log('PASS: four game tabs, owned inventory, equipment POST, text escaping, URL allowlist, focus trap and Escape');
await window.happyDOM.close();
