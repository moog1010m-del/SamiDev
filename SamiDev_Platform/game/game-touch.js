(() => {
  'use strict';
  const canvas = document.getElementById('game');
  if (!canvas) return;
  const editable = target => !!target?.closest?.('input,textarea,select,[contenteditable]:not([contenteditable="false"])');
  const prevent = event => { if (event.cancelable !== false) event.preventDefault(); };
  // WebKit needs prefixed CSS plus cancellation of native canvas touch gestures.
  // Pointer events still carry the game's taps and drags; no synthetic click is sent.
  for (const type of ['touchstart', 'touchmove', 'touchend', 'gesturestart', 'gesturechange', 'gestureend']) {
    canvas.addEventListener(type, prevent, {passive: false});
  }
  for (const type of ['dblclick', 'selectstart', 'contextmenu', 'dragstart']) {
    document.addEventListener(type, event => {
      if (!editable(event.target)) prevent(event);
    }, {capture: true, passive: false});
  }
  let lastTap = null;
  document.addEventListener('touchend', event => {
    const target = event.target;
    if (target === canvas || editable(target) || event.changedTouches?.length !== 1) {
      lastTap = null;
      return;
    }
    const touch = event.changedTouches[0], now = performance.now();
    if (lastTap && lastTap.target === target && now - lastTap.time < 320 &&
        Math.hypot(touch.clientX - lastTap.x, touch.clientY - lastTap.y) < 24) prevent(event);
    lastTap = {target, time: now, x: touch.clientX, y: touch.clientY};
  }, {passive: false});
})();
