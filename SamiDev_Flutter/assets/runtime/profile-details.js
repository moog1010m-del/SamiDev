(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number = v => Math.max(0, Math.floor(Number(v) || 0));
  const count = v => number(v).toLocaleString('ar-SA');
  const asset = v => window.SamiDevStickerArt?.cell(v)!==null && window.SamiDevStickerArt?.cell(v)!==undefined ? String(v) : /^\/(?:images|games|platform\/assets|room-sprites)\/[A-Za-z0-9_./-]+$/.test(String(v)) && !String(v).includes('..') ? String(v) : '';
  const games = [['pool','البلياردو','pool'],['carrom','الكيرم','carrom'],['tablesoccer','كرة الطاولة','football'],['crazy8','أونو','cards']];

  // Shared original vector art: the server remains the source of level/score.
  const reputationThresholds = [0, 1, 100, 500, 1000, 10000, 50000];
  function reputationTier(score) {
    const value=number(score);
    return reputationThresholds.reduce((tier, threshold, i)=>value>=threshold?i:tier,0);
  }
  function flameMarkup(score) {
    const tier=reputationTier(score);
    return `<span class="sd-reputation-flame" data-reputation-tier="${tier}" role="img" aria-label="سمعة ${count(score)}"><svg viewBox="0 0 40 48" aria-hidden="true"><path class="sd-flame-halo" d="M20 2C22 13 35 15 35 29c0 10-7 16-15 16S5 39 5 29c0-7 4-12 7-16 0 6 2 8 4 9C20 16 15 10 20 2Z"/><path class="sd-flame-body" d="M21 7c1 10 11 13 11 23 0 8-5 13-12 13S8 38 8 30c0-5 2-8 5-12 0 6 3 8 5 9 5-7 0-13 3-20Z"/><path class="sd-flame-core" d="M21 25c1 5 6 6 6 11a7 7 0 0 1-14 0c0-3 2-6 4-8 0 4 2 5 3 6 2-3 0-6 1-9Z"/><path class="sd-flame-sparks" d="m6 8 1 3m25-6-1 4M2 26l2 1m32-8 2-2"/></svg></span>`;
  }
  function renderReputation(root, score) {
    if(!root)return;
    root.classList.add('sd-reputation-slot');
    root.innerHTML=flameMarkup(score);
  }
  function rankMarkup(level) {
    level=Math.max(1,Math.min(100,number(level)));
    const tier=Math.floor((level-1)/10);
    return `<span class="sd-rank-star" data-tier="${tier}" role="img" aria-label="المستوى ${level}"><svg viewBox="0 0 64 64" aria-hidden="true"><path class="sd-star-edge" d="m32 5 8 16 18 3-13 13 3 19-16-9-16 9 3-19L6 24l18-3Z"/><path class="sd-star-face" d="m32 11 6.5 14 15 2-11 11 2.5 14-13-7-13 7 2.5-14-11-11 15-2Z"/></svg><b>${level}</b></span>`;
  }

  function render(root, user, {own = false} = {}) {
    if (!root) return;
    const items = (Array.isArray(user.showcaseItems) ? user.showcaseItems : []).filter(x => x && x.id && number(x.quantity || 1));
    const stats = Array.isArray(user.gameStatistics) ? user.gameStatistics : [];
    const playedGames = games.filter(([id]) => stats.some(s => s.gameId === id && number(s.played) > 0));
    const collected = number(user.collectionOwnedCount ?? new Set(items.map(x=>x.id)).size);
    const catalogTotal = Math.max(collected, number(user.collectionTotalCount));
    const completion = catalogTotal ? Math.min(100, collected / catalogTotal * 100) : 0;
    const total = items.reduce((sum, x) => sum + number(x.quantity || 1), 0);
    let expanded = false, full = false;
    root.classList.add('sd-profile-details');
    root.setAttribute('dir', 'rtl');
    root.innerHTML = `<section class="sd-collection-section" aria-label="المقتنيات">
      <header class="sd-detail-heading"><h3>${own ? 'مقتنياتي' : 'مقتنيات اللاعب'}</h3><span class="sd-collection-count" dir="rtl">${count(collected)} من ${count(catalogTotal)}</span></header>
      <div class="sd-collection-progress" role="progressbar" aria-label="تقدم جمع المقتنيات" aria-valuemin="0" aria-valuemax="${catalogTotal}" aria-valuenow="${collected}"><span style="width:${completion}%"></span></div>
      <div class="sd-collection-controls" hidden><label>تصفّح حسب اللعبة <select aria-label="تصفية المقتنيات"><option value="all">كل المقتنيات</option><option value="profile">زينة الملف</option>${games.map(([id, name]) => `<option value="${id}">${name}</option>`).join('')}</select></label></div>
      <div class="sd-collection-grid"></div>
      <p class="sd-collection-empty" ${items.length ? 'hidden' : ''}>${own ? 'ستظهر هنا المقتنيات التي تجمعها أو تشتريها.' : 'لا توجد مقتنيات مملوكة للعرض بعد.'}</p>
      <button class="sd-collection-more" type="button" aria-expanded="false" ${items.length ? '' : 'hidden'}>تصفّح كل المقتنيات (${count(total)})</button>
      <div class="sd-item-detail" role="dialog" aria-modal="true" aria-label="تفاصيل المقتنى" hidden><button class="sd-item-close" type="button" aria-label="إغلاق تفاصيل المقتنى">×</button><div class="sd-item-art"></div><h4></h4><p></p></div>
      </section><section class="sd-game-statistics" aria-label="إحصاءات الألعاب" ${playedGames.length ? '' : 'hidden'}>
      <header class="sd-detail-heading"><h3>رحلتي في الألعاب</h3><button class="sd-profile-full" type="button" aria-expanded="false">عرض التفاصيل</button></header>
      ${playedGames.map(([id, name, mark]) => {
        const s = stats.find(x => x.gameId === id);
        if (!s) return `<article class="sd-rank-row"><img class="sd-game-logo" src="/room-sprites/${mark}.png" alt=""><div><h4>${name}</h4><p class="sd-history-note">السجل غير متاح حاليًا</p></div></article>`;
        const level = Math.max(1, Math.min(100, number(s.level)));
        const progress = Math.max(0, Math.min(1, Number(s.progress) || 0));
        return `<article class="sd-rank-row" data-game="${id}"><div class="sd-game-emblem"><img class="sd-game-logo" src="/room-sprites/${mark}.png" alt="">${rankMarkup(level)}</div>
          <div class="sd-rank-info"><div class="sd-rank-title"><h4>${name}</h4><span>المستوى ${count(level)}</span></div>
          <div class="sd-rank-progress" role="progressbar" aria-label="تقدم مستوى ${name}" aria-valuemin="0" aria-valuemax="100" aria-valuenow="${Math.round(progress * 100)}"><span style="width:${progress * 100}%"></span></div><div class="sd-rank-label"><strong>${count(s.played)} لعب · ${count(s.wins)} فوز</strong><span>${esc(s.rankName || '')}</span></div>
          <div class="sd-rank-expanded" hidden><p>${level === 100 ? 'وصلت إلى قمة المستويات' : `${count(s.winsToNextLevel)} فوز للوصول إلى المستوى ${count(level + 1)}`}</p><div class="sd-match-numbers"><span>لعب <b>${count(s.played)}</b></span><span>خسر <b>${count(s.losses)}</b></span><span>تعادل <b>${count(s.draws)}</b></span></div></div></div></article>`;
      }).join('')}
      <p class="sd-history-note" data-history hidden>يُحتسب التقدم من نتائج المباريات المسجلة لكل لعبة.${number(user.legacyWins) ? ` يوجد ${count(user.legacyWins)} فوز سابق في الإجمالي دون تفاصيل حسب اللعبة.` : ''} نجوم الرتب تُكتسب بالفوز، وهي مستقلة عن زينة النجوم المشتراة.</p></section>`;
    const grid = root.querySelector('.sd-collection-grid');
    const filter = root.querySelector('select');
    const more = root.querySelector('.sd-collection-more');
    const dialog = root.querySelector('.sd-item-detail');
    let previousFocus = null;
    function closeDetail() { dialog.hidden = true; previousFocus?.focus(); }
    function drawItems() {
      const selected = expanded && filter.value !== 'all' ? items.filter(x => (x.gameId || 'profile') === filter.value) : items;
      grid.replaceChildren();
      for (const item of expanded ? selected : selected.slice(0, 3)) {
        const button = document.createElement('button');
        button.type = 'button'; button.className = 'sd-owned-card';
        button.innerHTML = `${asset(item.asset) ? window.SamiDevStickerArt.markup(asset(item.asset)) : '<span class="sd-owned-symbol" aria-hidden="true">✦</span>'}<strong>${esc(item.name)}</strong><small>×${count(item.quantity || 1)}</small>`;
        button.setAttribute('aria-label', `${item.name}، العدد ${number(item.quantity || 1)}، عرض التفاصيل`);
        button.onclick = () => {
          previousFocus = button;
          const image=dialog.querySelector('.sd-item-art');image.innerHTML=window.SamiDevStickerArt.markup(asset(item.asset));
          dialog.querySelector('h4').textContent = item.name;
          dialog.querySelector('p').textContent = `العدد: ${count(item.quantity || 1)}`;
          dialog.hidden = false; dialog.querySelector('button').focus();
        };
        grid.appendChild(button);
      }
      const empty = root.querySelector('.sd-collection-empty');
      empty.hidden = selected.length > 0;
      if (items.length && !selected.length) empty.textContent = 'لا توجد مقتنيات في هذه الفئة.';
    }
    more.onclick = () => {
      expanded = !expanded;
      more.setAttribute('aria-expanded', String(expanded));
      more.textContent = expanded ? 'عرض العيّنة' : `تصفّح كل المقتنيات (${count(total)})`;
      root.querySelector('.sd-collection-controls').hidden = !expanded;
      drawItems();
    };
    filter.onchange = drawItems;
    dialog.querySelector('button').onclick = closeDetail;
    dialog.onkeydown = event => {
      if (event.key === 'Escape') { event.preventDefault(); event.stopPropagation(); closeDetail(); }
      if (event.key === 'Tab') { event.preventDefault(); dialog.querySelector('button').focus(); }
    };
    root.querySelector('.sd-profile-full').onclick = event => {
      full = !full;
      event.currentTarget.textContent = full ? 'عرض مختصر' : 'عرض التفاصيل';
      event.currentTarget.setAttribute('aria-expanded', String(full));
      root.querySelectorAll('.sd-rank-expanded, [data-history]').forEach(x => { x.hidden = !full; });
    };
    drawItems();
  }
  window.SamiDevProfileDetails = {render, rankMarkup, reputationTier, flameMarkup, renderReputation};
})();
