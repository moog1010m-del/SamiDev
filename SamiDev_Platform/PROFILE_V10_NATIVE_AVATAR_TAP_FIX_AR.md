# إصلاح V10 — فتح البروفايل من نقر الأفاتار الأصلي داخل اللعبة

## سبب المشكلة الحقيقي
واجهة اللعبة الأصلية في `main.js` لديها بالفعل مسار نقر صحيح على صورة اللاعب:

`Avatar.image.onTap -> Avatar._onImageTap() -> SamiDev.showProfile(seat)`

لكن طبقة المتصفح في `game/browser-runtime.js` كانت تعرّف `showProfile` كدالة فارغة، لذلك كانت النقرة تصل من WebGL إلى اللعبة ثم تضيع عند الـhost bridge.

إصلاحات V7–V9 حاولت التعويض بواسطة مناطق HTML شفافة فوق الـcanvas. هذه المناطق لم تكن المسار الصحيح، بل كانت قادرة أيضًا على اعتراض `pointer/touch` ومنع InputManager الأصلي من استقبال الحدث.

## الإصلاح
- ربط `SamiDev.showProfile(seat)` مباشرة بـ `window.SamiDevPlayerProfileUI.openSeat(seat)`.
- إزالة مسار hit-targets الشفافة وحساب الإحداثيات من `player-profile-ui.js`.
- إزالة اعتراض `pointerdown/mousedown/touchstart/click` من طبقة البروفايل.
- ترك `main.js` نفسه بدون تعديل؛ نستخدم نظام النقر الأصلي الموجود فيه.
- اللاعب المسجل يفتح بيانات الحساب الحقيقية، والضيف يفتح بطاقة ضيف بدل الصمت.

## الاختبارات
- `tests/player_profile_click_regression.py`: PASS
- `tests/player_profile_social_regression.py`: PASS
- `tests/profile_game_avatar_regression.py`: PASS
- `tests/avatar_exit_regression.py`: PASS
- `tests/profile_win_stats_regression.py`: PASS
- `tests/gamehost_conformance.js`: 369/369 PASS
- `tests/client_resync_regression.js`: PASS
- `tests/turn_authority_regression.js`: PASS
- `tests/platform_v1_regression.py`: PASS

## ملاحظة
`game/main.js` لم يتغير، وSHA-256 بقي:

`f4c0ceb9e4eedfcf161848d33f673dfd26ce848be9ce556c01e3d23410351d2b`
