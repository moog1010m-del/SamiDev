'use strict';
// LinkeDOM exercises the actual HTML, event handlers, and server APIs; it does not render pixels.
const assert = require('node:assert/strict');
const vm = require('node:vm');
const {parseHTML} = require('linkedom');
const base = process.argv[2];
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
async function until(check, message) {
  for (let n = 0; n < 100; n++) { if (check()) return; await sleep(20); }
  throw new Error(message);
}
async function main() {
  let cookie = '';
  const requests = [];
  async function apiFetch(route, opts = {}) {
    const r = await fetch(new URL(route, base), {...opts, headers: {...opts.headers, Cookie: cookie}});
    const setCookie = r.headers.getSetCookie();
    if (setCookie.length) cookie = setCookie.map(x => x.split(';')[0]).join('; ');
    requests.push({route, status:r.status});
    return r;
  }
  const registered = await apiFetch('/api/auth/register', {method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({username:'v25_ui_test', password:'Test-password-123', displayName:'UI Test'})});
  assert.equal(registered.status, 200, await registered.text());
  const response = await apiFetch('/platform/');
  assert.equal(response.status, 200);
  assert.equal(response.headers.get('Cache-Control'), 'no-store');
  assert.match(response.headers.get('X-SamiDev-Build'), /^samidev-v25-/);
  const {document} = parseHTML(await response.text());
  const $ = selector => document.querySelector(selector);
  assert.equal($('meta[name="samidev-release"]').content, 'V25');
  const storage = () => { const m = new Map(); return {getItem:k=>m.get(k)||null, setItem:(k,v)=>m.set(k,String(v)), removeItem:k=>m.delete(k)}; };
  const context = {document, console, URL, URLSearchParams,
    location:{href:base+'/platform/', search:'', pathname:'/platform/'},
    history:{replaceState(){}}, localStorage:storage(), sessionStorage:storage(),
    fetch:apiFetch, matchMedia:()=>({matches:false}), requestAnimationFrame:fn=>fn(),
    setInterval:()=>0, clearInterval(){}, setTimeout:()=>0, clearTimeout(){}};
  context.window = context;
  vm.createContext(context);
  for (const script of document.querySelectorAll('script[src]')) {
    assert.match(script.getAttribute('src'), /\?v=[a-f0-9]{16}$/);
    const r = await apiFetch(script.getAttribute('src'));
    assert.equal(r.status, 200);
    vm.runInContext(await r.text(), context, {filename:script.getAttribute('src')});
  }
  await until(() => !$('#app').classList.contains('hidden') && $('.community-card'), 'Authenticated lobby did not load');
  await $('.community-card').onclick();
  assert(!$('#community-room').classList.contains('hidden'));
  assert(!$('#quick-create-tablesoccer').closest('.hidden'));
  $('#quick-create-tablesoccer').click();
  assert(!$('#create-modal').classList.contains('hidden'));
  assert.equal($('#create-game').value, 'tablesoccer');
  assert.equal($('#choose-tablesoccer').getAttribute('aria-pressed'), 'true');
  assert.equal($('#choose-carrom').getAttribute('aria-pressed'), 'false');
  for (const el of document.querySelectorAll('.soccer-setting')) assert(!el.classList.contains('hidden'));
  for (const el of document.querySelectorAll('.carrom-setting')) assert(el.classList.contains('hidden'));
  assert.match($('#create-go').textContent, /كرة الطاولة/);
  // Explicitly select options; LinkeDOM does not implement the browser's default selectedIndex.
  $('#create-soccer-mode option[value="1"]').selected = true;
  $('#create-goals option[value="2"]').selected = true;
  $('#create-passes option[value="1"]').selected = true;
  await $('#create-go').onclick();
  const soccer = new URL(context.location.href, base);
  assert.equal(soccer.pathname, '/games/tablesoccer/index.html');
  assert.equal(soccer.searchParams.get('game'), 'tablesoccer');
  assert.equal(soccer.searchParams.get('live'), '1');
  assert.equal(soccer.searchParams.get('goalsToWin'), '2');
  assert.equal(soccer.searchParams.get('passes'), '1');
  assert(soccer.searchParams.get('ticket'));
  assert(soccer.searchParams.get('community'));
  assert.equal((await apiFetch(soccer.pathname)).status, 200);
  $('#choose-carrom').click();
  assert.equal($('#create-game').value, 'carrom');
  assert.equal($('#choose-carrom').getAttribute('aria-pressed'), 'true');
  for (const el of document.querySelectorAll('.soccer-setting')) assert(el.classList.contains('hidden'));
  for (const el of document.querySelectorAll('.carrom-setting')) assert(!el.classList.contains('hidden'));
  $('#create-gamemode option[value="0"]').selected = true;
  $('#create-break option[value="0"]').selected = true;
  await $('#create-go').onclick();
  const carrom = new URL(context.location.href, base);
  assert.equal(carrom.pathname, '/index.html');
  assert.equal(carrom.searchParams.get('game'), 'carrom');
  assert(carrom.searchParams.get('ticket'));
  assert.equal(carrom.searchParams.has('goalsToWin'), false);
  assert.equal((await apiFetch(carrom.pathname)).status, 200);
  $('#create-modal [data-close]').click();
  assert($('#create-modal').classList.contains('hidden'));
  $('#open-create').click();
  assert(!$('#create-modal').classList.contains('hidden'));
  $('#quick-create-carrom').click();
  assert.equal($('#create-game').value, 'carrom');
  assert(requests.every(r=>r.status===200), JSON.stringify(requests));
  console.log(JSON.stringify({ok:true, realHttp:true, realAccountsAndTickets:true,
    gameCardsVisibleInDom:true, selectionAndSettings:true, routes:['carrom','tablesoccer'],
    visualBrowserTest:false}, null, 2));
}
main().catch(error => {console.error(error); process.exitCode=1;});
