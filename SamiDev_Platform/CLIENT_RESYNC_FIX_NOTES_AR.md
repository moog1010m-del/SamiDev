# إصلاح تكرار الأوامر / وميض المؤقت / اختفاء الـ Striker / تعطل NEXT

## السبب الفعلي

في اللعب Online تنفذ `BaseLogic.localMove()` الحركة محليًا بشكل متفائل قبل وصول تأكيد السيرفر، لذلك يصبح عداد `_sequence` المحلي متقدمًا مؤقتًا عن `authority_state` بمقدار حركة معلقة. الكود السابق في `game/browser-runtime.js` اعتبر أي اختلاف في sequence خطأ مزامنة مباشرة، فكان يطلب `resync` أثناء حركة طبيعية.

إعادة المزامنة تستدعي `deserialize()` وتعيد بناء حالة المشهد، ولذلك كانت النتيجة المرئية هي إعادة/تكرار الحالة، وظهور واختفاء المؤقت، وإعادة مزامنة الـ Striker والواجهة. كما أن تكرار طلبات resync كان يستطيع تضخيم المشكلة.

## ما تم تغييره

لم يتم تعديل `game/main.js` مطلقًا، وبالتالي لم تتغير قواعد الكاروم أو الفيزياء أو الانتقالات الأصلية.

التغييرات محصورة في:

- `game/browser-runtime.js`
  - لا يطلب resync من `authority_state` أثناء وجود `_localMoves` متفائلة معلقة.
  - يمنع طلب resync جديد أثناء تطبيق snapshot.
  - يعيد تشغيل history مع فحص `packet.n`، ويتخطى الحركة الموجودة أصلًا في snapshot بدل تنفيذها مرتين.
  - يرفض gap حقيقي في sequence ويطلب snapshot جديدًا بدل إكمال حالة ناقصة.
  - يضع حركات WebSocket الواردة أثناء replay في طابور، ثم يطبقها بالترتيب بعد اكتمال snapshot/history.
  - يتجنب سباقًا كانت فيه حركة تصل أثناء انتظار animation وتبقى عالقة في الطابور.

- `game/samidev-network.js`
  - دمج طلبات `resync` المتكررة: يوجد طلب واحد in-flight مع السماح بإعادة المحاولة بعد 1500ms إذا ضاع الرد.
  - تصفير حالة الطلب عند وصول `resync_state` أو إغلاق الاتصال.

- `tests/client_resync_regression.js`
  - اختبار جديد يثبت coalescing لطلبات resync، وتجاوز history المكرر، ورفض gaps، وتطبيق deferred moves مرة واحدة، وثبات `main.js`.

## زر NEXT

منطق زر NEXT نفسه داخل `main.js` لم يكن مكسورًا: الزر موصول بـ `press -> onButtonPress()` ومسار إدخال الويب ما زال يرسل DOWN/UP إلى Gesture Manager. لم يتم تعديل الزر أو نظام gestures حتى لا نخاطر بكسر السحب والتصويب.

السبب الذي كان يقطع/يعيد حالة الواجهة هو resync غير الضروري؛ الإصلاح يمنع هذا المسار. تم التحقق برمجيًا من wiring زر NEXT ومن اختبارات إدخال الـ Striker. تعذر إجراء نقرة Chromium مرئية داخل بيئة التنفيذ الحالية بسبب قيود تشغيل المتصفح، ولذلك لا يوجد ادعاء زائف باختبار بصري يدوي.

## حماية من تغيير منطق اللعبة

SHA-256 لـ `game/main.js` بعد الإصلاح:

`f4c0ceb9e4eedfcf161848d33f673dfd26ce848be9ce556c01e3d23410351d2b`

وهو نفس hash قبل الإصلاح.

الاختبارات التي نجحت تشمل:

- `client_resync_regression.js`
- `striker_move_regression.js`
- `turn_authority_regression.js`
- `alarm_authority_regression.js`
- `state_checkpoint_regression.js`
- `timeout_afk_regression.js`
- `gamehost_conformance.js` — 369 checks / 0 failures عبر 60 إعدادًا
- `store_sequence_regression.py`
- `store_authority_epoch_regression.py`
- `room_leave_regression.py`
- `integration_ws.py` — عميلان WebSocket + snapshot/resync
- `integration_timeout_ws.py` — timeout + authoritative auto move + resync + الحركة التالية

التفاصيل الخام في `CLIENT_RESYNC_TEST_RESULTS.txt`، والفروقات الكاملة في `CLIENT_RESYNC_FIX.patch`.
