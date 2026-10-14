/* Shared Game Pool presentation, embedded by tools/apply_pool_pocketed_layout.py. */
globalThis.SamiDevPoolPocketedLayout = Object.freeze({
  items(scene) {
    const seen = new Set();
    // The eight-ball scene has two indicators for rank 8 (one per group).
    // Game Pool has a single collection of all numbered balls.
    return scene.gapBalls.filter(item => {
      const rank = item.getRank();
      if (seen.has(rank)) return false;
      seen.add(rank);
      return scene.logic.table.isBallPocketed(rank);
    }).sort((a, b) => a.getRank() - b.getRank());
  },
  updateVisibility(scene) {
    if (!scene.logic.freePool) return false;
    const visible = new Set(scene.isShowPocketed() ? this.items(scene) : []);
    for (const item of scene.gapBalls) item.visible = visible.has(item);
    return true;
  },
  updatePositions(scene) {
    if (!scene.logic.freePool) return false;
    const slots = scene.layoutInfo.cbGapsPos;
    const side = scene.logic.isLocalTeamTurn() ? 7 : 0;
    const anchor = slots[side];
    if (!anchor || !scene.isShowPocketed()) return true;
    const items = this.items(scene);
    const diameter = Math.max(1, ...items.map(item => Math.max(item.width, item.height)));
    const spacing = Math.max(diameter * 1.15, Math.abs((slots[side + 1]?.[1] ?? anchor[1]) - anchor[1]));
    const sideWidth = 2 * Math.min(anchor[0], scene.layoutInfo.logW - anchor[0]);
    const columns = items.length > 8 ? 2 : 1;
    // Keep long collections above the aiming controls, including narrow phones.
    const scale = Math.min(1, Math.max(1, sideWidth - 8) / ((columns - 1) * spacing + diameter));
    const rows = Math.ceil(items.length / columns);
    for (let index = 0; index < items.length; index++) {
      const column = Math.floor(index / rows), row = index % rows;
      // Derive positions below the heading instead of indexing the native
      // seven-slot group: its first slot is the heading, leaving only six balls.
      items[index].scale = scale;
      items[index].position(anchor[0] + (column - (columns - 1) / 2) * spacing * scale,
        anchor[1] + (row + 1) * spacing * scale);
    }
    return true;
  },
});
/* End SamiDev pool pocketed layout. */
