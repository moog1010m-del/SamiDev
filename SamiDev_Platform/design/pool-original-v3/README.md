# Independent raster pool artwork V3 — 2026-10-21

Runtime output is lossless **WebP**, not SVG. Neither generation request used any reference image, previous sprite, screenshot or vendor artwork. The two built-in imagegen outputs are `table-generated.png` and `controls-generated.png`. `build.cjs` crops the newly generated controls and authors simple raster symbols/ball UV labels through a native bitmap canvas. It creates a blank atlas, never composites the previous atlas. Only the numeric sprite names/rectangles are reused for compatibility. The table silhouette and pocket circles are authored numerically, without copying an old alpha mask.

Art direction: graphite, brushed titanium, fine copper accents, jade cloth and teal controls. Generated assets: table quarter; spin selector, power meter, cue, spin reticle, fine-aim paddle, hand pointer, loading spinner, play control. Authored raster components: ball UV labels 0–15, shadows, markers, replay icons, eye icons, timer and small symbols. No SVG is created or rendered.

Technical contract: quarter 433×773, mirrored by the engine; 46 named atlas regions at their unchanged offsets in a 1343×625 atlas. Cue/background/thumbnail sizes match their existing slots. Engine, physics, touch handling and rules are unchanged; `engine-before.json` records source fingerprints. Eight installed paths and SHA-256 values are in `installed.json`; rollback backups are under `backup/`.

Generation prompt set:

1. Original overhead quarter-table sprite, no reference. Logical canvas 433×773; top/left rails only; rounded top-left silhouette; cloth boundary near 91,91; corner pocket center near 83,84; half-side-pocket near 60,773; right/bottom reflection seams; graphite stepped frame, titanium hardware, copper stripe, jade cloth. No UI, balls, lettering, wood or gold plating. Transparent exterior.
2. Original raster billiards control kit, no reference. 1536×1024 canvas, eight isolated assets: ivory/titanium spin selector with teal ticks; horizontal coral–amber–teal power meter; graphite/maple cue with tip right; amber spin-target reticle; fine-aim paddle; ivory hand pointer; titanium/teal spinner; teal play button. Transparent background, no labels or logos. The generated kit is cropped and fitted into original numeric UV rectangles.

Validation: source fingerprints unchanged; 39 pool runtime checks and asset-cache contract passed. Geometry/atlas region bounds and shared web/Flutter bytes checked. Public Play version 1.0.5 (6) is unchanged; no store upload in this task. This asset work does not relicense unrelated code, sound, avatar, shop or animation assets.
