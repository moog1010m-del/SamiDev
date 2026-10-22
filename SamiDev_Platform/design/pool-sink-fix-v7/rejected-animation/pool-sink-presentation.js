/* Pocket fall presentation. Bodies, collisions, scoring and network moves stay native. */
(() => {
  'use strict';
  const DURATION=260;
  function create({onInvalidate=()=>{},getTheme=()=>'',now=()=>performance.now()}={}){
    const records=new Map();
    let scene=null,disposed=false;
    function pocketGeometry(pocket,table){
      const emerald=getTheme(scene?.logic)==='pool_emerald';
      const shadow=table.shadowDims||[16,15],w=table.width,h=table.height;
      const middle=Math.abs(pocket.position[1]-(h-shadow[1]*2)/2)<100;
      const left=pocket.position[0]<(w-shadow[0]*2)/2,top=pocket.position[1]<(h-shadow[1]*2)/2;
      const cx=middle?(emerald?60:58.5):(emerald?83:80),cy=emerald?84:81;
      return {x:(left?cx:w-1-cx)-shadow[0],y:(middle?(h-1)/2:top?cy:h-1-cy)-shadow[1],radius:middle?(emerald?31:26):(emerald?40:26),key:(emerald?'emerald':'basic')+'-'+pocket.id};
    }
    function start(record){
      const body=record.body,pocket=body.getSinkingPocket?.();
      if(!body.isSinking?.()||!pocket)return;
      const geometry=pocketGeometry(pocket,scene.table);
      record.fall={entry:[body.position[0],body.position[1]],geometry,startedAt:null};
      onInvalidate();
    }
    function watch(view){
      if(records.has(view)||!view?.body||typeof view._render!=='function')return;
      const body=view.body,original=view._render,own=Object.getOwnPropertyDescriptor(view,'_render');
      const facade=Object.create(view),renderBody=Object.create(body);
      for(const key of ['x','y','width','height','hiliteX','hiliteY','hiliteSize','body'])Object.defineProperty(facade,key,{value:0,writable:true,configurable:true});
      const renderPocket={id:'',position:[0,0],getRadius(){return this.radius;},radius:26};
      Object.defineProperty(renderBody,'getSinkingPocket',{value:()=>renderPocket});
      facade.body=renderBody;
      const record={view,body,original,own,fall:null,onSunk:null,wrapped:null};
      record.onSunk=()=>start(record);
      record.wrapped=function(ctx){
        if(disposed||!body.isSinking?.())return original.apply(this,arguments);
        if(!record.fall)start(record);
        const fall=record.fall;if(!fall)return original.apply(this,arguments);
        const time=now();if(fall.startedAt===null)fall.startedAt=time;
        const t=Math.max(0,Math.min(1,(time-fall.startedAt)/DURATION));
        if(t>=1)return;
        const travel=1-(1-t)*(1-t),size=view.getDiameter()*(1-t*t),radius=view.getRadius();
        const x=fall.entry[0]+(fall.geometry.x-fall.entry[0])*travel;
        const y=fall.entry[1]+(fall.geometry.y-fall.entry[1])*travel;
        // Use a render-only receiver: never write visual positions back to the view/body.
        facade.x=x+radius-size/2;facade.y=y+radius-size/2;
        facade.width=size;facade.height=size;
        facade.hiliteX=facade.x;facade.hiliteY=facade.y;facade.hiliteSize=0;
        renderPocket.id='plazr-fall-v7-'+fall.geometry.key;
        renderPocket.position[0]=fall.geometry.x;renderPocket.position[1]=fall.geometry.y;
        renderPocket.radius=fall.geometry.radius;
        onInvalidate();
        return original.call(facade,ctx);
      };
      view._render=record.wrapped;
      body.onSunk?.receive(record.onSunk);
      records.set(view,record);
    }
    function unwatch(record){
      record.body.onSunk?.ignore(record.onSunk);
      if(record.view._render===record.wrapped){
        if(record.own)Object.defineProperty(record.view,'_render',record.own);
        else delete record.view._render;
      }
      records.delete(record.view);
    }
    function reset(){for(const record of records.values())record.fall=null;}
    function detach(){
      for(const record of Array.from(records.values()))unwatch(record);
      scene?.logic?.onSynchronize?.ignore(reset);
      scene?.logic?.onAnimationCanceled?.ignore(reset);
      scene=null;
    }
    function frame(nextScene){
      if(disposed||!nextScene?.table?.getBall)return;
      if(scene!==nextScene){
        detach();scene=nextScene;
        scene.logic?.onSynchronize?.receive(reset);
        scene.logic?.onAnimationCanceled?.receive(reset);
      }
      const seen=new Set(),count=scene.logic?.table?.balls?.length??15;
      for(let rank=0;rank<=count;rank++){
        const view=scene.table.getBall(rank);if(!view)continue;
        seen.add(view);watch(view);
        if(!view.body.isSinking?.())records.get(view).fall=null;
      }
      for(const record of Array.from(records.values()))if(!seen.has(record.view))unwatch(record);
    }
    return {frame,dispose(){if(disposed)return;disposed=true;detach();}};
  }
  window.PlazrPoolSinkPresentation={create};
})();
