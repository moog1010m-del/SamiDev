# Pool reference V5

تصحيح النسخة V4 المرفوضة بصرياً. المرجع الحالي هو `reference.png` الذي أرسله المستخدم، والطاولة وحدها هي نطاق التعديل.

التغييرات المرئية: جيوب دائرية بحافة رمادية رفيعة، قطع معدنية أصغر بلون زيتوني مطفأ، خشب أحمر أقل لمعاناً، وسائد خضراء أعرض وأبسط، وقماش أخضر ناعم بإضاءة وسطية خفيفة. الرسمة إعادة بناء من المرجع وليست ادعاء تطابق بكسلي.

## طريقة الأصول

- `table.webp`: ربع طاولة **433 × 773** بصيغة WebP lossless. نفس مسار الأصل القديم، ونفس الانعكاس إلى أربعة أرباع داخل المحرك.
- قناع ألفا الأصلي محفوظ، وكذلك حدود القماش داخل السبرايت ومقاسه ونقطتا انعكاسه.
- ملفات المحرك الأربعة و`pool-presentation.js` و`pool-result-card.js` وأطلس الواجهة **لم تتغير**. المقارنة ببصمات SHA-256 في `verification.json`.
- الجيوب والحواف أعيد رسم مظهرها؛ أجسام التصادم وقواعد الكرة لم تتغير.
- نقاط الحواف داخل الرسم المولد أزيلت لتظهر مجموعة نقاط المحرك الأصلية وحدها. لم نغير سبرايت النقطة أو موقعه في الأطلس.
- الأصل البديل `pool-emerald.webp` محفوظ؛ هذا التغيير للثيم الافتراضي ومعاينته فقط.
- `build.cjs` ينقل خامة المصدر إلى إحداثيات ربع السبرايت الحالي ويعيد إنتاجه. `--install` ينسخ الملفات الأربعة للطاولة ومعايناتها ويرفع رمز إصدار الصورة.
- `backup/` يحتوي الأصول السابقة؛ لا يستعمل البناء ألوانها أو تفاصيلها، وإنما قناع ألفا فقط.

الملفات المثبتة:

1. `game/games/pool/images/imported/themes/th_basic_table.webp`
2. `game/games/pool/images/imported/themes/th_basic_preview.webp`
3. `game/images/themes/pool-midnight.webp`
4. `game/images/themes/pool-midnight-preview.webp`

## مصدر الصورة والأوامر

الأداة المستخدمة: **built-in image_gen**. لم يستخدم CLI. النتيجة الأصلية `table-generated.png` محفوظة داخل المشروع، والأصل المجهز للمحرك `table.webp`.

المرجع من المستخدم، وليس إثبات ملكية أو حصرية فنية. هذه المراجعة لا تغير ترخيص المحرك.

أمر إعادة البناء:

> Precise-object-edit of the supplied reference screenshot. The user specifically rejects a reinterpreted ornate table. Reconstruct ONLY THIS EXACT SIMPLE TABLE design as a clean empty production game asset, preserving its proportions and visual appearance. Remove all 16 billiard balls, the white aiming/move control near the lower middle, browser toolbar, surrounding purple background, and any UI. Fill their former locations with the same perfectly smooth, softly illuminated green cloth. Preserve the table's original slim red-brown wooden rails, small subtle gold sights, narrow dull olive-champagne metal end caps, thin double outer rim, simple straight pale-green cushions with shallow bevels, and SIX perfectly ROUND black circular pocket openings. The black pockets are round circles with a subtle grey rim, NEVER diagonal teardrops and NEVER large angular black corner cutouts. Metal must remain muted olive grey, NOT bright gold or polished brass. Felt must be almost textureless with the original soft central green glow, not mottled fabric, not grainy, not crosshatched. Wood must be restrained dark red, almost smooth, not glossy streaky mahogany. Keep exact orthographic flat top-down view, elongated portrait aspect ratio, and identical rail thickness and corner proportions to the provided image. This is a cleanup of the reference, NOT a redesign. Render the complete portrait table alone, tightly framed, with genuinely transparent exterior margins. No letters, branding, balls, cue, control arrows, shadows beyond a small soft table-edge shadow, or other objects. Preserve the existing pocket locations, circular shapes and cushion geometry in this reference.

أمر إزالة النقاط المكررة:

> Precise-object-edit. Remove ONLY the tiny round gold rail sight dots from this empty billiards table. There are three on the top horizontal wood rail, three on the bottom horizontal wood rail, four on the left vertical wood rail and four on the right vertical wood rail. Fill each of those fourteen tiny dots with the exact surrounding smooth dark red wood color and shading. Leave EVERY other pixel and feature visually unchanged: the exact same table dimensions, slim red rails, perfectly circular black pockets and thin rims, small muted olive-grey metal caps, wide shallow green cushions, very smooth green felt and gentle central glow, transparency, framing and proportions. Do not alter any pocket, corner, cushion, rail outline, felt lighting, color palette or geometry. This bitmap will use the game's existing independent sight-dot sprite, so it must contain no embedded rail dots. Keep the transparent exterior. No balls, cues, controls, lettering or UI.

## التحقق

`verification.json` يسجل بصمات المحرك والأطلس وقياسات الصورة وقناع ألفا. `table-portrait.png` و`table-landscape.png` معاينتان لتجميع الأرباع من الأصل المثبت نفسه.

لقطات `game-phone.png` و`game-desktop.png` من اللعبة الفعلية بعد تركيب الأصل. العرض الطولي روجع بمحاكاة شاشة 390 × 844 مع اللمس داخل المتصفح، وليس جهاز هاتف حقيقياً. نجح اختبار قواعد البلياردو (39 تحققاً) واختبار بناء كاش الأصول، ونسخت 759 ملفات إلى Flutter دون نتائج مخالفة.

بقي حجم الكرات كما هو بناءً على طلب المستخدم المشروط؛ تصغير الرسم وحده يفصل الحجم المرئي عن حدود التصادم، ولم يغيّر هذا العمل نصف قطر الفيزياء.
