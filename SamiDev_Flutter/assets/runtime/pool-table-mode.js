/* Match-owned artwork selection. Native resource keys and physics stay unchanged. */
(() => {
  'use strict';
  const largeArtwork=Object.freeze({
    'images/imported/themes/th_basic_table.webp':'/images/pool-large/table.webp',
    'images/imported/themes/th_basic_background.webp':'/images/pool-large/background.webp',
    'images/imported/themes/th_basic_preview.webp':'/images/pool-large/preview.webp',
    'images/imported/themes/th_basic_head_line.webp':'/images/pool-large/head-line.webp',
    'images/ui/ui.webp':'/images/pool-large/ui.webp',
    '/images/themes/pool-emerald.webp':'/images/pool-large/emerald.webp',
    '/images/themes/pool-emerald-preview.webp':'/images/pool-large/emerald-preview.webp',
    '/images/cues/moon.webp':'/images/pool-large/moon.webp',
  });
  function create({online=false,settings={},presentation}={}){
    let large=null,resolve;
    const ready=new Promise(accept=>{resolve=accept;});
    function configure(value={}){
      const next=Number(value.largeTable)===1;
      if(large!==null&&large!==next)throw new Error('تغيّر وضع الطاولة أثناء تهيئة المباراة');
      large=next;presentation?.setLargeTable(next);resolve();
    }
    if(!online)configure(settings);
    return {ready,configure,get large(){return large===true;},source(path,fallback=path){return large===true?(largeArtwork[path]||fallback):fallback;}};
  }
  window.PlazrPoolTableMode={create};
})();
