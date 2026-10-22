/* Guide geometry only. Actual rail/pocket bodies and shot processing are untouched. */
(() => {
  'use strict';
  const EPS=1e-8;
  function circleDistance(p,d,c,r){
    const x=p[0]-c[0],y=p[1]-c[1],b=x*d[0]+y*d[1],q=x*x+y*y-r*r;
    if(q<=0)return 0;
    const discriminant=b*b-q;if(discriminant<0)return Infinity;
    const t=-b-Math.sqrt(discriminant);return t>=0?t:Infinity;
  }
  function polygonDistance(p,d,vertices,radius){
    let area=0,hit=Infinity;
    for(let i=0;i<vertices.length;i++){const a=vertices[i],b=vertices[(i+1)%vertices.length];area+=a[0]*b[1]-a[1]*b[0];}
    const sign=area>=0?1:-1;
    for(let i=0;i<vertices.length;i++){
      const a=vertices[i],b=vertices[(i+1)%vertices.length],dx=b[0]-a[0],dy=b[1]-a[1],len=Math.hypot(dx,dy);
      if(len<EPS)continue;
      const nx=sign*dy/len,ny=-sign*dx/len,denom=nx*d[0]+ny*d[1],distance=nx*(p[0]-a[0])+ny*(p[1]-a[1]);
      if(denom<-EPS&&distance>=radius-EPS){
        const t=Math.max(0,(radius-distance)/denom),x=p[0]+d[0]*t-nx*radius-a[0],y=p[1]+d[1]*t-ny*radius-a[1],along=(x*dx+y*dy)/len;
        if(along>=-EPS&&along<=len+EPS)hit=Math.min(hit,t);
      }
      hit=Math.min(hit,circleDistance(p,d,a,radius));
    }
    return hit;
  }
  function polygons(table){
    const result=[];
    for(const body of table.world.bodies)for(const shape of body.shapes){
      if(!(shape.collisionGroup&12)||!shape.vertices)continue;
      const ba=body.angle||0,sa=ba+(shape.angle||0),cb=Math.cos(ba),sb=Math.sin(ba),c=Math.cos(sa),s=Math.sin(sa),sp=shape.position||[0,0];
      const x=body.position[0]+sp[0]*cb-sp[1]*sb,y=body.position[1]+sp[0]*sb+sp[1]*cb;
      result.push(shape.vertices.map(v=>[x+v[0]*c-v[1]*s,y+v[0]*s+v[1]*c]));
    }
    return result;
  }
  function create(){
    let table=null,original=null,own=null,wrapped=null,disposed=false;
    function detach(){
      if(table?.getPointMinDistToRail===wrapped){if(own)Object.defineProperty(table,'getPointMinDistToRail',own);else delete table.getPointMinDistToRail;}
      table=original=own=wrapped=null;
    }
    function frame(scene){
      const next=scene?.logic?.table;
      if(disposed||!next?.world?.bodies||typeof next.getPointMinDistToRail!=='function'||next===table)return;
      detach();table=next;original=table.getPointMinDistToRail;own=Object.getOwnPropertyDescriptor(table,'getPointMinDistToRail');
      const rails=polygons(table);
      wrapped=function(point,angle){
        if(!Number.isFinite(angle)||!Number.isFinite(point?.[0])||!Number.isFinite(point?.[1]))return original.apply(this,arguments);
        const direction=[Math.cos(angle),Math.sin(angle)],radius=this.cueBall.radius;
        let distance=Infinity;
        for(const rail of rails)distance=Math.min(distance,polygonDistance(point,direction,rail,radius));
        for(const pocket of this.pockets)distance=Math.min(distance,circleDistance(point,direction,pocket.position,pocket.radius-radius));
        return Number.isFinite(distance)?distance:original.apply(this,arguments);
      };
      table.getPointMinDistToRail=wrapped;
      scene.onCueBallMoved?.emit();
    }
    return {frame,dispose(){if(disposed)return;disposed=true;detach();}};
  }
  window.PlazrPoolAimPresentation={create};
})();
