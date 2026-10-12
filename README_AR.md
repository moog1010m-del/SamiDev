تقييم المزامنة واختبار السعة والإصلاحات في [SYNC_CAPACITY_REVIEW_AR.md](SamiDev_Platform/SYNC_CAPACITY_REVIEW_AR.md).

> النسخة الحالية: **V37 — تحديث مؤثرات Freesound**. اقرأ `RELEASE_V37_AR.md` أولًا. تتضمن الحزمة جميع تعديلات الواجهة V36.

إعداد التخزين الجديد للإنتاج وترحيل بيانات Redis موثقان في
[POSTGRES_PRODUCTION_AR.md](SamiDev_Platform/POSTGRES_PRODUCTION_AR.md).
PostgreSQL يخزّن بيانات الحسابات الدائمة، وRedis ينسّق اللعب والجلسات المؤقتة.

تحديث المقتنيات وإحصاءات الألعاب والرتب 1–100 ومشهد الانتظار الأصلي موثق في
[PROFILE_RANKS_AND_WAITING_AR.md](SamiDev_Platform/PROFILE_RANKS_AND_WAITING_AR.md).

# SamiDev V36 — إصلاح الواجهة والرسومات

ابدأ من `RELEASE_V36_AR.md` للتغييرات وحدود التحقق. هذه حزمة كاملة وأصول Flutter مضمنة. ما يلي توثيق النسخة الأساسية السابق.

# SamiDev V30 — الويب والباك إند وتطبيق Flutter

لتنظيف هوية الألعاب راجع BRANDING_V30_AR.md. لمشكلة HTTP 502 في APK راجع MOBILE_HTTP_502_FIX_AR.md.

ابدأ من `RELEASE_STATUS_AR.md` لمعرفة ما نُفذ واختُبر وما بقي للتحقق.

الأصول كاملة مرة واحدة في `SamiDev_Platform/game` لتقليل حجم ZIP. قبل أول بناء للتطبيق شغّل `python3 SamiDev_Flutter/tool/sync_assets.py` من هذا المجلد؛ ينسخ الأصول إلى Flutter دون تنزيلها من الإنترنت.

- `SamiDev_Platform`: الويب والباك إند ومحركات الألعاب الأربع وأصولها واختباراتها.
- `SamiDev_Flutter`: مصدر Android وiOS؛ مساحات وتبويبات وشات وتنقل Flutter، مع صفحات الحساب والأصدقاء والمتجر والإدارة الكاملة من الويب.
- `PATCH_V29_TO_V30.diff`: باتش نصي من V29؛ بعده شغّل `python3 SamiDev_Platform/tools/apply_v30_media.py` ثم مزامنة أصول Flutter. التفاصيل في BRANDING_V30_AR.md. المشروع الحالي كامل ولا يحتاج تطبيق الباتش.
- `SOURCE_VALIDATION.json` و`VALIDATION_SUMMARY.json`: فحوص المصدر والخادم وحدود التحقق.
- `.github/workflows/mobile-checks.yml`: مسار بناء واختبار لم يُشغّل هنا.

مقاطع كريزي 8 من Freesound بترخيص CC0 ومراجعها في `SamiDev_Platform/AUDIO_CREDITS.md`. أُصلح تشغيلها عند سحب عدة أوراق وأُضيف تنبيه دفاعي مولّد برمجيًا. طاولة البلياردو تتبع مقتنيات صاحب الدور وصور الكرات محفوظة.

عند الترقية من إصدار أقدم من V26 يلزم تسجيل الدخول مجددًا بسبب تحديث تخزين الجلسات في V26. احتفظ بنسخة Redis احتياطية قبل ترقية الإنتاج. التقارير القديمة داخل المنصة تصف إصدارات سابقة؛ الحالة الحالية في ملفات أعلى الحزمة.
