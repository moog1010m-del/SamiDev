(() => {
  'use strict';
  let current=null,lastReport=null;
  const unavailable=(message='قناة المحادثة غير متصلة')=>Object.assign(new Error(message),{retryViaHttp:true});

  class CommunityChannel {
    constructor({cid,userId,onEvent}){
      Object.assign(this,{cid,userId,onEvent,socket:null,source:null,stopped:false,ready:false,attempt:0,lastPacket:0});
      this.pending=new Map();this.seen=new Set();this.samples=[];this.connect();
    }
    note(kind,details={}){this.samples.push({at:Date.now(),kind,...details});if(this.samples.length>60)this.samples.shift();}
    observe(rows,source){
      for(const row of rows){
        if(!row?.id||row.pending||this.seen.has(row.id))continue;
        this.seen.add(row.id);this.note('delivery',{source,id:row.id,serverAgeMs:Number.isFinite(this.clockOffset)?Math.round(Date.now()-Number(row.createdAt)-this.clockOffset):null});
      }
      while(this.seen.size>200)this.seen.delete(this.seen.values().next().value);
    }
    receive(event,source){
      if(this.stopped)return;
      if(event.type==='message'){
        this.observe([event.message],source);
        this.confirm(event.message);
      }else if(event.type==='snapshot'){this.observe(event.messages||[],source+'-snapshot');if(event.deliveryState)this.gateway=event.deliveryState;}
      else if(event.type==='ack')this.confirm(event.message);
      else if(event.type==='error'){
        const pending=this.pending.get(event.clientMessageId);
        if(pending){clearTimeout(pending.timer);this.pending.delete(event.clientMessageId);pending.reject(Object.assign(new Error(event.message||'تعذر إرسال الرسالة'),{code:event.error}));}
        this.note('server_error',{code:event.error});return;
      }else if(event.type==='pong'){
        const now=Date.now(),roundTripMs=this.pingAt?now-this.pingAt:null;
        if(roundTripMs!==null&&Number.isFinite(event.serverTime))this.clockOffset=event.serverTime-(this.pingAt+now)/2;
        this.note('pong',{roundTripMs});return;
      }
      try{this.onEvent(event);}catch(error){this.note('render_error',{message:String(error.message).slice(0,160)});console.error('Community chat render failed',error);}
    }
    confirm(message){
      if(message?.userId!==this.userId)return;
      const pending=this.pending.get(message.clientMessageId);if(!pending)return;
      clearTimeout(pending.timer);this.pending.delete(message.clientMessageId);
      this.note('ack',{roundTripMs:Date.now()-pending.started});pending.resolve(message);
    }
    fallback(){
      if(this.stopped||this.source||!window.EventSource)return;
      this.source=new EventSource('/api/communities/'+encodeURIComponent(this.cid)+'/events');
      this.note('sse_fallback');
      this.source.onmessage=event=>{try{this.receive(JSON.parse(event.data),'sse');}catch(_){this.note('bad_event');}};
      this.source.onerror=()=>this.note('sse_error');
    }
    connect(){
      if(this.stopped)return;
      if(!window.WebSocket){this.fallback();return;}
      const url=new URL('/ws/community/'+encodeURIComponent(this.cid),location.href);url.protocol=location.protocol==='https:'?'wss:':'ws:';
      let socket;
      try{socket=new WebSocket(url.href);}catch(_){this.fallback();this.retry();return;}
      this.socket=socket;this.note('connecting');
      const startup=setTimeout(()=>{if(!this.ready){this.note('connect_timeout');socket.close();this.fallback();}},4000);
      socket.onmessage=event=>{
        if(this.socket!==socket||this.stopped)return;
        let data;try{data=JSON.parse(event.data);}catch(_){this.note('bad_event');return;}
        this.lastPacket=Date.now();
        if(!this.ready){
          if(data.type!=='snapshot')return;
          this.ready=true;this.attempt=0;clearTimeout(startup);this.source?.close();this.source=null;this.note('websocket_ready');
          this.watch=setInterval(()=>{
            if(socket.readyState!==1)return;
            if(Date.now()-this.lastPacket>20000){this.note('stalled');socket.close();return;}
            this.pingAt=Date.now();socket.send(JSON.stringify({type:'ping'}));
          },5000);
          this.pingAt=Date.now();socket.send(JSON.stringify({type:'ping'}));
        }
        this.receive(data,'websocket');
      };
      socket.onerror=()=>this.note('websocket_error');
      socket.onclose=()=>{
        clearTimeout(startup);clearInterval(this.watch);
        if(this.socket!==socket)return;
        this.socket=null;this.ready=false;
        for(const pending of this.pending.values()){clearTimeout(pending.timer);pending.reject(unavailable());}
        this.pending.clear();
        if(!this.stopped){this.note('disconnected');this.fallback();this.retry();}
      };
    }
    retry(){
      if(this.stopped)return;clearTimeout(this.retryTimer);
      this.retryTimer=setTimeout(()=>this.connect(),Math.min(10000,500*2**Math.min(this.attempt++,5))+Math.random()*250);
    }
    send(message){
      if(!this.ready||this.socket?.readyState!==1)return Promise.reject(unavailable());
      const nonce=message.clientMessageId;
      if(this.pending.has(nonce))return this.pending.get(nonce).promise;
      const pending={started:Date.now()};
      pending.promise=new Promise((resolve,reject)=>Object.assign(pending,{resolve,reject}));
      pending.timer=setTimeout(()=>{
        this.pending.delete(nonce);this.note('ack_timeout');pending.reject(unavailable('تأخر تأكيد الرسالة'));this.socket?.close();
      },6000);
      this.pending.set(nonce,pending);
      try{this.socket.send(JSON.stringify({type:'chat_send',text:message.text,clientMessageId:nonce,...(message.stickerId?{stickerId:message.stickerId}:{})}));}
      catch(_){clearTimeout(pending.timer);this.pending.delete(nonce);pending.reject(unavailable());}
      return pending.promise;
    }
    report(){return {community:this.cid,transport:this.ready?'websocket':this.source?'sse-fallback':'disconnected',gateway:this.gateway||null,lastPacketAgeMs:this.lastPacket?Date.now()-this.lastPacket:null,pending:this.pending.size,samples:[...this.samples]};}
    close(){
      this.stopped=true;this.ready=false;clearTimeout(this.retryTimer);clearInterval(this.watch);this.source?.close();this.socket?.close();
      for(const pending of this.pending.values()){clearTimeout(pending.timer);pending.reject(new Error('تم إغلاق المحادثة'));}this.pending.clear();
    }
  }
  window.SamiDevCommunityLive={
    open(options){this.close();current=new CommunityChannel(options);},
    close(){if(current){lastReport=current.report();current.close();current=null;}},
    send(message){return current?.cid===message.communityId?current.send(message):Promise.reject(unavailable());},
    history(rows){current?.observe(rows,'history');},
    report(){return current?.report()||lastReport||{transport:'disconnected'};}
  };
})();
