# Middle pockets V6

تعديل الجيبين الوسطيين المتقابلين وفق مرجع المستخدم في `reference.png`، مع إبقاء بقية الطاولة والكرات والأطلس والمحرك كما هي.

سبب التمدد السابق: خط انعكاس ربع السبرايت كان يمر بعد مركز الجيب في صورة المصدر. كان القطر الأسود الظاهر بعد تجميع الأرباع 68 × 54 بكسل تقريباً. تم تصحيح مركز القص ونسبة السبرايت، مع إدراج حافة أرفع حول الدائرة.

## بناء الأصول

- الأصل النهائي `table.webp`: ربع طاولة 433 × 773، WebP lossless، ينعكس أربع مرات بالطريقة الحالية.
- المصدر الأساسي هو `../pool-reference-v5/table-generated.png`؛ تعديل القص محصور أسفل يسار الربع، حيث نصف الجيب الوسطي.
- `pocket-generated.png` تعديل محلي للحافة عبر **built-in image_gen**. `pocket-art.png` شريحة مجهزة منه للأصل الحالي.
- `pocket-crop-final.json` يحدد قص شريحة الجيب المولدة، وتضبط إلى مقاس 90 × 90 بكسل أثناء التجهيز.
- يعيد `build.cjs` ضبط مركز الانعكاس، ويطابق قطر الدائرة، ويطوي الشريحة إلى ربع السبرايت. إعادة أخذ عينات من الخامة المجاورة تزيل أثر الحافة القديمة قبل تركيب الحافة الرفيعة.
- قناع ألفا لم يتغير. البكسلات خارج منطقة الجيب في الربع مطابقة حرفياً للنسخة السابقة.
- `verification.json` يقارن بصمات ملفات المحرك وأطلس الواجهة وملفات العرض المحمية؛ لا تعديلات فيها.
- لم تتغير مواقع التصادم أو أنصاف أقطار الكرات أو قواعد اللعبة أو نتائجها.

المراجعة النهائية: القطر الأسود بعد التركيب 52 × 52 بكسل تقريباً، مقابل 68 × 54 سابقاً. `game-desktop.png` من اللعبة الفعلية و`game-pockets.png` تكبير للجيبين المتقابلين من اللقطة نفسها. نجح بناء كاش الأصول، وتطابقت الصورة المقدمة من الخادم المحلي مع الأصل المثبت، وزومنت 759 ملفات إلى Flutter دون نتائج مخالفة.

التثبيت: `node design/pool-middle-pockets-v6/build.cjs --install` من مجلد المنصة، ثم أدوات سلامة الأصول وبناء الكاش ومزامنة Flutter المعتادة.

## أمر التوليد

الأداة المستخدمة هي **built-in image_gen**، ولم يستخدم CLI. استُخدمت معاينة الجيب المعدلة كهدف، وصورة المستخدم الثانية كمرجع للشكل والحافة. النص المستخدم:

> Precise-object-edit. Image 1 is the EDIT TARGET: an enlarged crop of our game table's single middle pocket. Image 2 is the user's STYLE/SHAPE REFERENCE, showing the original top and bottom middle pockets. Correct ONLY the pocket opening and its immediate rim in image 1 to match the original pocket in image 2. Both the outer rim and black interior must be true perfect CIRCLES in this flat top-down image, NOT a vertical ellipse, NOT a horizontal oval, NOT a squircle. Keep the pocket center exactly where it is: about (249,174) on the 498x450 target. Aim for a black interior circle radius about 81 target pixels, with a very thin muted olive-grey bevel of only 5 target pixels. Remove the current thick puffy grey ring, shiny halo, and asymmetric doughnut appearance. The circular hole must be solid very dark black, with subtle depth like image 2. Preserve the exact target crop dimensions, framing, metal plate width and location, wood rails, green cushion positions, surrounding green felt, all colors away from this tiny pocket, and the transparent outside above the rail. Do not redraw the table or change its overall texture or lighting. No balls, lettering, UI, added outlines, decorative trim or extra objects. Return the corrected target crop alone, same aspect ratio and transparency.

## مراجعة مقطع المستخدم

حلل المقطع إلى إطارات في `video-review/`، ثم أعيد السلوك في محرك البلياردو المحلي المعزول. `native-pocket-path.json` يوثق بدء `sinking` قبل انعكاس حركة الكرة، وتعطيل تصادمها مع الكرات والحواف، ثم انتهاء إسقاطها واحتساب scratch ونقل الدور.

الاستنتاج: الرجوع المرئي يحدث ضمن مسار إنهاء السقوط بعد التقاط الكرة، لا كتصادم لعب جديد. يحتاج عرض السقوط والإخفاء إلى تصحيح مستقل. **هذا التعديل البصري للجيبين لا يدعي إصلاح حركة السقوط، ولم يغيّر ذلك المسار أو الفيزياء.**
