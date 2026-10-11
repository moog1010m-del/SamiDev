# إصلاح V8 — فتح ملف اللاعب من الأفاتار

## سبب المشكلة
V7 كان يعتمد على منطقة نقر صغيرة مرتبطة بموضع افتراضي للأفاتار، وكان يتجاهل اللاعب بالكامل إذا لم يحمل `accountId`. لذلك النقر على لاعب دخل كضيف مثل `Player 869` لا ينفذ أي شيء.

## ما تغير
- توسعة منطقة النقر في 1v1 لتغطي لوحة هوية الخصم كاملة (الأفاتار + الاسم + المؤقت) بدل دائرة افتراضية صغيرة.
- مناطق مناسبة أيضًا لمقاعد 2v2 الجانبية.
- التقاط `pointerdown` على مستوى `document` كمسار احتياطي، مع تقييده بمنطقة هوية الخصم فقط.
- استمرار مسار الـcanvas ومسار زر الوصول الشفاف كطبقات احتياطية إضافية.
- اللاعب المسجل يفتح ملفه الحقيقي من `/api/public-profile/{accountId}`.
- اللاعب الضيف يفتح بطاقة ضيف بدل تجاهل النقرة؛ الإحصائيات والإجراءات المرتبطة بالحساب تظهر غير متاحة بدل اختلاق بيانات.

## التحقق
- Chromium فعلي عبر Harness: فتح بطاقة حساب مسجل عند النقر: PASS.
- Chromium فعلي عبر Harness: فتح بطاقة ضيف عند النقر: PASS.
- player_profile_click_regression: PASS.
- player_profile_social_regression: PASS.
- profile_ui_regression: PASS.
- profile_game_avatar_regression: PASS.
- avatar_exit_regression: PASS.
- profile_win_stats_regression: PASS.
- GameHost conformance: 369/369 PASS.
- `game/main.js` لم يتغير.
