(() => {
  'use strict';
  let clipId=0;
  const sheet='/platform/assets/stickers/samidev-stickers.png';
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function cell(value){if(value==='/platform/assets/profile/identity/profile-atlas.png#star')return 9;const match=String(value||'').match(/^\/platform\/assets\/stickers\/samidev-stickers\.png#cell-([0-8])$/);return match?Number(match[1]):null;}
  function markup(value,className='',label=''){
    const index=cell(value);
    if(index!==null){
      const col=index===9?0:index%3,row=index===9?0:Math.floor(index/3),id='sd-sticker-clip-'+(++clipId);
      return `<svg class="sd-sticker-art ${esc(className)}" viewBox="${col} ${row} 1 1" role="img" aria-label="${esc(label)}"><defs><clipPath id="${id}"><rect x="${col}" y="${row}" width="1" height="1"/></clipPath></defs><g clip-path="url(#${id})"><image href="${index===9?'/platform/assets/profile/identity/profile-atlas.png':sheet}" width="${index===9?4:3}" height="${index===9?2:3}" preserveAspectRatio="none"/></g></svg>`;
    }
    if(!/^\/(?:images|games|platform\/assets|room-sprites)\/[A-Za-z0-9_./-]+$/.test(String(value))||String(value).includes('..'))return '';
    return `<img class="${esc(className)}" src="${esc(value)}" alt="${esc(label)}" loading="lazy">`;
  }
  function render(root,value,label=''){if(!root)return;root.classList.add('sd-sprite-badge');root.innerHTML=markup(value,'',label);}
  const style=document.createElement('style');style.textContent='.sd-sticker-art{display:block;overflow:hidden;max-width:100%;max-height:100%}.sd-sprite-badge{background-image:none!important;display:inline-flex;align-items:center;justify-content:center}.sd-sprite-badge>svg,.sd-sprite-badge>img{width:100%;height:100%;object-fit:contain}.sd-owned-card .sd-sticker-art{width:100%;height:64px}.sd-item-art{height:140px;width:100%;display:grid;place-items:center}.sd-item-art>svg,.sd-item-art>img{width:100%;height:100%;object-fit:contain}.profile-stars [hidden],.lobby-profile-stars [hidden],.community-member-stars [hidden]{display:none!important}';document.head.appendChild(style);
  window.SamiDevStickerArt={cell,markup,render};
})();
