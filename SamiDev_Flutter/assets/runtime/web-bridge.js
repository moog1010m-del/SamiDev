(() => {
  'use strict';

  function haptic(type='selection') {
    try {
      if (!navigator.vibrate) return;
      const pattern = type === 'warning' ? [35, 35, 35] : type === 'success' ? [20, 25, 45] : [18];
      navigator.vibrate(pattern);
    } catch (_) {}
  }

  function inviteLink(inviteToken) {
    const token = String(inviteToken || '').trim();
    if (!/^[A-Za-z0-9_-]{20,64}$/.test(token)) throw new Error('رمز الدعوة غير صالح');
    const url = new URL('/platform/', location.origin);
    url.searchParams.set('invite', token);
    url.searchParams.set('game',window.SamiDevGames.current().id);
    return url.toString();
  }

  function matchLabel(settings={}) { return window.SamiDevGames.label(settings); }

  async function copyText(text) {
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (_) {
      const input = document.createElement('textarea');
      input.value = text;
      input.setAttribute('readonly', '');
      input.style.position = 'fixed';
      input.style.opacity = '0';
      document.body.appendChild(input);
      input.select();
      let ok = false;
      try { ok = document.execCommand('copy'); } catch (_) {}
      input.remove();
      return ok;
    }
  }

  async function shareInvite({inviteToken, inviterName, settings}={}) {
    const url = inviteLink(inviteToken);
    const who = String(inviterName || 'صديقك').trim().slice(0, 40) || 'صديقك';
    const mode = matchLabel(settings || {});
    const text = `🎯 ${who} يتحداك في ${window.SamiDevGames.current().title}\n⚡ ${mode}\nادخل المباراة قبل انتهاء الدعوة:`;
    haptic('selection');

    if (navigator.share) {
      try {
        await navigator.share({title: window.SamiDevGames.current().title, text, url});
        return {url, shared: true};
      } catch (e) {
        if (e?.name === 'AbortError') return {url, cancelled: true};
      }
    }

    const copied = await copyText(`${text}\n${url}`);
    if (!copied) window.prompt('انسخ رابط الدعوة:', url);
    return {url, copied};
  }

  window.SamiDevPlatform = {haptic, inviteLink, shareInvite, copyText};
})();
