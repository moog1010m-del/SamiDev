/* Shared source, embedded into all four engines by tools/apply_v36_ui.py. */
globalThis.SamiDevAvatarLayout = Object.freeze({
  position(a) {
    const row = a.idContainer, badges = a.badgeContainer, name = a.nameText;
    const measure = a.nameTextMeasure, radius = a._imageRadius;
    const font = name.fontSize || 40, gap = Math.max(8, font * .22);
    const margin = Math.max(a.nameMargin || 0, font * .28);
    const rowBudget = Math.min(a.maxNameWidth > 0 ? a.maxNameWidth : Infinity, radius * 4.8);
    const rawBadgeWidth = badges.visible ? badges.width : 0;
    const badgeScale = rawBadgeWidth ? Math.min(1, rowBudget * .4 / rawBadgeWidth) : 1;
    badges.scaleX = badges.scaleY = badgeScale;
    const badgeWidth = rawBadgeWidth * badgeScale;
    const budget = Math.max(0, rowBudget - badgeWidth - (badgeWidth ? gap : 0));
    // Always measure the full name again: shrinking then growing the viewport
    // must restore characters, including Arabic and surrogate pairs.
    const full = String(a.oldNameTextContents || ''), chars = Array.from(full);
    measure.text = full; measure._update();
    if (measure.width > budget) {
      let low = 0, high = chars.length;
      while (low < high) {
        const mid = Math.ceil((low + high) / 2);
        measure.text = chars.slice(0, mid).join('') + '…'; measure._update();
        if (measure.width <= budget) low = mid; else high = mid - 1;
      }
      measure.text = chars.slice(0, low).join('') + '…'; measure._update();
      if (measure.width > budget) { measure.text = ''; measure._update(); }
    }
    name.text = measure.text;
    const height = Math.max(font * 1.35, (badges.height || 0) * badgeScale);
    row.resize(badgeWidth + (badgeWidth ? gap : 0) + measure.width, height);
    badges.anchorX = 0; badges.anchorY = 0;
    badges.position(0, (height - badges.height * badgeScale) / 2);
    name.anchorX = 0; name.anchorY = .5;
    name.position(badgeWidth + (badgeWidth ? gap : 0), height / 2);
    const pill = a.localTurnPill;
    switch (a.nameAlign) {
      case 'ABOVE':
        row.anchorX = .5; row.anchorY = 1; row.position(0, -radius - margin);
        pill.anchorX = .5; pill.anchorY = 1; pill.position(0, -radius - margin);
        break;
      case 'LEFT':
        row.anchorX = 1; row.anchorY = .5; row.position(-radius - margin, 0);
        pill.anchorX = 1; pill.anchorY = .5; pill.position(-radius - margin, 0);
        break;
      case 'RIGHT':
        row.anchorX = 0; row.anchorY = .5; row.position(radius + margin, 0);
        pill.anchorX = 0; pill.anchorY = .5; pill.position(radius + margin, 0);
        break;
      default:
        row.anchorX = .5; row.anchorY = 0; row.position(0, radius + margin);
        pill.anchorX = .5; pill.anchorY = 0; pill.position(0, radius + margin);
    }
    // Connection state belongs to the avatar, never to the measured name row.
    const dot = a._activeIndicator;
    const diameter = Math.max(12, Math.min(font * .4, radius * .30));
    dot.resize(diameter, diameter); dot.anchorX = dot.anchorY = .5;
    dot.position(radius * .68, radius * .55);
    this.owner(a);
  },
  owner(a) {
    a.checkOwnerBadgeVisibility();
    const crown = a.ownerIndicator;
    if (!crown) return;
    const radius = a._imageRadius, size = Math.max(22, Math.min(36, radius * .55));
    crown.resize(size, size); crown.anchorX = crown.anchorY = .5;
    crown.position(-radius * .62, -radius * .62);
  }
});
