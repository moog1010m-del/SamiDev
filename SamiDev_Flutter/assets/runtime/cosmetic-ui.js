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
  window.SamiDevCosmetics={bubble,cover};
})();
