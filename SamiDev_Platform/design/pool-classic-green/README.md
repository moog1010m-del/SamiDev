# Classic green pool table — 2026-10-21

Table material change only. The engine mirrors the existing 433×773 quarter sprite. The runtime path, alpha pixels, silhouette, near-black pocket pixels, and dimensions are preserved. No engine, physics, rules, balls, cue, chat, aiming, or layout source was changed for this work.

Original backup: `original-quarter.webp`. Generated material: `generated-material.png`. Fitted replacement: `classic-green-quarter.webp`. `before.png` and `after.png` show the mirrored table; `live-game.png` is the actual public web game after integration. `validation.json` records geometry checks and unchanged protected source fingerprints.

Built-in imagegen prompt: edit the original top-left quarter texture only; deep emerald felt, dark reddish mahogany, restrained warm brass; preserve orthographic framing, rail widths, corner/side pocket positions, original transparency and right/bottom mirror seams; no balls, cue, text, branding or additional objects. Generated materials were fitted with `pack.cjs`, retaining original material boundaries, shading, alpha and dark pocket pixels.

Applied to `game/games/pool/images/imported/themes/th_basic_table.webp`; resource SHA-1, asset inventory SHA-256, service-worker cache and deployment inventory refreshed. Synchronized to Flutter runtime assets. The already-uploaded Play version 1.0.5 (6) is unchanged; no new store upload was performed.

Validation: 39 pool runtime checks passed; public asset cache contract passed; image dimensions/alpha/pocket-pixel checks passed; protected main.js/browser-runtime.js/pool-presentation.js fingerprints unchanged; actual web game rendered the replacement. The older whole-project `tests/original_assets.py` still fails because 11 unrelated existing assets are missing from its inventory. Windows path and newline handling in the two asset checks was normalized; assertions were retained.
