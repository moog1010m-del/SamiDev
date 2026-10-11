'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.join(__dirname,'..','game');
const game=process.argv[2]||'tablesoccer';
let redirect,assignment,closed=false;const saved=new Map();
class Socket {
 static OPEN=1;
 constructor(){this.readyState=1;this.listeners={};queueMicrotask(()=>this.emit('open',{}));}
 addEventListener(name,fn){(this.listeners[name]??=[]).push(fn);}
 emit(name,data){for(const f of this.listeners[name]||[])f(data);}
 send(raw){assignment=JSON.parse(raw);queueMicrotask(()=>this.emit('message',{data:JSON.stringify({type:'joined',roomId:'ABCDEF',token:'seat-token-test',settings:{gameId:game},seat:1,capacity:2})}));}
 close(){closed=true;}
}
const location={protocol:'http:',host:'local.test',href:'http://local.test/index.html?online=1&action=join&room=ABCDEF',pathname:'/index.html',search:'?online=1&action=join&room=ABCDEF',replace:url=>{redirect=url;}};
const c={location,URL,URLSearchParams,WebSocket:Socket,sessionStorage:{getItem:k=>saved.get(k),setItem:(k,v)=>saved.set(k,v)},history:{replaceState(){}},console,setTimeout,clearTimeout};c.window=c;vm.createContext(c);
for(const name of ['samidev-games.js','samidev-network.js'])vm.runInContext(fs.readFileSync(path.join(root,name),'utf8'),c);
c.SamiDevNetwork.connectFromLocation(()=>{}).catch(e=>{throw e;});
setTimeout(()=>{
 assert.equal(assignment.type,'join_room');
 assert(redirect.startsWith(`/games/${game}/index.html?`));
 const q=new URLSearchParams(redirect.split('?')[1]);assert.equal(q.get('room'),'ABCDEF');assert.equal(q.get('action'),'join');
 const data=JSON.parse(saved.get('samidev_reconnect'));assert.equal(data.token,'seat-token-test');assert.equal(data.gameId,game);
 assert.equal(q.has('token'),false);assert(closed);
 console.log(JSON.stringify({ok:true,correctGameRedirect:true,reconnectTokenPreserved:true,tokenAbsentFromUrl:true}));
},10);
