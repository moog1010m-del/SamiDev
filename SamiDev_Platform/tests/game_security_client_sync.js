'use strict';
const assert=require('node:assert/strict');
const path=require('node:path');
const {GameRuntimeFactory}=require('../gamehost/runtime');
const factory=new GameRuntimeFactory(path.join(__dirname,'../game'));

(async()=>{
  const results=[];
  for(const gamemode of [0,2]) {
    const settings={players:0,gamemode,live:1,break:0};
    const room=factory.createRoom('CLIENT-SYNC-'+gamemode,settings,2,()=>{});
    const clients=[];
    try {
      factory.processMove(room,0,{i:'start',n:0,m:{m:0}});
      for(const seat of [0,1]) {
        const host=factory._baseHostApi(),timers=new Map();let next=0;
        host.ownerSeat=()=>seat;
        host.setTimer=(fn,ms)=>{
          const id=++next;
          timers.set(id,setTimeout(()=>{timers.delete(id);factory.context.SamiDev=host;fn();},ms));
          return id;
        };
        host.clearTimer=id=>{clearTimeout(timers.get(id));timers.delete(id);};
        host.sendMove=()=>{};
        factory.context.SamiDev=host;
        const logic=new factory.GameLogicCtor();
        logic.initialize(settings,seat);logic.onSetAlarm=()=>{};
        for(let s=0;s<2;s++)logic.enter(s);
        logic._initialSync=true;
        const snapshot=factory.describeRoom(room,true).snapshot;
        factory.context.SamiDev=host;
        logic.deserialize(structuredClone(snapshot),seat);
        // Supply a deterministic frame clock; keep the actual client physics,
        // server reveal handling and delayed completion callbacks intact.
        logic.animator.getAnimationDeltaTime=()=>logic.getFixedTimeStep();
        clients.push({host,logic,timers});
      }
      for(const seat of [0,1]) {
        const packet={i:'shot-'+seat,n:room.logic._sequence[seat],m:{m:5,i:[0,seat===0?50:-50],ps:.5}};
        const result=factory.processMove(room,seat,structuredClone(packet));
        assert.ok(result.accepted);
        for(const client of clients) {
          factory.context.SamiDev=client.host;
          assert.ok(client.logic.move(seat,structuredClone(packet),structuredClone(result.revealBySeat[String(client.logic.localSeat)])));
          let frames=0;
          while(client.logic.animator.animatingWorld && frames++<12000)client.logic.animator.executeAnimation();
          assert.ok(frames<12000);
        }
        await new Promise(resolve=>setTimeout(resolve,650));
        for(const client of clients) for(const key of ['turn','totalScore','_sequence']) {
          assert.deepEqual(Array.from(client.logic[key]),Array.from(room.logic[key]),key);
        }
      }
      results.push({gamemode,twoClientShotsReplicated:true});
    } finally {
      for(const client of clients)for(const timer of client.timers.values())clearTimeout(timer);
      factory.destroyRoom(room);
    }
  }
  console.log(JSON.stringify({ok:true,results},null,2));
})().catch(error=>{console.error(error);process.exitCode=1;});
