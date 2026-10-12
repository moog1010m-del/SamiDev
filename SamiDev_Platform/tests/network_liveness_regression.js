'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
let now=0,nextTimer=1,reloads=0,renewals=0;
const timers=new Map(),sockets=[],documents=new Map();
const timeout=(fn,ms,repeat=false)=>{const id=nextTimer++;timers.set(id,{fn,due:now+ms,ms,repeat});return id;};
const clear=id=>timers.delete(id);
class Clock extends Date {static now(){return now;}}
class Socket {
 static OPEN=1;static CLOSING=2;
 constructor(url){this.url=url;this.events=new Map();this.sent=[];this.readyState=0;sockets.push(this);
  queueMicrotask(()=>{if(sockets.indexOf(this)===0)this.emit('error',{});else{this.readyState=1;this.emit('open',{});}});
 }
 addEventListener(type,fn){if(!this.events.has(type))this.events.set(type,new Set());this.events.get(type).add(fn);}
 removeEventListener(type,fn){this.events.get(type)?.delete(fn);}
 emit(type,event){for(const fn of [...this.events.get(type)||[]])fn(event);}
 message(value){this.emit('message',{data:JSON.stringify(value)});}
 send(raw){const msg=JSON.parse(raw);this.sent.push(msg);if(msg.type==='create_room'){
  this.message({type:'created',roomId:'ABCDEF',seat:0,token:'test-token',capacity:2,settings:{gameId:'carrom'},roster:[]});
  this.message({type:'start',settings:{gameId:'carrom'},roster:[],moveCount:0});
 }}
 close(code=1000){this.readyState=3;this.emit('close',{code});}
}
const ctx={window:{SamiDevGames:{current:()=>({id:'carrom'}),settings:()=>({players:0})}},
 location:{protocol:'https:',host:'game.example.test',href:'https://game.example.test/index.html?online=1&action=create&ticket=old',search:'?online=1&action=create&ticket=old',reload:()=>reloads++},
 history:{replaceState(){}},sessionStorage:{setItem(){},getItem(){return null;},removeItem(){}},
 document:{visibilityState:'visible',addEventListener:(t,fn)=>documents.set(t,fn)},
 WebSocket:Socket,Date:Clock,URL,URLSearchParams,AbortController,console,Promise,Math,
 setTimeout:(fn,ms)=>timeout(fn,ms),clearTimeout:clear,setInterval:(fn,ms)=>timeout(fn,ms,true),clearInterval:clear,
 fetch:async(url,options)=>{assert.equal(url,'/api/game-ticket');assert.equal(options.credentials,'same-origin');renewals++;return{ok:true,status:200,json:async()=>({ticket:'renewed'})};}};
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(path.join(__dirname,'../game/samidev-network.js'),'utf8'),ctx);
const net=ctx.window.SamiDevNetwork;
const flush=()=>new Promise(resolve=>setImmediate(resolve));
async function tick(ms){now+=ms;for(const [id,item]of [...timers])if(item.due<=now){if(item.repeat)item.due=now+item.ms;else timers.delete(id);item.fn();}await flush();}
(async()=>{
 const starting=net.connectFromLocation();await flush();await tick(1000);await flush();await starting;
 assert.equal(sockets.length,2);assert.equal(sockets[0].readyState,3,'failed handshake socket closed');
 assert.equal(renewals,1);assert(sockets[1].url.includes('ticket=renewed'));
 assert.equal(sockets.flatMap(s=>s.sent).filter(m=>m.type==='create_room').length,1,'initial retry never duplicates room creation');
 net.runtimeReady();
 await tick(6000);assert(sockets[1].sent.some(m=>m.type==='ping'&&m.authority===true));
 assert.equal(sockets[1].sent.filter(m=>m.type==='runtime_ready').length,2,'failed readiness can retry after native runtime finished loading');
 sockets[1].message({type:'pong'});
 net.sendMove({i:'lost-ack',n:0,m:{m:6,ps:.5}});
 await tick(10000);assert(sockets[1].sent.some(m=>m.type==='resync'),'missing move ACK triggers checkpoint');
 sockets[1].message({type:'resync_state',snapshot:{}});
 const before=sockets[1].sent.length;documents.get('visibilitychange')();
 assert(sockets[1].sent.slice(before).some(m=>m.type==='ping'&&m.authority));
 await tick(21000);assert.equal(net.state.connected,false,'silent OPEN socket is closed');
 await tick(2000);assert.equal(reloads,1,'silent connection reconnects using saved room credentials');
 console.log('PASS handshake retry + ticket renewal + one room creation + missing ACK recovery + foreground sync + silent socket reconnect');
})().catch(e=>{console.error(e);process.exitCode=1;});
