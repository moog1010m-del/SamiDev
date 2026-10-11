'use strict';
const {validatePoolMove} = require('./pool');
const object = x => x !== null && typeof x === 'object' && !Array.isArray(x);
const finite = x => typeof x === 'number' && Number.isFinite(x);
const vector = x => Array.isArray(x) && x.length === 2 && x.every(finite);
function safeData(value, depth=0) {
  if (depth > 12) return false;
  if (typeof value === 'number') return Number.isFinite(value);
  if (Array.isArray(value)) return value.length <= 512 && value.every(x=>safeData(x,depth+1));
  if (object(value)) return Object.entries(value).every(([k,v]) => !['__proto__','prototype','constructor'].includes(k) && (!k.startsWith('__') || k === '__ready') && safeData(v,depth+1));
  return value === null || ['boolean','string','undefined'].includes(typeof value);
}
function tableMove(g, seat, move) {
  if (!Number.isInteger(move.a) || move.a < 0 || move.a > 8) return false;
  const actions=g.GAME_ACTIONS;
  if (move.a===actions.SHOOT && !g.gsMgr.isTacticalMode()) return false;
  if ([actions.SHOOT_ST,actions.CANCEL_SHOOT_ST].includes(move.a) && g.gsMgr.isTacticalMode()) return false;
  if ([actions.SHOOT,actions.SHOOT_ST].includes(move.a)) {
    // Position reports are not movement commands. Only server physics places bodies.
    if (move.ci!==undefined || move.up!==undefined) return false;
    if (!Number.isInteger(move.id) || !vector(move.impulse) || !g._isValidImpulse(move.impulse)) return false;
    const body=g.stadium.players.find(b=>b.id===move.id);
    if (!body || g.stadium.getPlayerTeam(body)!==g.getAssignedTeam(seat)+1 || !g.isTurn(seat)) return false;
    if (g.is2v2AllPlayMode() && body.id%2!==seat%2 && !g.isResigned(g.getTeamMate(seat))) return false;
  }
  if (move.a===actions.CANCEL_SHOOT_ST && (!Number.isInteger(move.id) || !g.isTurn(seat))) return false;
  if (move.a===actions.MISS_TURN && !g.isTurn(seat)) return false;
  if (move.a===actions.SELECT_TEAM && !/^(Red|Blue)\.c\.h$/.test(move.team || '')) return false;
  if (move.a===actions.SELECT_FORMATIONS && (!Array.isArray(move.formations) || move.formations.length!==2 || !move.formations.every(x=>typeof x==='string'&&x.length<64))) return false;
  if (move.a===actions.SELECT_THEME && move.t!=='Default') return false;
  if (move.a===actions.SHOOT_ST && g.is2v2AllPlayMode() && (move.idx!==undefined && (!Number.isInteger(move.idx) || !g.stadium.players[move.idx] || g.stadium.players[move.idx].id!==move.id) || move.dimp!==undefined && !vector(move.dimp))) return false;
  if (move.a===actions.PLAYER_DRAGGED && (!Number.isInteger(move.index) || move.index<0 || move.index>=g.stadium.players.length || !g.isTurn(seat) || g.stadium.getPlayerTeam(g.stadium.players[move.index])!==g.getAssignedTeam(seat)+1 || (move.impulse!==undefined&&!vector(move.impulse)))) return false;
  return true;
}
function validatePacket(gameId,g,seat,packet) {
  if (!object(packet) || Object.keys(packet).some(k=>!['i','n','m','__info'].includes(k))) return false;
  if (gameId==='crazy8' && (!Number.isInteger(seat) || seat<0 || seat>=g.seats || '__info' in packet)) return false;
  if (gameId==='pool' && '__info' in packet) return false;
  if ('__info' in packet) {
    if (Object.keys(packet).length !== 1) return false;
    const info=packet.__info;
    if (!object(info)||!safeData(info)) return false;
    if (gameId==='tablesoccer' && [g.GAME_ACTIONS.SHOOT_ST,g.GAME_ACTIONS.CANCEL_SHOOT_ST].includes(info.a)) return tableMove(g,seat,info);
    return info.a===-1 && Number.isInteger(info.idx) && info.idx>=0;
  }
  if (!Number.isSafeInteger(packet.n)||packet.n<0||typeof packet.i!=='string'||packet.i.length<1||packet.i.length>160||!object(packet.m)||!safeData(packet.m)) return false;
  const m=packet.m;
  if (gameId==='pool') return validatePoolMove(g,seat,m);
  if (m.__ready===1) return Object.keys(m).length===1;
  if (m.m===15000) return true; // Native reaction plugin validates its own reaction payload.
  if (gameId==='crazy8') {
    // Never forward debug, internal, or permissive legacy move variants to the
    // supplied bundle. Card ownership and game rules are still checked by it.
    if (g.gameOver || !g.started || g.isResigned(seat)) return false;
    const keys=Object.keys(m);
    if (m.q===1) return keys.length===1;
    if (!g.isTurn(seat)) return false;
    if (m.d===1) return keys.length===1 && g.stock.length>0;
    if (!keys.every(k=>k==='c'||k==='o') || !Number.isInteger(m.c) || m.c<0 || m.c>75) return false;
    if (m.o!==undefined && (!Number.isInteger(m.o)||m.o<0||m.o>3)) return false;
    return g.hands[seat].includes(m.c) && g.canPlayCard(seat,m.c) && g.isValidMove(seat,m);
  }
  if (gameId==='tablesoccer') return tableMove(g,seat,m);
  if (m.type==='equipment_move') return true;
  if (![0,3,4,5,6,7].includes(m.m)) return false;
  if ([3,5,6,7].includes(m.m)&&!g.isTurn(seat)) return false;
  if (m.ps!==undefined && (!finite(m.ps)||m.ps<0||m.ps>1)) return false;
  if (m.m===5 && (!vector(m.i)||!g.constructor.isValidImpulse(m.i))) return false;
  if (m.m===6 && m.ps===undefined) return false;
  return true;
}
module.exports={validatePacket};
