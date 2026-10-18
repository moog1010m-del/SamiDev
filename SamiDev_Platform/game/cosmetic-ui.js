(() => {
  'use strict';
  const bubbles=new Set(['chat_turquoise','chat_mist','chat_ember']);
  const banners=new Set(['banner_dunes','banner_garden','banner_canyon']);
  const path=id=>'/platform/assets/cosmetics/'+id+'.webp';
  function bubble(element,id){
    if(!element)return;
    element.classList.toggle('sd-decorated-message',bubbles.has(id));
    if(bubbles.has(id)){
      element.style.setProperty('--sd-bubble-frame',`url("${path(id)}")`);
      element.style.setProperty('--sd-bubble-fill',({chat_mist:'#24212e',chat_turquoise:'#12312f',chat_ember:'#38201c'})[id]);
    }else{element.style.removeProperty('--sd-bubble-frame');element.style.removeProperty('--sd-bubble-fill');}
  }
  function cover(element,id){
    if(!element)return;
    const selected=banners.has(id);
    const image=selected?`url("${path(id)}")`:'none';
    element.style.setProperty('background-color','#000','important');
    element.classList.add('sd-profile-cover');
    element.classList.toggle('sd-custom-cover',selected);
    element.style.setProperty('--sd-profile-cover',image);
    // Override the identity stylesheet's !important default on every surface.
    element.style.setProperty('background-image',image,'important');
    element.style.setProperty('background-position','center','important');
    element.dataset.sdCover=selected?id:'banner_default';
  }
  let audio;
  function pop(){
    try{if(window.__SAMIDEV_MOBILE_APP||localStorage.getItem('samidev_chat_sound')==='0')return;audio??=new (window.AudioContext||window.webkitAudioContext)();audio.resume().catch(()=>{});const oscillator=audio.createOscillator(),gain=audio.createGain(),t=audio.currentTime;oscillator.type='sine';oscillator.frequency.setValueAtTime(640,t);oscillator.frequency.exponentialRampToValueAtTime(300,t+.065);gain.gain.setValueAtTime(.035,t);gain.gain.exponentialRampToValueAtTime(.001,t+.075);oscillator.connect(gain);gain.connect(audio.destination);oscillator.onended=()=>{oscillator.disconnect();gain.disconnect();};oscillator.start(t);oscillator.stop(t+.08);}catch{}
  }
  let closePicker=null;
  function pickStickers(data,onSelect,options={}){
    if(closePicker){closePicker();return;}
    const anchor=options.anchor||document.activeElement;
    const host=options.host||document.querySelector('#community-panel-chat');
    const mobile=matchMedia('(max-width: 760px)').matches&&host;
    const items=(data.catalog||[]).filter(item=>item.slot==='name_badge'&&item.owned);
    const panel=document.createElement('section');panel.className='sd-chat-sticker-picker';
    panel.setAttribute('role','dialog');panel.setAttribute('aria-label','ملصقاتي');
    const heading=document.createElement('header');heading.textContent='ملصقاتي';panel.append(heading);
    const close=document.createElement('button');close.type='button';close.textContent='×';close.setAttribute('aria-label','إغلاق الملصقات');heading.append(close);
    const grid=document.createElement('div');grid.className='sd-sticker-grid';panel.append(grid);
    if(!items.length){const empty=document.createElement('p');empty.textContent='الملصقات التي تملكها من المتجر تظهر هنا.';grid.append(empty);}
    for(const item of items){const button=document.createElement('button');button.type='button';button.setAttribute('aria-label',item.name);window.SamiDevStickerArt.render(button,item.asset,item.name);button.onclick=()=>{cleanup();onSelect(item);};grid.append(button);}
    const cleanup=()=>{panel.remove();host?.classList.remove('sd-selecting-stickers');anchor?.setAttribute('aria-expanded','false');document.removeEventListener('pointerdown',outside);document.removeEventListener('keydown',escape);window.removeEventListener('resize',cleanup);window.removeEventListener('pagehide',cleanup);closePicker=null;};
    const outside=e=>{if(!panel.contains(e.target)&&!anchor?.contains(e.target))cleanup();};
    const escape=e=>{if(e.key==='Escape'){cleanup();anchor?.focus({preventScroll:true});}};
    close.onclick=cleanup;closePicker=cleanup;anchor?.setAttribute('aria-expanded','true');
    if(mobile){host.classList.add('sd-selecting-stickers');panel.classList.add('sd-sticker-panel-mobile');host.insertBefore(panel,host.querySelector('form'));}
    else{document.body.append(panel);const rect=anchor?.getBoundingClientRect();panel.style.left=Math.max(8,Math.min(innerWidth-panel.offsetWidth-8,(rect?.right||innerWidth-8)-panel.offsetWidth))+'px';panel.style.bottom=Math.max(8,innerHeight-(rect?.top||innerHeight-16)+8)+'px';}
    document.addEventListener('pointerdown',outside);document.addEventListener('keydown',escape);window.addEventListener('resize',cleanup,{once:true});window.addEventListener('pagehide',cleanup,{once:true});
  }
  window.SamiDevCosmetics={bubble,cover,pop,pickStickers,closeStickerPicker:()=>closePicker?.()};
})();
