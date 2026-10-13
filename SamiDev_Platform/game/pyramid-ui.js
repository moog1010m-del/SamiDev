(() => {
  'use strict';
  if (window.SamiDevGames?.current().id !== 'pool') return;
  const style=document.createElement('style');
  style.textContent=`#sd-pyramid-ui{position:fixed;inset:0;z-index:24;pointer-events:none}#sd-pyramid-ui[hidden]{display:none}.pyr-select-ball{position:absolute;border:2px dotted #fff;border-radius:50%;background:transparent;padding:0;pointer-events:auto;touch-action:manipulation;box-shadow:0 0 3px #0008;cursor:pointer}.pyr-select-ball[hidden]{display:none}.pyr-choice-status{position:absolute;transform:translate(-50%,-100%);max-width:80vw;white-space:nowrap;border-radius:999px;background:#122b31eb;color:#fff;padding:6px 10px;font:11px/1.5 Arial;text-align:center}`;
  document.head.append(style);
  const root=document.createElement('div');root.id='sd-pyramid-ui';root.hidden=true;
  const caption=document.createElement('div');caption.className='pyr-choice-status';root.append(caption);
  const buttons=Array.from({length:15},(_,index)=>{
    const button=document.createElement('button');button.type='button';button.className='pyr-select-ball';button.dataset.rank=String(index+1);root.append(button);
    button.addEventListener('click',event=>{
      event.preventDefault();event.stopPropagation();const g=window.__gameLogic,rank=index+1;
      if(g?.canSelectPyramidCue?.(g.localSeat,rank)&&!g.animator?.isAnimatingWorld?.()&&!g.preshooting){
        if(g.localMove({a:9,rank}))for(const item of buttons)item.hidden=true;
      }
    });return button;
  });
  document.body.append(root);
  const place=(node,x,y,diameter)=>{
    const transform=`translate(${(x-diameter/2).toFixed(2)}px,${(y-diameter/2).toFixed(2)}px)`;
    if(node.style.transform!==transform)node.style.transform=transform;
    const size=diameter.toFixed(2)+'px';if(node.style.width!==size){node.style.width=size;node.style.height=size;}
  };
  function update(){
    const g=window.__gameLogic,projection=window.__samidevGameState?.poolProjection;
    if(!g?.pyramid||!projection||!g.started||g.gameOver){root.hidden=true;requestAnimationFrame(update);return;}
    root.hidden=false;
    const rect=document.getElementById('game').getBoundingClientRect(),view=projection.view;
    const sx=rect.width/projection.width,sy=rect.height/projection.height;
    const screen=position=>{const p=view.toWorldCoordinates(position);return [rect.x+p[0]*sx,rect.y+p[1]*sy];};
    const available=g.pyramid.canSelect&&g.localSeat>=0&&g.isTurn(g.localSeat)&&!g.paused&&!g.preshooting&&!g.animator.isAnimatingWorld();
    for(let index=0;index<15;index++){
      const ball=g.table.balls[index],button=buttons[index],rank=index+1;
      const hidden=!available||!g.canSelectPyramidCue(g.localSeat,rank);if(button.hidden!==hidden)button.hidden=hidden;
      if(!button.hidden){const [x,y]=screen(ball.position);place(button,x,y,Math.max(16,ball.radius*2*view.scaleX*sx+6));const id=g.pyramid.ids[rank],label=id===0?'اختيار الكرة الصفراء للضرب':'اختيار كرة '+id+' للضرب';if(button.getAttribute('aria-label')!==label)button.setAttribute('aria-label',label);}
    }
    caption.hidden=!g.isTurn(g.localSeat)||g.preshooting||g.animator.isAnimatingWorld();
    if(!caption.hidden){const [x,y]=screen([417,-55]);const left=x+'px',top=y+'px';if(caption.style.left!==left)caption.style.left=left;if(caption.style.top!==top)caption.style.top=top;const text=available?'النقاط البيضاء: اختر كرة الضرب مرة واحدة':'تم اختيار كرة الضرب — صوّب الآن';if(caption.textContent!==text)caption.textContent=text;}
    requestAnimationFrame(update);
  }
  requestAnimationFrame(update);
})();
