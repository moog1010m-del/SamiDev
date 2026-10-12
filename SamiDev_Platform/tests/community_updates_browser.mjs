// Real Chromium and local PostgreSQL/Redis/GameHost: two members, chat and a live table.
import assert from 'node:assert/strict';
import path from 'node:path';
import {spawnSync} from 'node:child_process';
const {chromium}=await import(process.env.SAMIDEV_PLAYWRIGHT_MODULE||'playwright-core');
const base=process.env.SAMIDEV_TEST_BASE_URL||'http://127.0.0.1:8088';
assert(['127.0.0.1','localhost'].includes(new URL(base).hostname),'Local test deployment required');
assert(process.env.SAMIDEV_TEST_DATABASE_URL,'Test database URL required for cleanup');
const browser=await chromium.launch({executablePath:process.env.SAMIDEV_CHROMIUM||'/usr/bin/chromium',headless:true,args:['--no-sandbox','--use-gl=angle','--use-angle=swiftshader','--enable-unsafe-swiftshader']});
const users=[],errors=[],contexts=[];
let table;
try {
  const pages=[];
  for(let i=0;i<2;i++) {
    const context=await browser.newContext();contexts.push(context);
    const registered=await context.request.post(base+'/api/auth/register',{data:{username:'cu_'+Date.now().toString(36)+'_'+i,password:'Test-password-123',displayName:'Community Check '+i}});
    assert.equal(registered.status(),200,await registered.text());users.push((await registered.json()).user);
    const page=await context.newPage();pages.push(page);page.on('pageerror',e=>errors.push(e.message));
    await page.goto(base+'/platform/?community=majlis');
    await page.locator('#community-room').waitFor({state:'visible'});
  }
  for(let i=0;i<2;i++) {
    const member=pages[i].locator('.community-member').filter({hasText:users[1-i].username});
    await member.waitFor({timeout:12000});
    assert.equal(await member.locator('.community-member-copy').count(),1);
    assert((await member.innerText()).includes(users[1-i].displayName));
  }
  const text='Community updates '+Date.now();
  await pages[0].locator('#community-chat-input').fill(text);
  await pages[0].locator('#community-chat-form').evaluate(form=>form.requestSubmit());
  for(const page of pages)await page.locator('.community-chat-message').filter({hasText:text}).waitFor({timeout:12000});
  table=await contexts[0].newPage();table.on('pageerror',e=>errors.push(e.message));
  await table.goto(base+'/games/pool/index.html?online=1&action=create&community=majlis&players=0&live=1');
  await table.waitForFunction(()=>window.SamiDevNetwork?.state.roomId,{},{timeout:30000});
  const room=await table.evaluate(()=>window.SamiDevNetwork.state.roomId);
  for(const page of pages) {
    const card=page.locator('#rooms .room-card').filter({hasText:room});
    await card.waitFor({timeout:12000});assert((await card.innerText()).includes(users[0].displayName));
  }
  const reply='Reply after table creation '+Date.now();
  await pages[1].locator('#community-chat-input').fill(reply);
  await pages[1].locator('#community-chat-form').evaluate(form=>form.requestSubmit());
  for(const page of pages)await page.locator('.community-chat-message').filter({hasText:reply}).waitFor({timeout:12000});
  assert.deepEqual(errors,[]);
  console.log(JSON.stringify({ok:true,checks:['Both players render the other member with a valid content element','Sent chat reaches both browsers through polling','A real pool table appears to both community viewers','Chat continues updating after table creation'],count:4}));
} finally {
  if(table&&!table.isClosed())await table.evaluate(()=>window.SamiDevNetwork?.leaveRoom({closeSocket:true})).catch(()=>{});
  for(const context of contexts)await context.request.post(base+'/api/communities/majlis/leave',{data:{}}).catch(()=>{});
  await browser.close();
  if(users.length) {
    const clean=spawnSync(process.env.SAMIDEV_TEST_PYTHON||'python3',['-c',`import asyncio,json,os,sys,asyncpg
async def main():
 c=await asyncpg.connect(os.environ['SAMIDEV_TEST_DATABASE_URL'])
 for user in json.load(sys.stdin):
  await c.execute('DELETE FROM samidev_social_documents WHERE key=$1 OR key=$2','sdp:user:'+user['id'],'sdp:username:'+user['username'].lower())
 await c.close()
asyncio.run(main())`],{input:JSON.stringify(users),encoding:'utf8',cwd:path.resolve(import.meta.dirname,'..')});
    assert.equal(clean.status,0,clean.stderr);
  }
}
