'use strict';
const assert = require('node:assert/strict');
const path = require('node:path');
const {GameRuntimeFactory} = require('../gamehost/runtime');
const factory = new GameRuntimeFactory(path.join(__dirname,'../game'));
let checks = 0;
const timings = [];
function check(value, message) { assert.ok(value, message); checks++; }
function state(g) {
  return JSON.stringify({score:g.totalScore, queen:g.queenState, turn:g.turn,
    sequence:g._sequence, pos:g.getPositionsToValidate(), gameOver:g.gameOver,
    finishOrder:g.finishOrder, animations:g.noAnimations});
}
for (const players of [0,1]) for (const gamemode of [0,1,2,3,4]) {
  const settings = {players,gamemode,live:1,break:0};
  const room = factory.createRoom(`SEC-${players}-${gamemode}`,settings,players?4:2,()=>{});
  const g = room.logic;
  const move = (seat,m) => factory.processMove(room,seat,{i:`s-${seat}-${g._sequence[seat]}`,n:g._sequence[seat],m});
  try {
    check(move(0,{m:0}).accepted,'start');
    const before = state(g);
    check(!move(1,{m:5,i:[0,50],ps:.1}).accepted,'wrong turn rejected');
    check(before===state(g),'wrong turn cannot even move striker');
    const shot = {i:'first-shot',n:g._sequence[0],m:{m:5,i:[0,50],ps:.5}};
    const t = performance.now();
    const result = factory.processMove(room,0,structuredClone(shot));
    timings.push(performance.now()-t);
    check(result.accepted,'server shot');
    check(!!result.revealBySeat['0'],'server positions revealed with shot');
    check(g.turn[0]===1,'turn advances without any client result');
    check(g.lastValidAnim===g.noAnimations && Object.keys(g.animValidation).length===0,'physics completed');
    check(factory.describeRoom(room,true).snapshotSafe,'immediate authoritative checkpoint');
    const after = state(g);
    check(!factory.processMove(room,0,{__info:{a:-1,idx:1},i:'mixed',n:0,m:{m:4}}).accepted,'mixed report and move rejected');
    check(!factory.processMove(room,0,structuredClone(shot)).accepted,'shot replay rejected');
    check(after===state(g),'replay has no effect');
    for (const seat of [0,1]) for (const idx of [0,g.noAnimations,g.noAnimations+1000]) {
      const forged = {__info:{a:-1,idx,
        logic:{scores:[999999,0],queenState:3,fouls:[],penalties:[],resetQueen:false,reason:-1},
        gameOver:true,pos:[[1e20,-1e20]],rot:[999],extra:{winner:seat}}};
      check(factory.processMove(room,seat,forged).accepted,'legacy report acknowledged');
      check(forged.__info===1,'forged payload stripped from broadcast/history');
      check(after===state(g),'forged result and positions have no effect');
    }
    check(!move(1,{m:5,i:[0,-50],ps:.5,__psValidationMove:true}).accepted,'internal bypass rejected');
    check(move(1,{m:5,i:[0,-50],ps:.5}).accepted,'next player can shoot');
    const snapshot = factory.describeRoom(room,true).snapshot;
    const restored = factory.createRoom('RESTORED',settings,players?4:2,()=>{});
    try { factory.deserialize(restored,snapshot);check(state(restored.logic)===state(g),'shot checkpoint restores result'); }
    finally { factory.destroyRoom(restored); }
  } finally { factory.destroyRoom(room); }
}
// A controlled server fixture places one disc in a pocket. Real collision
// detection, not a client report, must award its points and retain the turn.
{
  const room = factory.createRoom('POCKET',{players:0,gamemode:2,live:1,break:0},2,()=>{}),g=room.logic;
  try {
    factory.processMove(room,0,{i:'start',n:0,m:{m:0}});
    const disc=g.table.tCarrom.find(b=>b.rank===2);
    disc.position[0]=120;disc.position[1]=110;disc.aabbNeedsUpdate=true;disc.wakeUp();
    check(factory.processMove(room,0,{i:'pocket',n:1,m:{m:5,i:[0,50],ps:.5}}).accepted,'scoring shot');
    check(disc.isPocketed() && g.totalScore[0]===20,'server physics awards 20 points');
    check(g.turn[0]===0 && !g.gameOver,'legitimate scoring retains turn');
  } finally {factory.destroyRoom(room);}
}
console.log(JSON.stringify({ok:true,checks,carromConfigurations:10,
  localShotMs:{max:Math.max(...timings),average:timings.reduce((a,b)=>a+b,0)/timings.length},
  note:'Local fixed-shot timings are not a production load test.'},null,2));
