(() => {
  'use strict';
  const bubbles=new Set(['chat_turquoise','chat_mist','chat_ember']);
  const banners=new Set(['banner_dunes','banner_garden','banner_canyon']);
  const path=id=>'/platform/assets/cosmetics/'+id+'.webp';
  function bubble(element,id){
    if(!element)return;
    element.classList.toggle('sd-decorated-message',bubbles.has(id));
    if(bubbles.has(id))element.style.setProperty('--sd-bubble-frame',`url("${path(id)}")`);
    else element.style.removeProperty('--sd-bubble-frame');
  }
  function cover(element,id){
    if(!element)return;
    element.classList.toggle('sd-custom-cover',banners.has(id));
    if(banners.has(id))element.style.setProperty('--sd-profile-cover',`url("${path(id)}")`);
    else element.style.removeProperty('--sd-profile-cover');
  }
  window.SamiDevCosmetics={bubble,cover};
})();
