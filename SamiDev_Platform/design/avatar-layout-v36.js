/* Shared source, embedded into all four engines by tools/apply_v36_ui.py. */
globalThis.SamiDevAvatarHUDState = {avatars:new Set(),timers:new Set(),clocks:new WeakMap(),canvas:null};
globalThis.SamiDevAvatarLayout = Object.freeze({
  trackTimer(timer) { globalThis.SamiDevAvatarHUDState.timers.add(timer); return 0; },
  position(a) {
    globalThis.SamiDevAvatarHUDState.avatars.add(a);
    const row = a.idContainer, badges = a.badgeContainer, name = a.nameText;
    const measure = a.nameTextMeasure, radius = a._imageRadius;
    const font = name.fontSize || 40, gap = Math.max(8, font * .22);
    const margin = Math.max(a.nameMargin || 0, font * .28);
    const rowBudget = Math.min(a.maxNameWidth > 0 ? a.maxNameWidth : Infinity, radius * 4.8);
    const rawBadgeWidth = badges.visible ? badges.width : 0;
    const badgeScale = rawBadgeWidth ? Math.min(1, rowBudget * .4 / rawBadgeWidth) : 1;
    badges.scaleX = badges.scaleY = badgeScale;
    const badgeWidth = rawBadgeWidth * badgeScale;
    a._plazrTurnBadge=!!(a._turn&&a._localSeat&&a.showTurnPill&&a.showName);
    a.localTurnPill.visible=false;
    const pillWidth=0;
    const budget = Math.max(0, rowBudget - badgeWidth - (badgeWidth ? gap : 0) - (pillWidth?pillWidth+gap:0));
    // Always measure the full name again: shrinking then growing the viewport
    // must restore characters, including Arabic and surrogate pairs.
    const full = String(a.oldNameTextContents || ''), chars = Array.from(full);
    measure.text = full; measure._update();
    if (measure.width > budget) {
      let low = 0, high = chars.length;
      while (low < high) {
        const mid = Math.ceil((low + high) / 2);
        measure.text = chars.slice(0, mid).join('') + 'â€¦'; measure._update();
        if (measure.width <= budget) low = mid; else high = mid - 1;
      }
      measure.text = chars.slice(0, low).join('') + 'â€¦'; measure._update();
      if (measure.width > budget) { measure.text = ''; measure._update(); }
    }
    name.text = measure.text;
    name._update?.();
    const nameWidth=name.width||measure.width;
    const height = Math.max(font * 1.35, (badges.height || 0) * badgeScale);
    row.resize(badgeWidth + (badgeWidth ? gap : 0) + nameWidth + (pillWidth?pillWidth+gap:0), height);
    badges.anchorX = 0; badges.anchorY = 0;
    badges.position(0, (height - badges.height * badgeScale) / 2);
    name.anchorX = 0; name.anchorY = .5;
    name.position(badgeWidth + (badgeWidth ? gap : 0), height / 2);
    const pill = a.localTurnPill;
    // Keep the name visible during the local turn; the badge has its own slot.
    name.visible = !!a.showName && a.seat >= 0;
    if(pill.visible) pill.resize(pillWidth, font * .95);
    switch (a.nameAlign) {
      case 'ABOVE':
        row.anchorX = .5; row.anchorY = 1; row.position(0, -radius - margin);
        pill.anchorX = .5; pill.anchorY = 1; pill.position(0, -radius - margin);
        break;
      case 'LEFT':
        row.anchorX = 1; row.anchorY = .5; row.position(-radius - margin, 0);
        pill.anchorX = 1; pill.anchorY = .5; pill.position(-radius - margin, 0);
        break;
      case 'RIGHT':
        row.anchorX = 0; row.anchorY = .5; row.position(radius + margin, 0);
        pill.anchorX = 0; pill.anchorY = .5; pill.position(radius + margin, 0);
        break;
      default:
        row.anchorX = .5; row.anchorY = 0; row.position(0, radius + margin);
        pill.anchorX = .5; pill.anchorY = 0; pill.position(0, radius + margin);
    }
    if(pill.visible){
      pill.anchorX=.5;pill.anchorY=.5;
      const nameRight=row.x-row.anchorX*row.width+name.x+measure.width;
      pill.position(nameRight+gap+pillWidth*.5,row.y+(.5-row.anchorY)*height);
    }
    // Connection state belongs to the avatar, never to the measured name row.
    const dot = a._activeIndicator;
    const diameter = Math.max(12, Math.min(font * .4, radius * .30));
    dot.resize(diameter, diameter); dot.anchorX = dot.anchorY = .5;
    dot.position(radius * .68, radius * .55);
    this.owner(a);
  },
  point(node,x=0,y=0) {
    if(typeof node.localToWorld==='function')return node.localToWorld({x,y});
    // Rebuild from the live scene graph: renderer matrices are scratch buffers.
    let depth=0;
    for(let n=node;n&&depth++<30;n=n.parent){
      const w=n.width||0,h=n.height||0,px=(n.pivotX||0)*w,py=(n.pivotY||0)*h;
      const sx=Number.isFinite(n.scaleX)?n.scaleX:1,sy=Number.isFinite(n.scaleY)?n.scaleY:1;
      const c=Math.cos(n.rotation||0),s=Math.sin(n.rotation||0),dx=(x-px)*sx,dy=(y-py)*sy;
      x=c*dx-s*dy+(n.x||0)-(n.anchorX||0)*w+px;
      y=s*dx+c*dy+(n.y||0)-(n.anchorY||0)*h+py;
    }
    return {x,y};
  },
  frame(canvas, now, scene) {
    const state=globalThis.SamiDevAvatarHUDState;
    if(!canvas||typeof document==='undefined')return;
    const visible=node=>{let count=0;for(let n=node;n&&count++<30;n=n.parent)if(n.visible===false)return false;return !!node.parent;};
    const timers=[...state.timers].filter(t=>t.time>0&&t.timer&&visible(t));
    for(const t of state.timers)t.alpha=0; // Presentation only: native timer events continue.
    if(!state.canvas){state.canvas=document.createElement('canvas');state.canvas.setAttribute('aria-hidden','true');state.canvas.style.cssText='position:fixed;pointer-events:none;z-index:7';document.body.appendChild(state.canvas);}
    const layer=state.canvas,rect=canvas.getBoundingClientRect(),dpr=Math.min(2,globalThis.devicePixelRatio||1);
    const w=Math.max(1,Math.round(rect.width*dpr)),h=Math.max(1,Math.round(rect.height*dpr));
    if(layer.width!==w||layer.height!==h){layer.width=w;layer.height=h;}
    Object.assign(layer.style,{left:rect.left+'px',top:rect.top+'px',width:rect.width+'px',height:rect.height+'px'});
    const ctx=layer.getContext('2d');ctx.setTransform(dpr,0,0,dpr,0,0);ctx.clearRect(0,0,rect.width,rect.height);
    const timer=timers[0];let clock=timer?state.clocks.get(timer):null;
    if(timer&&(!clock||clock.value!==timer.countdown)){clock={value:timer.countdown,at:now};state.clocks.set(timer,clock);}
    const ratio=timer?Math.max(0,Math.min(1,(timer.countdown-Math.min(now-clock.at,timer.tickDuration||500))/timer.time)):0;
    const sx=rect.width/canvas.width,sy=rect.height/canvas.height;
    const poolUnit=scene?.layoutInfo?.logScale?sx/scene.layoutInfo.logScale:null;
    const project=(a,x=0,y=0)=>poolUnit!==null?{x:(a.x+x*(a.scaleX||1))*poolUnit,y:(a.y+y*(a.scaleY||1))*poolUnit}:this.point(a,x,y);
    for(const a of state.avatars){
      if(!visible(a))continue;
      if(a._plazrTurnBadge&&a.idContainer){
        const row=a.idContainer,name=a.nameText,measure=a.nameTextMeasure;
        const edge=poolUnit!==null?project(a,row.x-row.anchorX*row.width+name.x+(name.width||measure.width),row.y+(.5-row.anchorY)*row.height):this.point(row,name.x+(name.width||measure.width),row.height/2);
        const bw=37,bh=19,bx=Math.min(rect.width-bw-5,edge.x*(poolUnit!==null?1:sx)+7),by=edge.y*(poolUnit!==null?1:sy)-bh/2;
        ctx.fillStyle='#244b51';ctx.beginPath();ctx.roundRect(bx,by,bw,bh,6);ctx.fill();ctx.fillStyle='#f0e0b4';ctx.font='600 11px system-ui';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText('ÏæÑß',bx+bw/2,by+bh/2);
      }
      if(!timer||!a._turn)continue;
      const center=project(a),edge=project(a,a._imageRadius,0),ux=poolUnit!==null?1:sx,uy=poolUnit!==null?1:sy;
      const x=center.x*ux,y=center.y*uy,r=Math.hypot((edge.x-center.x)*ux,(edge.y-center.y)*uy)+4;
      if(!Number.isFinite(r)||r<4)continue;
      ctx.lineWidth=3;ctx.strokeStyle='rgba(134,158,159,.28)';ctx.beginPath();ctx.arc(x,y,r,0,Math.PI*2);ctx.stroke();
      ctx.strokeStyle=ratio<.25?'#dfad58':'#55c3bd';ctx.lineCap='round';ctx.beginPath();ctx.arc(x,y,r,-Math.PI/2,-Math.PI/2+ratio*Math.PI*2);ctx.stroke();
    }
    return !!timer;
  },
  poolBalls(scene) {
    if(!scene?.avatars?.get||!scene.gapBalls?.length)return;
    const logic=scene.logic,groups=new Map();
    if(logic.freePool)return;
    for(let index=0;index<scene.gapBalls.length;index++){
      const ball=scene.gapBalls[index];if(!ball.visible)continue;
      const rank=ball.getRank();let seats=[];
      for(let seat=0;seat<logic.seats;seat++){
        let owns=false;
        if(logic.freePool)owns=seat===(logic.currentShot?.seat??logic.turn[0]);
        else if(logic.isCutthroatGame())owns=logic.getCutthroatGroupBySeat(seat).includes(rank);
        else if(logic.is8BallGame()&&logic.getSolids()>=0)owns=logic.isPlayerPlayingSolids(seat)===(rank===8?index===14:rank<8);
        else if(logic.is9BallGame())owns=seat===index%logic.seats;
        if(owns)seats.push(seat);
      }
      const seat=seats[0];if(seat===undefined)continue;
      if(!groups.has(seat))groups.set(seat,[]);groups.get(seat).push(ball);
    }
    for(const [seat,balls] of groups){
      const a=scene.avatars.get(seat);if(!a)continue;
      const radius=a._imageRadius*(a.scaleX||1),font=a.nameText?.fontSize||40;
      const step=Math.max(42,Math.min(58,radius*.9));
      const y=a.y+radius+Math.max(a.nameMargin||0,font*.28)+font*1.35+step*.6;
      balls.sort((a,b)=>a.getRank()-b.getRank());
      balls.forEach((ball,i)=>{ball.scale=1;ball.position(a.x+(i-(balls.length-1)/2)*step,y);});
    }
  },
  owner(a) {
    a.checkOwnerBadgeVisibility();
    const crown = a.ownerIndicator;
    if (!crown) return;
    const radius = a._imageRadius, size = Math.max(22, Math.min(36, radius * .55));
    crown.resize(size, size); crown.anchorX = crown.anchorY = .5;
    crown.position(-radius * .62, -radius * .62);
  }
});
