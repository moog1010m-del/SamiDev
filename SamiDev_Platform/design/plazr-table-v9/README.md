# Plazr graphite table — V9

The user clarified that the default table should be a completely new Plazr design with the name engraved on the frame. The saved optional large-table mode from V8 stays independent and unchanged.

## Original sources

Both sources were generated from text only with the built-in `image_gen` tool, without an external image reference. Exact prompts are in `prompts.json`.

- `quarter-generated.png`: fresh satin graphite, champagne pinstripe, petroleum-teal rubber and blue-green cloth. Generated alpha retained through atlas resampling and an independently authored native silhouette mask.
- `engraving-generated.png`: newly generated intaglio «Plazr» inlay, packed into `engraving.webp`.
- `table.webp`: production 433 × 773 quarter, mirrored by the existing native engine. `build.cjs` resamples only the new generated material into the existing technical geometry. It does not read a previous table image or alpha mask.
- The wordmark is a separate raster inlay because text baked into a mirrored quarter would become reversed. `pool-brand-mark.js` binds it to the actual frame coordinates and caches a small canvas, without touching native bodies, drawing routines or input.
- The native background tiles, so the new background is a flat matte procedural color, without a repeated vignette pattern.

## Integration

The new table/background/preview assets replace the default only. The UI/ball atlas, native `main.js`, ball size, collision geometry, shots, native sink animation and existing pocket VFX are unchanged. All eight saved large-mode files under `game/images/pool-large/` retain their exact V8 hashes. Branding is hidden for that mode.

Native geometry remains 834 × 1516 with its 433 × 773 quarter texture and 16/15 px padding. Cushions are fitted to the existing rail vertices; `corner-contact-review.png` overlays the actual native contact boundary for visual review. The renderer still owns ball shading and pocket handling.

Backups are under `backup/`. No Google Play binary was uploaded. Runtime assets are synchronized to the Flutter source bundle.

## Verification

See `asset-verification.json` for native engine, UI atlas and saved large-mode hashes, and `verification.json` for build/runtime checks. Actual desktop and phone renders are saved under `proof/`. Temporary phone emulation is cleared after testing.
