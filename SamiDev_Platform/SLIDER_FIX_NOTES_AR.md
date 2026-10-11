# إصلاح شريط Drag your Striker

تمت إعادة إنتاج المشكلة في Chromium. السبب لم يكن `m:6` ولا السيرفر، بل اختلاف أصل إحداثي Y بين DOM Pointer Events وSamiDev Touch Input.

المتصفح يعطي Y من أعلى، بينما `main.js` يعكس Touch Y داخليًا لأنه يتوقع إحداثيات SamiDev من أسفل. كان الـbridge يرسل Y المتصفح مباشرة، فينتج Hit-Test معكوس عموديًا.

الإصلاح في `game/browser-runtime.js` فقط:

- Touch: `y = canvas.height - domY` قبل إرساله إلى `main.js`.
- Mouse: يبقى top-origin بدون تغيير.
- `game/main.js` لم يتغير.

اختبار Chromium الفعلي:

- قبل الإصلاح: visual drag من مركز slider لم يستدع `requestStrikerMove()` وبقي `strikerPos=0.5`.
- بعد الإصلاح: بعد إغلاق Tutorial الأصلي، visual drag نقل الموضع إلى `0.908215` ثم `0.208418`.

ملاحظة: إذا كان Tutorial الكامل مفتوحًا لأول مرة، أول drag قد يغلقه لأنه يملك full-screen drag handler في `main.js`. بعد إغلاقه، شريط الـslider يلتقط السحب بصورة طبيعية.
