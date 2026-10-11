// Run with happy-dom (tests/package.json). Executes actual network/UI scripts;
// deterministic socket transport, no WebGL or device rendering claims.
import assert from 'node:assert/strict';
import fs from 'node:fs';
const {Window}=await import(process.env.SAMIDEV_HAPPY_DOM_MODULE||'happy-dom');
const read=name=>fs.readFileSync(new URL('../game/'+name,import.meta.url),'utf8');
const flush=()=>new Promise(resolve=>setTimeout(resolve,15));
for(const [game,entry] of Object.entries({pool:'games/pool/index.html',carrom:'index.html',crazy8:'games/crazy8/index.html',tablesoccer:'games/tablesoccer/index.html'})){
  const win=new Window({url:`https://game.test/${entry}?online=1&action=create&community=majlis`});
  const bridge=[],sent=[];let socket;
  const me={seat:0,accountId:'owner_test_1234',name:'صاحب الطاولة',connected:true};
  const other={seat:1,accountId:'guest_test_1234',name:'<img src=x onerror=alert(1)>',connected:true};
  const settings={gameId:game,players:0,seats:0,live:1};
  const room={roomId:'ABCDEF',communityId:'majlis',seat:0,capacity:2,settings,roster:[me,null],started:false,begun:false,cosmetics:{'0':{pool_theme:'pool_emerald'}}};
  class Socket extends win.EventTarget {
    static OPEN=1;static CONNECTING=0;static CLOSING=2;static CLOSED=3;
    readyState=0;
    constructor(){super();socket=this;queueMicrotask(()=>{this.readyState=1;this.dispatchEvent(new win.Event('open'));});}
    receive(data){this.dispatchEvent(new win.MessageEvent('message',{data:JSON.stringify(data)}));}
    send(value){const data=JSON.parse(value);sent.push(data);
      if(data.type==='create_room')queueMicrotask(()=>{this.receive({...room,type:'created',token:'test-reconnect-token'});this.receive({...room,type:'room_state'});});
      if(data.type==='leave_room')queueMicrotask(()=>this.receive({type:'left_room',roomId:room.roomId}));
    }
    close(code=1000){this.readyState=3;this.dispatchEvent(new win.CloseEvent('close',{code}));}
  }
  win.WebSocket=Socket;win.SamiDevMobile={postMessage:value=>bridge.push(JSON.parse(value))};
  win.alert=()=>{};win.document.body.innerHTML='<canvas id="game"></canvas><div id="status">Loading</div>';
  win.document.getElementById('game').getBoundingClientRect=()=>({left:0,top:0,width:390,height:740});
  win.fetch=async route=>({ok:true,json:async()=>String(route).includes('public-profile')?
    {ok:true,user:{id:other.accountId,displayName:other.name,username:'guest',wins:17,reputation:6,accountAgeDays:22,relation:'none',reputationDailyRemaining:4}}:
    {ok:true,equipped:{carrom_theme:'carrom_cat'}}});
  for(const name of ['samidev-games.js','samidev-network.js','waiting-room.js','room-menu.js','player-profile-ui.js'])win.eval(read(name));
  win.document.dispatchEvent(new win.Event('DOMContentLoaded'));
  try{
    let started=false;
    const start=win.SamiDevNetwork.connectFromLocation(text=>win.SamiDevWaitingRoom.progress(text)).then(data=>{started=true;return data;});
    await flush();
    const doc=win.document,waiting=doc.getElementById('sd-waiting');assert(waiting);
    assert.equal(started,false);assert.equal(doc.querySelectorAll('.sd-waiting-player').length,1);
    assert.equal(doc.querySelectorAll('.sd-waiting-top .sd-waiting-player').length,0);
    assert.equal(doc.querySelector('.sd-waiting-own').textContent,me.name);
    if(game==='pool')assert.equal(doc.querySelectorAll('.sd-waiting-mirror img[src="/images/themes/pool-emerald.webp"]').length,4);
    if(game==='carrom')assert.equal(doc.querySelector('.sd-waiting-board').getAttribute('src'),'/images/themes/cat-preview.webp');
    // Returning is a native navigation message, never leave_room / resignation.
    doc.getElementById('sd-room-back-button').click();
    assert.equal(bridge.at(-1).type,'room_background');assert.equal(socket.readyState,Socket.OPEN);
    assert(!sent.some(m=>m.type==='leave_room'||m.type==='move'));
    assert(!doc.getElementById('sd-exit-modal').classList.contains('open'));
    room.roster=[me,other];room.started=true;
    socket.receive({...room,type:'room_state'});
    assert.equal(doc.querySelectorAll('.sd-waiting-player').length,2);
    const opponent=doc.querySelector('.sd-waiting-top .sd-waiting-player');
    assert.equal(opponent.querySelector('span').textContent,other.name);
    assert.equal(opponent.querySelector('span').children.length,0);
    opponent.click();assert.equal(bridge.at(-1).type,'open_player_profile');assert.equal(bridge.at(-1).userId,other.accountId);
    // Web fallback profile really becomes visible; ID specificity used to hide it.
    win.SamiDevPlayerProfileUI.openSeat(1);await flush();
    const layer=doc.getElementById('sdpp-layer');
    assert.equal(layer.getAttribute('aria-hidden'),'false');assert.equal(win.getComputedStyle(layer).display,'flex');
    assert.equal(doc.querySelectorAll('.sdpp-stars .sdpp-icon-star').length,5);
    assert(doc.getElementById('sdpp-card').textContent.includes('17'));
    doc.querySelector('.sdpp-close').click();assert.equal(win.getComputedStyle(layer).display,'none');
    // Server start releases initialization, but preview stays until runtime is ready.
    socket.receive({...room,type:'start',snapshot:null,history:[]});await start;
    assert.equal(started,true);assert.equal(waiting.isConnected,true);
    assert(!sent.some(m=>m.type==='runtime_ready'));
    win.SamiDevWaitingRoom.ready();assert.equal(doc.getElementById('sd-waiting'),null);assert(!doc.body.classList.contains('sd-waiting'));
    // Explicit exit remains under the ellipsis and actually frees the seat.
    doc.getElementById('sd-room-menu-button').click();doc.getElementById('sd-exit').click();
    assert(doc.getElementById('sd-exit-modal').classList.contains('open'));
    await win.SamiDevRoomUI.exitMatch();assert(sent.some(m=>m.type==='leave_room'));assert.equal(socket.readyState,Socket.CLOSED);
  }finally{if(socket?.readyState===1){win.SamiDevNetwork.state.intentionalClose=true;socket.close();}await win.happyDOM.close();}
}
console.log('PASS: all four waiting tables; real roster only; safe names; back preserves socket; native profile bridge; visible web card; server-gated start; explicit leave');
