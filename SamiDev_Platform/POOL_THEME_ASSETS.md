# Pool table assets

Built-in image generation/editing created the midnight and emerald table textures. The edit target was the original top-left quarter texture. Prompt constraints: preserve orthographic framing, rail widths, circular top-left pocket, half pocket at the bottom-left, no rails at the right/bottom mirror seams, no balls, cues, text or logos. New materials: dark walnut, champagne brass, petroleum-blue / emerald felt.

Generated images were fitted to 433×773. The original alpha and near-black pocket mask were retained so the replacement does not change geometry. This does not imply that every pixel is newly generated. The engine still mirrors the quarter texture and uses its unchanged ball atlas.

Runtime paths:
- game/games/pool/images/imported/themes/th_basic_table.webp (midnight default)
- game/images/themes/pool-midnight.webp
- game/images/themes/pool-emerald.webp
- game/images/themes/pool-midnight-preview.webp
- game/images/themes/pool-emerald-preview.webp

`POOL_ORIGINAL_ASSETS.json` records the 18 unchanged images and the replaced table separately. No exclusive legal ownership guarantee is attached to generated or previously supplied assets.
