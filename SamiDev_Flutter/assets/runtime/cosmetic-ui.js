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
    const asset=selected?path(id):'/platform/assets/profile/identity/samidev-night-cover.png';
    const image=`url("${asset}")`;
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
  function pickStickers(data,onSelect){
    const items=(data.catalog||[]).filter(item=>item.slot==='name_badge'&&item.owned);
    const dialog=document.createElement('dialog');dialog.className='sd-chat-sticker-picker';const heading=document.createElement('h3');heading.textContent='ملصقاتي';dialog.append(heading);
    const close=document.createElement('button');close.type='button';close.textContent='إغلاق';close.onclick=()=>dialog.close();dialog.append(close);
    if(!items.length){const empty=document.createElement('p');empty.textContent='الملصقات التي تملكها من المتجر تظهر هنا.';dialog.append(empty);}
    for(const item of items){const button=document.createElement('button');button.type='button';button.setAttribute('aria-label',item.name);window.SamiDevStickerArt.render(button,item.asset,item.name);button.onclick=()=>{dialog.close();onSelect(item);};dialog.append(button);}
    dialog.addEventListener('close',()=>dialog.remove(),{once:true});document.body.append(dialog);dialog.showModal();
  }
  window.SamiDevCosmetics={bubble,cover,pop,pickStickers};
})();
