(() => {
  'use strict';
  // The server owns the selection. Only bundled, allowlisted atlases may load.
  const themes = Object.freeze({
    carrom_classic: Object.freeze({id:'carrom_classic', name:'كلاسيك', atlas:'images/game.webp?v=f566bcd679679d4c'}),
    carrom_cat: Object.freeze({id:'carrom_cat', name:'القطو الملكي', atlas:'images/themes/cat-atlas.webp?v=c609d3058fd43894'}),
  });
  const defaultTheme = themes.carrom_classic;

  function fromSnapshot(snapshot) {
    const id = snapshot?.equipped?.carrom_theme;
    const catalog = Array.isArray(snapshot?.catalog) ? snapshot.catalog : [];
    const item = catalog.find(entry => entry && entry.id === id && entry.slot === 'carrom_theme' && entry.owned === true);
    return Object.prototype.hasOwnProperty.call(themes, id) && item ? themes[id] : defaultTheme;
  }

  async function resolve() {
    if (typeof fetch !== 'function') return defaultTheme;
    const controller = typeof AbortController === 'function' ? new AbortController() : null;
    let timeout;
    try {
      const request = fetch('/api/store', {credentials:'same-origin', cache:'no-store', ...(controller ? {signal:controller.signal} : {})})
        .then(async response => response.ok ? fromSnapshot(await response.json()) : defaultTheme)
        .catch(() => defaultTheme);
      const deadline = new Promise(resolveTimeout => {
        timeout = setTimeout(() => { controller?.abort(); resolveTimeout(defaultTheme); }, 2500);
      });
      return await Promise.race([request, deadline]);
    } finally {
      clearTimeout(timeout);
    }
  }

  window.SamiDevCarromThemes = Object.freeze({themes, defaultTheme, fromSnapshot, resolve});
})();
