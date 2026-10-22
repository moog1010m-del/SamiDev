'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const window={};vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../game/pool-aim-presentation.js'),'utf8'),{window});
const {GameRuntimeFactory}=require('../gamehost/runtime');
const factory=new GameRuntimeFactory(path.join(__dirname,'../game/games/pool'),{gameId:'pool'}),results=[];
for(const [name,target,expected] of [['corner opening',[49,47],'pocket'],['top jaw',[126,70],'rail'],['left jaw',[70,126],'rail']]){
 const room=factory.createRoom('AIM_GEOMETRY',{gameType:7,break:0,live:1,trickShots:0},2,()=>{}),g=room.logic;
 const api=window.PlazrPoolAimPresentation.create();
 try{
  const move=m=>factory.processMove(room,0,{i:name,n:g._sequence[0],m});assert(move({__ready:1}).accepted);g.ballInHand=0;
  const ball=g.table.cueBall;ball.position[0]=200;ball.position[1]=200;ball.aabbNeedsUpdate=true;ball.wakeUp();
  const angle=Math.atan2(target[1]-200,target[0]-200),original=g.table.getPointMinDistToRail,old=original.call(g.table,ball.position,angle);
  const before=JSON.stringify(g.world.bodies.map(b=>({p:b.position,v:b.velocity,s:b.shapes.map(s=>s.collisionMask)})));
  api.frame({logic:g});const distance=g.table.getPointMinDistToRail(ball.position,angle),predicted=[200+Math.cos(angle)*distance,200+Math.sin(angle)*distance];
  assert.equal(JSON.stringify(g.world.bodies.map(b=>({p:b.position,v:b.velocity,s:b.shapes.map(s=>s.collisionMask)}))),before,'guide does not mutate bodies');
  let first=null;
  g.addCollisionListener(0,{pairMask:5,callback:event=>{if(!first&&event.bodies.includes(ball))first={kind:'rail',position:ball.position.slice()};}});
  ball.onSunk.receive(()=>{if(!first)first={kind:'pocket',position:ball.position.slice()};});
  assert(move({a:1,st:.2,an:angle,sp:[0,0]}).accepted);assert(first,name+' must reach an event');
  assert.equal(first.kind,expected,name);assert(Math.hypot(predicted[0]-first.position[0],predicted[1]-first.position[1])<6,name+' guide follows actual contact/entry');
  if(expected==='pocket')assert(distance>old+10,'opening is no longer shown as a rectangular rail');
  results.push({name,expected,oldDistance:old,newDistance:distance,predicted,actual:first});
  api.dispose();assert.equal(g.table.getPointMinDistToRail,original,'original getter restored');
 }finally{api.dispose();factory.destroyRoom(room)}
}
console.log(JSON.stringify({ok:true,bodyMutation:false,actualPhysicsCases:results},null,2));
