/* Desktop-only presentation. Physics bodies and network packets keep native axes. */
(() => {
  "use strict";
  function create({canvas: canvas, mobileDevice: mobileDevice, native: native = false, portrait: portrait = false}) {
    let scene = null, context = null, enabled = false, geometry = null, backgroundDirty = true;
    const routes = new Map, wrapped = new WeakSet;
    const api = {
      get enabled() {
        return enabled;
      },
      get geometry() {
        return geometry;
      },
      forward: forward,
      inverse: inverse,
      beforeFrame: beforeFrame,
      mapPointer: mapPointer,
      endPointer: id => routes.delete(id)
    };
    function forward(p) {
      if (!enabled) return {
        ...p
      };
      const g = geometry;
      return {
        x: g.cx + g.scale * (p.y - g.sy),
        y: g.cy - g.scale * (p.x - g.sx)
      };
    }
    function inverse(p) {
      if (!enabled) return {
        ...p
      };
      const g = geometry;
      return {
        x: g.sx - (p.y - g.cy) / g.scale,
        y: g.sy + (p.x - g.cx) / g.scale
      };
    }
    function matrix(m, out = new Float32Array(9)) {
      const g = geometry, s = g.scale, tx = g.cx - s * g.sy, ty = g.cy + s * g.sx;
      for (let c = 0; c < 3; c++) {
        out[c] = s * m[3 + c] + tx * m[6 + c];
        out[3 + c] = -s * m[c] + ty * m[6 + c];
        out[6 + c] = m[6 + c];
      }
      return out;
    }
    function transformRender(node) {
      if (!node || wrapped.has(node) || typeof node.render !== "function") return;
      wrapped.add(node);
      const original = node.render;
      node.render = function(ctx) {
        if (!enabled) return original.apply(this, arguments);
        const set = ctx.setTransform, saved = new Float32Array(9), projected = new Float32Array(9);
        ctx.currentMatrix(saved);
        ctx.setTransform = function(m) {
          return set.call(this, matrix(m, projected));
        };
        try {
          return original.apply(this, arguments);
        } finally {
          ctx.setTransform = set;
          set.call(ctx, saved);
        }
      };
    }
    function install(s) {
      scene = s;
      context = null;
      backgroundDirty = true;
      for (const key of [ "table", "cueStick", "vbLayer", "animEffectsMgr", "debugTable" ]) transformRender(s[key]);
      const left = [ "powerMeter", "premiumBtn", "premiumLabel", "newText" ], right = [ "angleBtnL", "angleBtnR", "angleText", "spinBtn", "aimLineBtn", "aimLineBtnPulse" ];
      for (const key of [ ...left, ...right ]) {
        const animator = s[key]?.animator;
        if (!animator?.updatePositions) continue;
        const update = animator.updatePositions;
        animator.updatePositions = function(x, hiddenX, y) {
          return update.call(this, enabled ? left.includes(key) ? 105 : s.layoutInfo.logW - 125 : x, hiddenX, y);
        };
      }
      const layout = s.updateLayout;
      s.updateLayout = function(info) {
        const result = layout.apply(this, arguments);
        if (enabled) {
          for (const key of left) if (this[key] && !this[key].animator) this[key].x = 105;
          for (const key of right) if (this[key] && !this[key].animator) this[key].x = info.logW - 125;
        }
        return result;
      };
      const slots = s.updateCBGapsPos;
      s.updateCBGapsPos = function() {
        const result = slots.apply(this, arguments);
        if (enabled) {
          const positions = this.layoutInfo.cbGapsPos, step = 54;
          for (let i = 0; i < positions.length; i++) {
            const half = positions.length === 14 ? i < 7 ? 0 : 1 : 0, count = positions.length === 14 ? 7 : positions.length, index = positions.length === 14 ? i % 7 : i;
            positions[i] = [ this.layoutInfo.logW * (positions.length === 14 ? half ? .7 : .3 : .5) + (index - (count - 1) / 2) * step, this.layoutInfo.logH - 95 ];
          }
        }
        return result;
      };
      const updateBalls = s.updateGapBallsPos;
      s.updateGapBallsPos = function() {
        const result = updateBalls.apply(this, arguments);
        if (enabled) layoutFreeBalls(this);
        return result;
      };
      const updateHeading = s.updatePocketedPos;
      s.updatePocketedPos = function() {
        const result = updateHeading.apply(this, arguments);
        if (enabled && this.logic.freePool && this.pocketed) this.pocketed.position(this.layoutInfo.logW * (this.logic.isLocalTeamTurn() ? .74 : .26), this.layoutInfo.logH - 180);
        return result;
      };
      const bg = s.bgnd, create = bg.createSprite, render = bg.render;
      bg.createSprite = function() {
        if (!enabled || !context) return create.apply(this, arguments);
        const ctx = context, draw = ctx.drawTexture;
        ctx.drawTexture = function(sprite) {
          if (sprite !== s.table.sprite) return draw.apply(this, arguments);
          const saved = new Float32Array(9);
          ctx.currentMatrix(saved);
          ctx.setTransform(matrix(saved));
          try {
            return draw.apply(this, arguments);
          } finally {
            ctx.setTransform(saved);
          }
        };
        try {
          return create.apply(this, arguments);
        } finally {
          ctx.drawTexture = draw;
        }
      };
      bg.render = function(ctx) {
        context = ctx;
        if (backgroundDirty) {
          backgroundDirty = false;
          this.updateSprite(s.logic.activeTheme);
        }
        return render.apply(this, arguments);
      };
    }
    function layoutFreeBalls(s) {
      if (!s.logic.freePool) return;
      const items = [], ranks = new Set;
      for (const item of s.gapBalls) {
        if (item.visible && !ranks.has(item.rank)) {
          items.push(item);
          ranks.add(item.rank);
        }
      }
      const spacing = Math.max(54, ...items.map(item => item.width * 1.15)), cx = s.layoutInfo.logW * (s.logic.isLocalTeamTurn() ? .74 : .26), columns = Math.min(8, items.length);
      for (let i = 0; i < items.length; i++) {
        const row = Math.floor(i / columns), count = Math.min(columns, items.length - row * columns);
        items[i].scale = 1;
        items[i].position(cx + (i % columns - (count - 1) / 2) * spacing, s.layoutInfo.logH - 125 + row * 70);
      }
      if (s.pocketed) s.pocketed.position(cx, s.layoutInfo.logH - 180);
    }
    function beforeFrame(s) {
      if (!s?.table || !s.bgnd) return;
      const rect = canvas.getBoundingClientRect(), layout = s.layoutInfo;
      const next = !portrait && !mobileDevice && !native && rect.width >= 900 && rect.height >= 500 && rect.width >= rect.height * 1.05;
      // Leave the phone/native scene completely untouched until a desktop layout is needed.
      if (!next && !enabled) return;
      if (scene !== s) install(s);
      const sx = s.table.x, sy = s.table.y, w = s.table.width * s.table.scaleX, h = s.table.height * s.table.scaleY;
      const scale = Math.min((layout.logW - 420) / h, (layout.logH - 700) / w);
      const nextGeometry = {
        sx: sx,
        sy: sy,
        cx: layout.logW / 2,
        cy: (460 + layout.logH - 240) / 2,
        scale: scale,
        logScale: layout.logScale,
        width: h * scale,
        height: w * scale
      };
      if (enabled !== next || JSON.stringify(geometry) !== JSON.stringify(nextGeometry)) {
        enabled = next;
        geometry = nextGeometry;
        backgroundDirty = true;
        routes.clear();
        s.updateLayout(layout);
      }
      if (!enabled) return;
      layoutFreeBalls(s);
    }
    function mapPointer(p, {begin: begin = false} = {}) {
      if (!enabled || !geometry) return p;
      const g = geometry, logical = {
        x: p.x * g.logScale,
        y: p.y * g.logScale
      };
      const modal = scene.spinPanel?.visible || scene.gameOverPopup?.visible || scene.shopWidget?.visible || scene.settingsWidget?.visible;
      let use = routes.get(p.id);
      if (use === undefined) {
        use = !modal && Math.abs(logical.x - g.cx) <= g.width / 2 + 30 && Math.abs(logical.y - g.cy) <= g.height / 2 + 70;
        if (begin) routes.set(p.id, use);
      }
      if (!use) return p;
      const mapped = inverse(logical);
      return {
        ...p,
        x: mapped.x / g.logScale,
        y: mapped.y / g.logScale
      };
    }
    return api;
  }
  window.SamiDevPoolPresentation = {
    create: create
  };
})();
