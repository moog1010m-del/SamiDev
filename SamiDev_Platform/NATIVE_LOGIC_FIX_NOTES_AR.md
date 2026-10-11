# إصلاح الحركة / انتهاء الوقت / AFK بالاعتماد على main.js الأصلي

هذه النسخة مبنية على آخر ملف `SamiDev_Authoritative_GameHost_AlarmFix.zip` الذي تم رفعه، وليس على نسخة صديقك أو أي نسخة أقدم.

## مبدأ الإصلاح

لم يتم تعديل `game/main.js` ولم يتم إنشاء قواعد أدوار أو AFK بديلة. بقي SHA-256 للملف الأصلي:

`f4c0ceb9e4eedfcf161848d33f673dfd26ce848be9ce556c01e3d23410351d2b`

الإصلاح يجعل طبقة المنصة تستدعي المسارات الأصلية الموجودة داخل `main.js` بدل محاكاتها يدويًا.

## 1) انتهاء الوقت وانتقال الدور

- `BaseLogic` في الحزمة يحتوي `_turnExpire()` فارغة، بينما منطق Carrom الأصلي يعرف حركة تفويت الدور `m:3` ويديرها عبر `missTurn()` و`animationCompleted(true)`.
- في `gamehost/runtime.js` أصبح `_turnExpire` الخاص بالغرفة يستدعي **`BaseLogic.autoMoves([{seat, data:{m:3}}])`**.
- `autoMoves()` الأصلية هي التي تضيف `__auto:1`، تزيد Sequence، تحدث عدادات AFK، وتضع الحركة داخل Reveal لكل مقعد.
- `authority_alarm` يصل للعميل ومعه `__auto`، و`main.js` على العميل ينفذ `_executeClientAutoMoves()` الأصلي.
- تم تفعيل `SamiDev.setTimer/clearTimer` في الـGameHost كـHost timers مستقلة عن BaseLogic alarms، حتى ينفذ callback الأصلي في `animationCompleted(true)` بعد `ON_TURN_MISSED` ويستدعي `nextTurnAfterShotCompleted(..., true)` كما كتبته اللعبة.
- عند تغير الحالة بسبب Host timer يتم إرسال `authority_state` جديد وتخزين Snapshot بعد انتقال الدور.

## 2) AFK / الخسارة بسبب عدم اللعب

لم تتم كتابة عداد جديد. القيم تأتي مباشرة من `main.js`:

- `maxAutoMovesPerSeat = 3` في مباراة لاعبين.
- `maxConsecutiveAutoMoves = 4`.
- `_preMove/_postMove` الأصلية تزيد العدادات.
- عند التفويت الثالث لنفس المقعد تستدعي اللعبة `resign(seat, true)` وتنهي المباراة كـForfeit (`go_resigned_observer`).

تم اختبار 3 تفويتات للاعب 0 مع ضربة حقيقية من اللاعب 1 بين التفويتات حتى لا تختلط قاعدة الـ3 per-seat بقاعدة الـ4 consecutive، وكانت النتيجة `gameOver=true` و`resignedSeats=[0]` من `main.js` نفسه.

## 3) تحريك الـStriker عبر شريط "Drag your Striker"

تمت إعادة إنتاج العطل داخل Chromium فعليًا، وليس فقط باختبار `m:6` على السيرفر.

### السبب الجذري

- DOM Pointer Events تعطي الإحداثي `Y` من أعلى الشاشة (top-left origin).
- `main.js` الأصلي، داخل `InputManager.digest()`، يتوقع Touch coordinates من منصة SamiDev بأصل من أسفل الشاشة ثم يعكس `Y` بنفسه.
- `browser-runtime.js` كان يمرر `Y` الخاص بالمتصفح كما هو؛ لذلك كان `main.js` يعكسه مرة إضافية.
- النتيجة: عند الضغط على قرص الـslider الظاهر أسفل الشاشة، Hit-Test يبحث عن العنصر في الموضع العمودي المقابل، فلا يتم التقاط `fm` slider ولا يصل أي استدعاء إلى `requestStrikerMove()`.

### الإصلاح

تم تعديل Browser Input Bridge فقط:

- أضيف `touchPoint()` ليحوّل Touch Y إلى bottom-left physical coordinates قبل إرسال الحدث إلى `main.js`.
- `main.js` يقوم بالتحويل العكسي الأصلي كما هو، فيصبح Hit-Test مطابقًا لمكان العنصر المرئي.
- Mouse coordinates لم تُعكس؛ `MouseManager` في `main.js` لا يعكس Y، لذلك بقي `emitMouse()` يستخدم `eventPoint()` الأصلي.
- بقيت حماية Hover السابقة: Touch MOVE لا يرسل إلا عند Pointer نشط/مضغوط.
- بقيت نقاط اللمس ترسل كنسخة مستقلة `{id,x,y}`.

منطق الحركة نفسه لم يتغير: `slider -> requestStrikerMove -> m:6 -> updateStrikerPosition -> table.setStrikerPos` كله ما زال داخل `main.js`.

### اختبار Chromium الفعلي

تم تشغيل نفس `main.js` و`browser-runtime.js` داخل Chromium مع WebGL، ثم سحب القرص الموجود على الشريط نفسه:

- البداية: `strikerPos = 0.5`.
- في أول تشغيل، أول Drag أغلق Tutorial overlay الأصلي (`main.js` يسجله كـfull-screen drag) ولم يحرّك الـstriker؛ هذا سلوك Tutorial الأصلي.
- السحب التالي إلى اليمين: `strikerPos = 0.908215` وجرى استدعاء `requestStrikerMove()` عدة مرات أثناء السحب.
- السحب التالي إلى اليسار: `strikerPos = 0.208418`.
- لا توجد Page/Render errors.

## 4) Sequence بعد الحركة التلقائية

`m:3` التي ينفذها GameHost ترفع `_sequence` داخل `main.js` بدون أن تمر عبر `backend/store.append_move()`. لذلك كان يمكن أن يصبح Store متأخرًا ويرفض حركة لاحقة كـDESYNC.

تمت إضافة `sync_sequence()` في MemoryStore وRedisStore. عند وصول `authority_alarm/authority_state`، يرفع Gateway الـSequence المخزن إلى قيمة GameHost الموثوقة (monotonic فقط، ولا يخفضها عند وصول event قديم). لا يتم إنشاء History move مزيف.

## الاختبارات المضافة

- `tests/striker_move_regression.js`
- `tests/timeout_afk_regression.js`
- `tests/store_sequence_regression.py`
- `tests/integration_timeout_ws.py` (اختبار WebSocket حقيقي وينتظر انتهاء turn timer الطبيعي)

والاختبارات القديمة بقيت ناجحة أيضًا. راجع `NATIVE_LOGIC_FIX_TEST_REPORT.json` للتفاصيل الكاملة.
