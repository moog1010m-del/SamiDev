# تحديث واجهة الملف الشخصي

## ما تم الآن

- إعادة تصميم صفحة الملف الشخصي لتكون أقرب للمرجع المرئي مع الحفاظ على هوية المشروع.
- دعم صورة ملف شخصي فعلية مع fallback للحرف الأول عند عدم وجود صورة.
- زر كاميرا لاختيار PNG/JPG/WebP، مع قص مربع وضغط الصورة في المتصفح قبل الإرسال.
- تخزين صورة الملف الشخصي في حساب المستخدم عبر `PATCH /api/profile` مع تحقق من النوع والحجم ومحتوى الملف.
- إظهار عبارة `لاعب منذ ...` اعتمادًا على `createdAt` الموجود أصلًا في الحساب.
- إضافة خمس نجوم وشعار بسيط كعناصر عرض فقط حاليًا، بدون نظام تقييم/مستويات أو صلاحيات مرتبطة بهما.
- إزالة البطاقة التقنية القديمة من واجهة الملف الشخصي.
- إبقاء قائمة الأصدقاء والإدارة وغرف اللعب ومنطق المباراة دون تغيير.

## حدود الأمان والحجم

- الحد الأقصى للصورة بعد الضغط على الخادم: 300KB raw image.
- حد HTTP أصبح منفصلًا عن حد WebSocket حتى لا يتغير حد رسائل المباراة عند دعم الصور.
- الصورة تُقبل فقط كـ PNG/JPEG/WebP وتُفحص magic bytes قبل الحفظ.

## الاختبارات

- `python -m py_compile backend/social_platform.py backend/app.py tests/profile_ui_regression.py` — PASS
- `node --check game/platform/platform.js` — PASS
- `python tests/profile_ui_regression.py` — PASS
- `python tests/platform_v1_regression.py` — PASS
- `node tests/browser_runtime_race_regression.js` — PASS
- `node tests/client_resync_regression.js` — PASS
- اختبار HTTP مستقل لرفع صورة profile أكبر من حد 64KB القديم — PASS

`game/main.js` لم يُعدل في هذا التحديث.
