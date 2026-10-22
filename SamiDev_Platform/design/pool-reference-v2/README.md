# Reference table v2

Built-in imagegen produced new artwork, using the original quarter only as a geometry template and the user's first screenshot as style reference. Prompt: classic red mahogany rails, dark green cloth, narrow antique-brass trim, redesigned angular corner joinery and side-pocket trim; orthographic overhead quarter only; keep original rail widths, black pocket positions, silhouette and mirror seams; no UI, balls, cue, letters or branding.

`pack.cjs` fits the generated RGBA into the original 433×773 sprite. Unlike v1, every visible non-pocket pixel uses the generated artwork at full strength, not a blend with original artwork. Original alpha and near-black pocket pixels remain exact. Small generated transparent/black edge drift outside the original geometry mask is filled from neighboring generated material.

Files: `original-quarter.webp` is the backup geometry template, `generated-material.png` is the generated source, `reference-quarter.webp` is the installed asset, `before.png` / `after.png` are mirrored previews, `validation.json` records source fingerprints and asset hashes.

Installed at `game/games/pool/images/imported/themes/th_basic_table.webp`. Existing sprite key, dimensions, scene geometry, engine, physics and rules are unchanged. Updated asset/cache/deployment inventories and synchronized Flutter bundled assets. No Google Play upload in this task.

Verification: exact alpha/pocket-pixel checks; 39 pool runtime checks; asset-cache contract test; protected main.js/browser-runtime.js/pool-presentation.js hashes unchanged.

The equipped `pool_emerald` theme uses a separate shared image, `/images/themes/pool-emerald.webp`; the earlier v1 only changed the basic texture, so emerald players still saw the old table. V2 also replaces this shared quarter and its existing 224×400 thumbnail. `original-emerald-quarter.webp` and `original-emerald-preview.webp` preserve backups; `emerald-validation.json` confirms the original emerald alpha and near-black pocket pixels are exact. `emerald-after.png` is its mirrored preview. No equipment lookup or engine code was modified.
