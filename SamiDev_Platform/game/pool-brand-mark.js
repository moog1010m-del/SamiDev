/* Non-mirrored raster inlay. Native quarter atlas, bodies and input stay untouched. */
(() => {
 'use strict';
 const mark=Object.freeze({x:193,y:16,width:480,height:44});
 function create({canvas,getLargeTable=()=>false,onInvalidate=()=>{}}){
  let overlay=null,ctx=null,image=null,lastKey='',disposed=false;
  function hide(){if(overlay)overlay.hidden=true;lastKey='';}
  function preload(){
   if(image||disposed)return;
   image=new Image();image.decoding='async';image.onload=()=>{lastKey='';onInvalidate()};image.onerror=()=>hide();
   image.src='/images/themes/plazr-engraving.webp?v=plazr-table-v9';
  }
  function frame(logic){
   const s=logic?.sceneMgr;
   if(disposed||getLargeTable()||!s?.table?.toWorldCoordinates||!s.layoutInfo||s.spinPanel?.visible||s.shopWidget?.visible||s.settingsWidget?.visible||s.gameOverPopup?.visible){hide();return;}
   preload();if(!image.complete||!image.naturalWidth)return;
   const rect=canvas.getBoundingClientRect();if(!rect.width||!canvas.width)return;
   const shadow=s.table.shadowDims||[16,15],p=s.table.toWorldCoordinates([mark.x-shadow[0],mark.y-shadow[1]]),q=s.table.toWorldCoordinates([mark.x+mark.width-shadow[0],mark.y+mark.height-shadow[1]]);
   const unit=rect.width/canvas.width/s.layoutInfo.logScale,ratio=Math.min(2,window.devicePixelRatio||1);
   const key=JSON.stringify([rect.left,rect.top,rect.width,rect.height,...p,...q,unit,ratio]);
   if(key===lastKey&&overlay&&!overlay.hidden)return;
   lastKey=key;
   if(!overlay){overlay=document.createElement('canvas');overlay.id='plazr-pool-brand';overlay.setAttribute('aria-hidden','true');overlay.style.cssText='position:fixed;pointer-events:none;z-index:7;';document.body.append(overlay);ctx=overlay.getContext('2d');}
   const width=(q[0]-p[0])*unit,height=(q[1]-p[1])*unit;
   overlay.hidden=false;overlay.width=Math.max(1,Math.round(width*ratio));overlay.height=Math.max(1,Math.round(height*ratio));
   Object.assign(overlay.style,{left:rect.left+p[0]*unit+'px',top:rect.top+p[1]*unit+'px',width:width+'px',height:height+'px'});ctx.setTransform(ratio,0,0,ratio,0,0);ctx.clearRect(0,0,width,height);ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';
   ctx.drawImage(image,0,0,width,height);
  }
  return {frame,dispose(){if(disposed)return;disposed=true;if(image){image.onload=null;image.onerror=null;}overlay?.remove();overlay=ctx=null;}};
 }
 window.PlazrPoolBrandMark={create,mark};
})();
