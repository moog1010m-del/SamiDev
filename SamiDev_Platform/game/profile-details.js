(() => {
  'use strict';
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const number = v => Math.max(0, Math.floor(Number(v) || 0));
  const count = v => number(v).toLocaleString('ar-SA');
  const asset = v => window.SamiDevStickerArt?.cell(v)!==null && window.SamiDevStickerArt?.cell(v)!==undefined ? String(v) : /^\/(?:images|games|platform\/assets|room-sprites)\/[A-Za-z0-9_./-]+$/.test(String(v)) && !String(v).includes('..') ? String(v) : '';
  const games = [['pool','البلياردو','pool'],['carrom','الكيرم','carrom'],['tablesoccer','كرة الطاولة','football'],['crazy8','أونو','cards']];

  function render(root, user, {own = false} = {}) {
    if (!root) return;
    const items = (Array.isArray(user.showcaseItems) ? user.showcaseItems : []).filter(x => x && x.id && number(x.quantity || 1));
    const stats = Array.isArray(user.gameStatistics) ? user.gameStatistics : [];
    const total = items.reduce((sum, x) => sum + number(x.quantity || 1), 0);
    let expanded = false, full = false;
    root.classList.add('sd-profile-details');
    root.setAttribute('dir', 'rtl');
    root.innerHTML = `<section class="sd-collection-section" aria-label="المقتنيات">
      <header class="sd-detail-heading"><h3>${own ? 'مقتنياتي' : 'مقتنيات اللاعب'}</h3><span>${count(total)} قطعة</span></header>
      <div class="sd-collection-controls" hidden><label>تصفّح حسب اللعبة <select aria-label="تصفية المقتنيات"><option value="all">كل المقتنيات</option><option value="profile">زينة الملف</option>${games.map(([id, name]) => `<option value="${id}">${name}</option>`).join('')}</select></label></div>
      <div class="sd-collection-grid"></div>
      <p class="sd-collection-empty" ${items.length ? 'hidden' : ''}>${own ? 'ستظهر هنا المقتنيات التي تجمعها أو تشتريها.' : 'لا توجد مقتنيات مملوكة للعرض بعد.'}</p>
      <button class="sd-collection-more" type="button" aria-expanded="false" ${items.length ? '' : 'hidden'}>تصفّح كل المقتنيات (${count(total)})</button>
      <div class="sd-item-detail" role="dialog" aria-modal="true" aria-label="تفاصيل المقتنى" hidden><button class="sd-item-close" type="button" aria-label="إغلاق تفاصيل المقتنى">×</button><div class="sd-item-art"></div><h4></h4><p></p></div>
      </section><section class="sd-game-statistics" aria-label="إحصاءات الألعاب">
      <header class="sd-detail-heading"><h3>رحلتي في الألعاب</h3><button class="sd-profile-full" type="button" aria-expanded="false">عرض التفاصيل</button></header>
      ${games.map(([id, name, mark]) => {
        const s = stats.find(x => x.gameId === id);
        if (!s) return `<article class="sd-rank-row"><img class="sd-game-logo" src="/room-sprites/${mark}.png" alt=""><div><h4>${name}</h4><p class="sd-history-note">السجل غير متاح حاليًا</p></div></article>`;
        const level = Math.max(1, Math.min(100, number(s.level)));
        const progress = Math.max(0, Math.min(1, Number(s.progress) || 0));
        return `<article class="sd-rank-row" data-game="${id}"><div class="sd-game-emblem"><img class="sd-game-logo" src="/room-sprites/${mark}.png" alt=""><span class="sd-rank-star" data-tier="${Math.floor((level-1)/10)}" role="img" aria-label="المستوى ${level}"><b>${level}</b></span></div>
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
  window.SamiDevProfileDetails = {render};
})();
