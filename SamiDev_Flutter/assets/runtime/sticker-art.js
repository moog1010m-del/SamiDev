(() => {
  'use strict';
  let clipId=0;
  const sheet='/platform/assets/stickers/samidev-stickers.png';
  const independent=['badge_crown','badge_orbit','badge_shell','badge_fox','badge_fire','badge_crystal','badge_leopard','badge_jellyfish'];
  function resolve(value){
    value=String(value||'').replace(/^(\/platform\/assets\/stickers\/badge_[a-z]+)-v2\.png$/,'$1-v3.png');
    const index=cell(value);
    if(index!==null&&index<9)return index<independent.length?'/platform/assets/stickers/'+independent[index]+'-v3.png':'';
    const old=String(value||'').match(/^\/platform\/assets\/cosmetics\/(badge_(?:shard|ember|moonstone|steward))\.webp$/);
    return old?'/platform/assets/stickers/'+old[1]+'-v3.png':String(value||'');
  }
  const esc=value=>String(value??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function cell(value){if(value==='/platform/assets/profile/identity/profile-atlas.png#star')return 9;const match=String(value||'').match(/^\/platform\/assets\/stickers\/samidev-stickers\.png#cell-([0-8])$/);return match?Number(match[1]):null;}
  function markup(value,className='',label=''){
    if(value==='/platform/assets/profile/raster/palm-swords.webp')return '';
    value=resolve(value);
    value=String(value||'').replace('/images/cues/classic-preview.webp','/images/cues/classic.webp').replace('/images/cues/moon-preview.webp','/images/cues/moon.webp');
    const index=cell(value);
    if(index!==null){
      const col=index===9?0:index%3,row=index===9?0:Math.floor(index/3),id='sd-sticker-clip-'+(++clipId);
      return `<svg class="sd-sticker-art ${esc(className)}" viewBox="${col} ${row} 1 1" role="img" aria-label="${esc(label)}"><defs><clipPath id="${id}"><rect x="${col}" y="${row}" width="1" height="1"/></clipPath></defs><g clip-path="url(#${id})"><image href="${index===9?'/platform/assets/profile/identity/profile-atlas.png':sheet}" width="${index===9?4:3}" height="${index===9?2:3}" preserveAspectRatio="none"/></g></svg>`;
    }
    if(!/^\/(?:images|games|platform\/assets|room-sprites)\/[A-Za-z0-9_./-]+$/.test(String(value))||String(value).includes('..'))return '';
    return `<img class="${esc(className)}" src="${esc(value)}" alt="${esc(label)}" loading="lazy">`;
  }
  function render(root,value,label=''){if(!root)return;root.classList.add('sd-sprite-badge');root.innerHTML=markup(value,'',label);root.hidden=!root.innerHTML;}
  const style=document.createElement('style');style.textContent='.sd-sticker-art{display:block;overflow:hidden;max-width:100%;max-height:100%}.sd-sprite-badge[hidden]{display:none!important}.sd-sprite-badge{background-image:none!important;display:inline-flex;align-items:center;justify-content:center}.sd-sprite-badge>svg,.sd-sprite-badge>img{width:100%;height:100%;object-fit:contain}.sd-owned-card .sd-sticker-art{width:100%;height:64px}.sd-item-art{height:140px;width:100%;display:grid;place-items:center}.sd-item-art>svg,.sd-item-art>img{width:100%;height:100%;object-fit:contain}.profile-stars [hidden],.lobby-profile-stars [hidden],.community-member-stars [hidden]{display:none!important}';document.head.appendChild(style);
  function productMarkup(item,className=''){
    if(item.gameId!=='pool'||!['pool_theme','pool_cue','pool_pocket_effect'].includes(item.slot))return markup(item.asset,className,item.name);
    if(item.slot==='pool_cue'){
      const asset=String(item.asset||'').replace('/images/cues/classic-preview.webp','/images/cues/classic.webp').replace('/images/cues/moon-preview.webp','/images/cues/moon.webp');
      if(!/^\/images\/cues\/[a-z-]+\.webp$/.test(asset))return markup(item.asset,className,item.name);
      return `<div class="sd-product-stage sd-product-pool_cue ${esc(className)}" role="img" aria-label="${esc(item.name)}"><div class="sd-cue-display-parts" aria-hidden="true"><span class="sd-cue-display-butt" style="--cue-image:url('${esc(asset)}')"></span><span class="sd-cue-display-shaft" style="--cue-image:url('${esc(asset)}')"></span></div></div>`;
    }
    const artwork=markup(item.asset,'sd-product-object',item.name);
    return `<div class="sd-product-stage sd-product-${esc(item.slot)} ${esc(className)}">${artwork}</div>`;
  }
  const productStyle=document.createElement('style');productStyle.textContent=`
  .sd-product-stage{position:relative;isolation:isolate;display:grid!important;place-items:center;width:100%;height:180px!important;padding:0!important;overflow:hidden;border-radius:14px;background:radial-gradient(ellipse at 50% 40%,#315357 0%,#1b3038 52%,#14232c 100%)!important;box-sizing:border-box}
  .sd-product-stage:after{content:'';position:absolute;inset:auto 0 0;height:34%;background:linear-gradient(transparent,#14232c99);pointer-events:none}
  .sd-product-stage>img.sd-product-object{display:block;max-width:none;max-height:none;object-fit:contain;padding:0!important;box-sizing:border-box;background:none!important;filter:drop-shadow(0 12px 10px #0007)}
  .sd-product-stage.sd-product-pool_theme>img.sd-product-object{width:150px!important;height:270px!important;transform:translateY(28px) rotate(-26deg)}
  .sd-product-stage.sd-product-pool_cue>img.sd-product-object{width:90%!important;height:auto!important;transform:rotate(-27deg)}
  .sd-product-stage>.sd-cue-display-parts{position:absolute;left:16%;top:17%;width:72%;height:66%;padding:0!important;display:flex!important;flex-direction:column;align-items:center;justify-content:center;gap:20px!important;transform:rotate(-43deg);direction:ltr}
  .sd-cue-display-parts>span{display:block;flex:none;background-image:var(--cue-image);background-repeat:no-repeat;filter:drop-shadow(0 3px 3px #0007)}
  .sd-cue-display-butt{width:68%;aspect-ratio:14.5;background-size:263.158% 100%;background-position:left center;align-self:flex-start}
  .sd-cue-display-shaft{width:100%;aspect-ratio:23.4;background-size:161.29% 100%;background-position:right center;align-self:flex-end}
  .sd-product-stage.sd-product-pool_pocket_effect>img.sd-product-object{width:78%!important;height:145px!important}
  html[data-theme=light] .sd-product-stage{background:radial-gradient(ellipse at 50% 40%,#fff 0%,#e6f0ed 55%,#d4e2df 100%)!important}
  html[data-theme=light] .sd-product-stage:after{background:linear-gradient(transparent,#c6d9d455)}
  @media(max-width:540px){.sd-product-stage{height:150px!important}.sd-product-stage.sd-product-pool_theme>img.sd-product-object{width:132px!important;height:238px!important}.sd-product-stage.sd-product-pool_pocket_effect>img.sd-product-object{height:120px!important}}
  `;document.head.appendChild(productStyle);
  window.SamiDevStickerArt={cell,resolve,markup,render,productMarkup};
})();
