# Pool table — mahogany V4

**مراجعة مرفوضة بصرياً من المستخدم، واستبدلت بـ `../pool-reference-v5/`. لقطة الهاتف في هذا المجلد لا تمثل تحققاً ناجحاً؛ لا تعتمدها كدليل قبول.**

تغيير خامة الطاولة إلى خشب أحمر، قماش أخضر وحواف معدنية هادئة، بالاستناد إلى صور المستخدم. التغيير خاص بالطاولة ومعاينتها في المتجر.

## عقد الأصول المحفوظ

- `table.webp`: ربع طاولة **433 × 773**، WebP lossless مع شفافية خارجية.
- المحرك يجمعه بالانعكاس أربع مرات. لم نضف رسماً بديلاً فوق الطاولة أو طبقة DOM للطاولة.
- نفس قناع الشفافية السابق، ونفس إحداثيات القص والجيوب والحواف في المحرك.
- أطلس `images/ui/ui.webp` ومواضع سبرايتاته لم تتغير. كذلك الكرات والعصا ونقاط التوجيه الأصلية.
- نُقلت رسمة المصدر إلى الإحداثيات الحالية أثناء تجهيز السبرايت؛ `build.cjs` يسجل التحويل في `build-report.json`.
- تمت إزالة نقاط الزينة من الخشب المولد لأن اللعبة ترسم نقاط التوجيه من أصلها المستقل؛ حتى لا تظهر مجموعتان.
- نسخة المتجر الافتراضية `pool-midnight.webp` تطابق الأصل الافتراضي؛ الثيم البديل `pool-emerald.webp` لم يتغير.
- نسخ الأصول السابقة في `backup/`، وبصمات المحرك والأطلس قبل التغيير في `before.json`.

## الملفات المثبتة

1. `game/games/pool/images/imported/themes/th_basic_table.webp`
2. `game/games/pool/images/imported/themes/th_basic_preview.webp`
3. `game/images/themes/pool-midnight.webp`
4. `game/images/themes/pool-midnight-preview.webp`

تغير رمز إصدار صور البلياردو في `browser-runtime.js` فقط، ثم أعيد بناء بيانات سلامة الأصول والكاش ونسخة Flutter المضمّنة.

## التوليد والمصدر

الأداة: **built-in image_gen**، وليس CLI أو API خارجي. المصدر النهائي محفوظ في `table-generated.png`، والنسخة المجهزة للمحرك في `table.webp`. تستخدم الصور المرفقة من المستخدم كمرجع للمظهر؛ لا يتضمن هذا التوثيق ادعاء حصرية الشكل المرجعي.

الأمر التصميمي الأساسي: إنتاج ربع الطاولة الحالي مع الحفاظ على مواضع الحواف والجيب الركني ونصف الجيب الجانبي وحدود الانعكاس. الخامات المطلوبة: خشب mahogany أحمر هادئ، معدن champagne/olive مطفأ، وقماش emerald أخضر ناعم. لا كرات أو عصا أو شات أو نص أو عناصر واجهة داخل الخامة.

نص التصحيح المستخدم للجيوب والمعدن:

> Precise-object-edit of this quarter-table sprite. Keep every pixel's geometric position and the entire composition, aspect ratio, cushion shapes, wood panels, mirror seams and transparent OUTSIDE margins. Two corrections only: (1) The TOP-LEFT POCKET interior and BOTTOM-LEFT HALF-POCKET interior must be uniform, fully opaque almost-black (#020706), without transparency, gray speckling, green contamination, checkerboard, glossy rings or halos. Make the mouth and hole edges crisp and clean at the exact existing opening. Transparency belongs ONLY outside the outer table silhouette, NEVER in the pockets. (2) Tone down the corner metal material to understated matte champagne/olive brass, with broad soft shading and no blazing white highlights. Retain the mahogany red wood and smooth emerald green felt. Preserve the quarter-sprite geometry exactly; do not add any right or bottom borders, lettering, balls, cues, UI or additional objects. Deliver the one clean production quarter sprite, transparent exterior.

نص التعديل النهائي المستخدم لإزالة النقاط المكررة:

> Precise-object-edit: Edit this production quarter-table sprite with minimal changes. REMOVE EXACTLY the three round gold rail sights/medallions embedded in this bitmap: one centered near (631,92), one near (95,562), and one near (95,1120), on the 938x1677 input image. Replace each removed tiny round spot with uninterrupted matching mahogany wood grain and identical local lighting. The running game draws its own rail sights separately, so there must be ZERO circular markers anywhere in the wood rails in this bitmap. Preserve EVERY other feature: exact 938x1677 dimensions and aspect ratio, composition, all rail edges and widths, cushions and cloth texture, red mahogany material, matte champagne metal corners, the top-left black pocket, lower-left black pocket, and all existing transparency outside the table. Do not move or resize the table. Do not add anything. Do not modify any geometry or any surface away from those three tiny removed circles. Output the same transparent quarter sprite with those three wood-rail circles removed.

## المراجعة

المعاينات `table-landscape.png` و`table-portrait.png` تجمع الأصل نفسه بالانعكاس؛ لقطات `game-desktop.png` و`game-phone.png` من اللعبة الفعلية. مراجعة الهاتف بمحاكاة شاشة 390 × 844 مع اللمس، وليست اختبار جهاز هاتف حقيقي.

اختبار `tests/pool_runtime.js`: 39 تحققاً لقواعد اللعبة والفيزياء ودخول الجيوب. اختبار `tests/asset_cache_build.py`: بناء كاش قابل لإعادة الإنتاج. بصمات الملفات المحمية وقياسات الأصل ومقارنة قناع ألفا محفوظة في `verification.json`.
