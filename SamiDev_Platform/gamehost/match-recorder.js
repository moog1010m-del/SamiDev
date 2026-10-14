'use strict';
// Opt-in capture of the authoritative pool contract. Never record request headers,
// account identities, cookies, room reconnect tokens, chat, or arbitrary __info.
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {performance}=require('node:perf_hooks');
const FORMAT='samidev.pool-recording';
const ID=/^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const copy=value=>JSON.parse(JSON.stringify(value));
const failure=(code,statusCode=400)=>Object.assign(new Error(code),{code,statusCode});
function publicState(desc){
  const state={turn:copy(desc.turn),sequence:copy(desc.sequence),gameOver:!!desc.gameOver};
  if(desc.pool)state.pool=copy(desc.pool);
  return state;
}
function input(packet){
  const m=packet?.m;
  if(!m||typeof m!=='object'||Array.isArray(m))return null;
  if(m.__ready===1&&Object.keys(m).length===1)return {__ready:1};
  const fields={0:['a'],1:['a','st','an','sp'],2:['a','ps'],3:['a','an'],4:['a','st'],8:['a','al']}[m.a];
  if(!fields||Object.keys(m).some(k=>!fields.includes(k)))return null;
  return copy(m);
}
class MatchRecorder {
  constructor(directory,{maxBytes=64*1024*1024,maxPending=1024*1024,maxEvents=250000,maxMs=6*3600000,maxActive=32}={}){
    this.directory=directory?path.resolve(directory):null;this.limits={maxBytes,maxPending,maxEvents,maxMs,maxActive};
    this.byRoom=new Map();this.byId=new Map();
  }
  status(record){return {recordingId:record.id,active:record.active,complete:record.complete,events:record.events,bytes:record.bytes,error:record.error||null};}
  start(room){
    if(!this.directory)throw failure('RECORDING_DISABLED',503);
    if(room.gameId!=='pool'||room.capacity!==2)throw failure('RECORDING_REQUIRES_POOL_1V1');
    const prior=this.byRoom.get(room.roomId);
    if(prior?.active)return this.status(prior);
    if([...this.byRoom.values()].filter(r=>r.active).length>=this.limits.maxActive)throw failure('RECORDING_BUSY',503);
    const desc=room.factory.describeRoom(room,true);
    if(!desc.snapshot)throw failure('RECORDING_CHECKPOINT_BUSY',409);
    if(desc.gameOver)throw failure('RECORDING_MATCH_FINISHED',409);
    fs.mkdirSync(this.directory,{recursive:true,mode:0o700});
    const id=crypto.randomUUID(),file=path.join(this.directory,id+'.jsonl');
    const stream=fs.createWriteStream(file,{flags:'wx',mode:0o600});
    const record={id,file,stream,active:true,complete:false,events:0,bytes:0,started:performance.now(),roomId:room.roomId};
    record.finished=new Promise(resolve=>{
      stream.once('finish',resolve);
      stream.once('error',error=>{record.error=error.code||'WRITE_ERROR';record.active=false;record.complete=false;resolve();});
      stream.once('close',()=>{if(!stream.writableFinished){record.error||='STREAM_CLOSED';record.active=false;record.complete=false;}resolve();});
    });
    this.byRoom.set(room.roomId,record);this.byId.set(id,record);
    // Keep metadata bounded; files remain on disk for the operator to export.
    if(this.byId.size>256){const old=[...this.byId.values()].find(r=>!r.active);if(old){this.byId.delete(old.id);if(this.byRoom.get(old.roomId)===old)this.byRoom.delete(old.roomId);}}
    this.write(record,{type:'header',format:FORMAT,version:1,recordingId:id,createdAt:new Date().toISOString(),engineSha256:room.factory.sha256,
      settings:copy(room.settings),capacity:2,initialSnapshot:copy(desc.snapshot),initialState:publicState(desc),
      waitingForClients:!!room.waitingForClients,scope:'accepted pool inputs and native alarms; no browser rendering or account journey'});
    return this.status(record);
  }
  write(record,data){
    const raw=JSON.stringify(data)+'\n',bytes=Buffer.byteLength(raw);
    record.bytes+=bytes;record.stream.write(raw);
  }
  append(room,type,data={},started){
    const record=this.byRoom.get(room.roomId);if(!record?.active)return;
    try{
      const atMs=Math.max(0,Number(((started??performance.now())-record.started).toFixed(3)));
      const event={type,ordinal:record.events+1,atMs,...data};
      const bytes=Buffer.byteLength(JSON.stringify(event))+1;
      if(record.events>=this.limits.maxEvents||atMs>this.limits.maxMs||record.bytes+bytes>this.limits.maxBytes||record.stream.writableLength+bytes>this.limits.maxPending){
        this.finish(room.roomId,'recording_limit',false);return;
      }
      record.events++;this.write(record,event);
    }catch(error){record.error=error.code||'CAPTURE_ERROR';this.finish(room.roomId,'capture_error',false);}
  }
  command(room,seat,packet,desc,{accepted,code,processingMs,started}){
    if(!this.byRoom.get(room.roomId)?.active)return;
    if(packet?.__info!==undefined)return; // Validation traffic is outside replay scope.
    const move=input(packet);
    if(!accepted){this.append(room,'rejected',{seat,action:Number.isInteger(packet?.m?.a)?packet.m.a:null,code:code||'REJECTED'},started);return;}
    if(!move){this.finish(room.roomId,'unsupported_input',false);return;}
    this.append(room,'command',{seat,input:move,sequenceBefore:packet.n,state:publicState(desc),processingMs:Number(processingMs.toFixed(3))},started);
    if(desc.gameOver)this.finish(room.roomId,'game_over',true,publicState(desc));
  }
  event(room,event){
    if(!this.byRoom.get(room.roomId)?.active)return;
    if(event.type==='authority_alarm')this.append(room,'alarm',{alarmId:event.alarmId,state:publicState(event)});
    else this.append(room,'checkpoint',{state:publicState(event)});
    if(event.gameOver)this.finish(room.roomId,'game_over',true,publicState(event));
  }
  begin(room){if(this.byRoom.get(room.roomId)?.active)this.append(room,'begin',{state:publicState(room.factory.describeRoom(room,false))});}
  finish(roomId,reason='operator_stop',complete=true,state){
    const record=this.byRoom.get(roomId);if(!record)return null;
    if(record.active){
      record.active=false;record.complete=complete&&!record.error;
      try{this.write(record,{type:'end',atMs:Number((performance.now()-record.started).toFixed(3)),events:record.events,complete:record.complete,reason,...(state?{state}: {})});record.stream.end();}
      catch(error){record.error=error.code||'WRITE_ERROR';record.complete=false;record.stream.destroy();}
    }
    return record;
  }
  async stop(roomId,room){const r=this.finish(roomId,'operator_stop',true,room?publicState(room.factory.describeRoom(room,false)):undefined);if(!r)throw failure('RECORDING_NOT_FOUND',404);await r.finished;return this.status(r);}
  async download(id){
    if(!this.directory)throw failure('RECORDING_DISABLED',503);
    if(!ID.test(id))throw failure('BAD_RECORDING_ID');
    const known=this.byId.get(id);if(known?.active)throw failure('RECORDING_STILL_ACTIVE',409);if(known)await known.finished;
    const file=path.join(this.directory,id+'.jsonl');
    try{const stat=await fs.promises.stat(file);if(!stat.isFile())throw failure('RECORDING_NOT_FOUND',404);return {file,bytes:stat.size};}
    catch(error){if(error.code==='ENOENT')throw failure('RECORDING_NOT_FOUND',404);throw error;}
  }
}
module.exports={MatchRecorder,publicState,FORMAT};
