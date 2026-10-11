(() => {
  'use strict';
  if (window.SamiDevGames.current().id !== 'crazy8') return;
  const clips = new Map(), active = new Set();
  let context, pendingDeal = false, dealt = false, syncing = true, bound;
  let warningKey = '', warningPending = false;
  const muted = () => document.hidden || window.__SAMIDEV_AUDIO_SUSPENDED || window.SamiDevGameUI?.isMuted?.();
  function play(name, delay = 0) {
    if (muted() || !context || context.state !== 'running' || !clips.has(name) || active.size >= 24) return false;
    const source = context.createBufferSource(), gain = context.createGain();
    source.buffer = clips.get(name); gain.gain.value = name === 'shuffle' ? .48 : .70;
    source.connect(gain); gain.connect(context.destination); active.add(source);
    source.onended = () => { active.delete(source); source.disconnect(); gain.disconnect(); };
    source.start(context.currentTime + delay); return true;
  }
  function draw(count) {
    // Short overlapping card recordings follow the native number drawn, including
    // automatic +2/+4 and stacked penalties. Bound extreme stacks to a short burst.
    for (let i = 0; i < Math.min(12, Math.max(0, count)); i++) play('draw', i * .085);
  }
  function shield() {
    // Two quiet strikes of a recorded CC0 bell; uses the same mute/lifecycle
    // controls as the card clips and never creates a synthesized oscillator.
    play('warning');
  }
  function checkWarning() {
    if (warningPending) return;
    warningPending = true;
    queueMicrotask(() => {
      warningPending = false;
      const g = bound, seat = g?.localSeat;
      const threatened = !syncing && !g?.gameOver && g?.crank > 0 && g?.turn?.[0] === seat && seat >= 0;
      const canDefend = threatened && g.hands?.[seat]?.some(card => g.canPlayCard(seat, card));
      const key = canDefend ? `${g._sequence?.join(',')}:${seat}:${g.crank}` : '';
      if (key && key !== warningKey) shield();
      warningKey = key;
    });
  }
  async function unlock() {
    try {
      if (!context) {
        context = new (window.AudioContext || window.webkitAudioContext)();
        for (const name of ['draw', 'place', 'special', 'shuffle', 'warning']) {
          fetch(`/games/crazy8/sounds/card-${name}.m4a?v=audio37`, {credentials:'same-origin'})
            .then(r => { if (!r.ok) throw Error('audio'); return r.arrayBuffer(); })
            .then(b => context.decodeAudioData(b)).then(b => { clips.set(name, b); if (name === 'shuffle' && pendingDeal && play(name)) pendingDeal = false; }).catch(() => {});
        }
      }
      await context.resume();
      if (pendingDeal && play('shuffle')) pendingDeal = false;
    } catch (_) {}
  }
  const net = window.SamiDevNetwork;
  net?.on('begin_match', () => { if (!dealt) { dealt = true; pendingDeal = !play('shuffle'); } });
  document.addEventListener('pointerdown', unlock, {capture:true, passive:true});
  document.addEventListener('keydown', unlock, {capture:true});
  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) return;
    for (const s of active) { try { s.stop(); } catch (_) {} }
    context?.suspend();
  });
  window.SamiDevCardAudio = {play, unlock, stop(){for(const s of active){try{s.stop();}catch(_){}}active.clear();}, setSyncing(value) { syncing = !!value; warningKey = ''; }, bindLocal(logic) {
    if (bound || !logic?.emitter) return;
    bound = logic;
    // Observe actual native effects once, including server alarm auto-moves.
    // revealDraw only replaces hidden values and must never play a second draw.
    logic.emitter.on('move', (kind, seat, data) => {
      if (syncing) return;
      if (kind === 'drawCards') draw(data);
      else if (kind === 'playCard') play([8,10,11,12,13,14,15,16].includes(data.source >> 2) ? 'special' : 'place');
      checkWarning();
    });
    logic.emitter.on('batchDraw', (seats, count) => { if (!syncing) draw(seats.length * count); });
    logic.emitter.on('turnChanged', checkWarning);
  }};
})();
