/* Original Plazr raster pocket VFX. Presentation only; never changes physics. */
(() => {
  'use strict';
  const ITEM='pool_pocket_water',DURATION=900;
  const frames={};
  const names=['splash_00','splash_01','splash_02','splash_03','splash_04','splash_05','splash_06','splash_07','droplet','ribbon','spray','glint','ripple_00','ripple_01','foam','mist'];
  names.forEach((name,i)=>{frames[name]={x:(i%4)*512+64,y:Math.floor(i/4)*512+64,w:384,h:384};});
  function create({canvas,getCosmetics,onInvalidate,onSound,onDispose}){
    const observed=new WeakSet(),bursts=[];
    let overlay=null,ctx=null,image=null,disposed=false,shotEffect=null,logic=null,lastSound=-Infinity;
    function preload(){
      if(image||disposed)return;
      image=new Image();image.decoding='async';
      image.onload=()=>{if(!disposed)onInvalidate();};
      image.onerror=()=>{bursts.length=0;};
      image.src='/images/effects/plazr-water.webp?v=original-water-v1';
    }
    function selected(g){const seat=g.currentShot?.seat??g.turn?.[0];return getCosmetics()?.[String(seat)]?.pool_pocket_effect===ITEM?ITEM:'';}
    function observe(g){
      if(!g||observed.has(g))return;
      observed.add(g);logic=g;shotEffect=selected(g);
      g.onPreShot?.receive(()=>{shotEffect=selected(g);if(shotEffect===ITEM)preload();});
      g.onBallSinkInPocket?.receive((_ball,x,y)=>{
        if(disposed||(shotEffect??selected(g))!==ITEM||!Number.isFinite(x)||!Number.isFinite(y))return;
        const now=performance.now();
        if(now-lastSound>=180){lastSound=now;onSound?.();}
        preload();if(bursts.length>=12)bursts.shift();bursts.push({x,y,start:now});onInvalidate();
      });
    }
    function surface(rect){
      if(!overlay){overlay=document.createElement('canvas');overlay.setAttribute('aria-hidden','true');overlay.id='plazr-pocket-vfx';overlay.style.cssText='position:fixed;pointer-events:none;z-index:8;';document.body.appendChild(overlay);ctx=overlay.getContext('2d');}
      const ratio=Math.min(2,window.devicePixelRatio||1),w=Math.max(1,Math.round(rect.width*ratio)),h=Math.max(1,Math.round(rect.height*ratio));
      if(overlay.width!==w||overlay.height!==h){overlay.width=w;overlay.height=h;}
      Object.assign(overlay.style,{left:rect.left+'px',top:rect.top+'px',width:rect.width+'px',height:rect.height+'px'});ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,rect.width,rect.height);
    }
    function sprite(name,x,y,size,alpha,rotation=0){const f=frames[name];ctx.save();ctx.translate(x,y);ctx.rotate(rotation);ctx.globalAlpha=Math.max(0,Math.min(1,alpha));ctx.drawImage(image,f.x,f.y,f.w,f.h,-size/2,-size/2,size,size);ctx.restore();}
    function frame(g,presentation,now=performance.now()){
      if(disposed)return false;observe(g);
      if(!bursts.length){if(overlay&&ctx)ctx.clearRect(0,0,overlay.width,overlay.height);return false;}
      const rect=canvas.getBoundingClientRect(),s=g?.sceneMgr;if(!s?.table||!s.layoutInfo||!rect.width)return false;
      surface(rect);
      for(let i=bursts.length-1;i>=0;i--){
        const b=bursts[i],t=(now-b.start)/DURATION;if(t>=1){bursts.splice(i,1);continue;}
        if(!image?.complete||!image.naturalWidth)continue;
        const world=s.table.toWorldCoordinates([b.x,b.y]);let p={x:world[0],y:world[1]};if(presentation?.enabled)p=presentation.forward(p);
        const unit=rect.width/canvas.width/s.layoutInfo.logScale,x=p.x*unit,y=p.y*unit;
        const size=Math.max(90,Math.min(230,180*s.table.scaleX*unit*(presentation?.enabled?presentation.geometry.scale:1)));
        const alpha=Math.min(1,t*10,(1-t)*5);
        sprite('ripple_00',x,y,size*(.6+t*.8),Math.sin(t*Math.PI)*.5);
        sprite('splash_0'+Math.min(7,Math.floor(t*8)),x,y-size*.06,size*(.85+Math.sin(t*Math.PI)*.2),alpha);
        for(let n=0;n<6;n++){const a=n*Math.PI/3+.35,r=size*t*.48;sprite('droplet',x+Math.cos(a)*r,y+Math.sin(a)*r,size*.09,Math.sin(t*Math.PI),a);}
        sprite('glint',x,y-size*.1,size*.2,Math.max(0,1-t*3));
      }
      if(bursts.length)onInvalidate();return bursts.length>0;
    }
    return{frame,dispose(){if(disposed)return;disposed=true;onDispose?.();bursts.length=0;if(image){image.onload=null;image.onerror=null;}overlay?.remove();overlay=null;ctx=null;logic=null;}};
  }
  window.PlazrPocketEffects={create};
})();
