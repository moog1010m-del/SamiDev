# تقرير التدقيق الجنائي — مشكلة الشاشة البيضاء واختلاف الدور

## نطاق التدقيق

هذا التقرير يخص النسخة الموجودة في هذه الحزمة فقط. لم يتم تعديل `game/main.js`؛ بقي byte-for-byte مطابقًا للأصل.

- `game/main.js` SHA-256: `f4c0ceb9e4eedfcf161848d33f673dfd26ce848be9ce556c01e3d23410351d2b`
- عدد ملفات الزون المدققة: **10**
- مجموع البايتات المدققة: **1,165,775**
- مجموع الأسطر المدققة: **5,267**
- `FORENSIC_LINE_LEDGER.csv` يحتوي سجلًا لكل سطر خام: اسم الملف، رقم السطر، byte offsets، طول البايتات، نوع newline، SHA-256 للسطر الخام، والعلامات الدلالية.
- `FORENSIC_FILE_MANIFEST.json` يثبت SHA-256 والحجم وعدد الأسطر وفحص BOM/NUL/control characters لكل ملف.
- `FORENSIC_CROSS_REFERENCE.txt` يجمع كل المواضع المرتبطة بـ turn/sequence/authority/revision/resync/snapshot/resize/sync/timers/events.
- `FORENSIC_MAINJS_ZONE.txt` يحفظ offsets وhashes للمقاطع الحساسة داخل `main.js` المصغّر.

الملفات المدققة بالكامل:

1. `game/browser-runtime.js`
2. `game/samidev-network.js`
3. `game/chat-ui.js`
4. `backend/app.py`
5. `backend/store.py`
6. `backend/gamehost_client.py`
7. `gamehost/runtime.js`
8. `gamehost/server.js`
9. `game/main.js`
10. `deploy/nginx/nginx.conf`

## النتيجة التنفيذية

تم إثبات مشكلتين منفصلتين لكنهما تتقاطعان في bridge/lifecycle حول `surfaceChanged/sync`:

1. **اختلاف الدور كان bug حقيقيًا وقابلًا لإعادة الإنتاج بنفس `main.js` الأصلي.** أمكن الوصول إلى حالة يكون فيها السيرفر `turn=[1]` بينما عميل متأثر يبقى `turn=[0]` مع بقاء `sequence` متطابقة. لذلك كل طرف يستطيع أن يرى أن الدور عند خصمه، بينما فحص العميل القديم لا يكتشف المشكلة لأنه كان يقارن `sequence` فقط.
2. **الشاشة البيضاء كان لها startup race حقيقي.** إذا قيس Canvas مؤقتًا بأقل من `8×8` كان `resize()` يخرج بصمت، ثم يكمل startup ويختفي loader من غير ضمان أن `surfaceChanged()` حصل. وبما أن `main.js` سبق أن مسح WebGL بالأبيض، يمكن أن يبقى المشهد أبيض حتى refresh أو حدث لاحق.

تم إصلاح المسارين وإضافة اختبارات regression مخصصة لهما، ثم أجري مرور تدقيق ثانٍ بعد الإصلاح. هذا المرور كشف عيبين إضافيين في recovery وتم إصلاحهما قبل الحزمة النهائية.

---

## F-01 — شاشة بيضاء بسبب Canvas collapsed وقت startup — مؤكد ومصلح

### السبب الأصلي

في النسخة الأصلية كان `resize()` يقرأ `getBoundingClientRect()` ثم يعمل return إذا كان القياس أصغر من `8×8`، من غير retry مضمون. startup كان يستطيع الاستمرار وإخفاء حالة التحميل رغم أن `main.js` لم يستلم أول surface صالح.

التعليق القديم نفسه أشار إلى أن collapsed layout مؤقتًا حدث في production.

### الإصلاح الحالي

في `game/browser-runtime.js`:

- الأسطر **243–285**: `resize()` يعيد `false` للقياس غير الصالح بدل اعتبار التهيئة ناجحة.
- الأسطر **287–293**: `ensureInitialSurface()` ينتظر عبر `requestAnimationFrame` حتى يصبح السطح صالحًا، ويعطي خطأ ظاهرًا بدل Canvas أبيض صامت إذا استمر الفشل.
- الأسطر **890–892**: `ResizeObserver` يلتقط توسع Canvas اللاحق، فلا يعتمد التعافي على أن المتصفح سيطلق `window.resize` بالضرورة.

### عيب اكتشفه التدقيق بعد الإصلاح

`ResizeObserver` يمكن أن يعمل قبل أن ينتهي `main.js` من تسجيل `state.surfaceChanged`. لو حفظنا المقاس كـinitialized في تلك اللحظة، فإن نفس المقاس عند startup الحقيقي كان سيعتبر duplicate، وقد نعيد إنشاء الشاشة البيضاء بأنفسنا.

تم إغلاق هذا في الأسطر **255–260**: إذا لم توجد `surfaceChanged` فعلية بعد، لا يتم تثبيت surface كـinitialized.

الاختبار `tests/browser_runtime_race_regression.js` يثبت:

- `collapsedSurfaceRecovered=true`
- `earlyObserverCannotPoisonSurface=true`

---

## F-02 — render request يمكن أن يضيع بعد exception — مؤكد ومصلح

حلقة الرسم كانت تمسح `frameRequested=false` قبل `drawFrame()`. إذا رمى أول رسم exception عابرًا، لا يوجد ضمان لطلب frame جديد، فيستطيع Canvas البقاء على اللون السابق.

الأسطر **873–883** الآن تعيد طلب frame بعد أخطاء الرسم العابرة بعدد محاولات محدود بدل loop لا نهائي.

كما أضيف handling لـWebGL context:

- **894–898**: `webglcontextlost`
- **900–903**: `webglcontextrestored`

لأن `main.js` الحالي لا يملك lifecycle موثوقًا لإعادة بناء كل موارد GPU بعد context restore، يتم استخدام reload كمسار recovery واضح بدل ترك Canvas ميتًا.

---

## F-03 — race يجعل العميل يفوّت انتقال الدور — مؤكد، أُعيد إنتاجه، ومصلح

### سلسلة السبب داخل `main.js` الأصلي

`FORENSIC_MAINJS_ZONE.txt` يثبت المقاطع التالية من نفس bundle الأصلي:

1. `Game.surfaceChange(...)` يؤدي في النهاية إلى sync.
2. `CarromLogic.onSync` يضع `_syncCalledFlag=true`.
3. `animationCompleted()` يضع `_syncCalledFlag=false` ثم يشغل timer محليًا.
4. callback الـtimer لا ينفذ `nextTurnAfterShotCompleted(...)` إذا أصبحت `_syncCalledFlag=true` قبل انتهائه.

لذلك يمكن أن يحدث:

```text
shot/timeout completes
  -> _syncCalledFlag = false
  -> pending ~500ms turn timer
  -> visual resize
  -> surfaceChanged()
  -> main.js sync()
  -> onSync => _syncCalledFlag = true
  -> pending turn timer is suppressed
  -> local client keeps old turn
```

السيرفر في نفس الوقت يتقدم إلى الدور الصحيح.

### إعادة الإنتاج قبل الإصلاح

`tests/turn_resize_race_regression.js` يستخدم **نفس `main.js` الحقيقي** وليس mock لمنطق اللعبة.

النتيجة المثبتة:

```text
serverTurn        = 1
brokenClientTurn  = 0
repairedClientTurn= 1
sameSequenceBroken= true
```

هذه هي الحالة الخطرة تحديدًا: `turn` مختلف بينما `sequence` لا تكشف الاختلاف.

### الإصلاح الحالي

`game/browser-runtime.js` الأسطر **270–282** تحفظ قيمة `_syncCalledFlag` حول **visual surface resize** فقط. إذا كان false قبل resize وجعله `main.js` true بسبب surface sync، يعاد false حتى لا يلغى turn timer المحلي. لا يتم فرض `logic.turn` يدويًا ولا تعديل `main.js`.

الاختبار يثبت `visualResizePreservesTurnTimer=true` و`repairedClientTurn=1`.

> ملاحظة صيانة: هذا bridge يعتمد على private field في الـbundle الحالي. لذلك تثبيت SHA واختبار regression مهمان إذا تغير `main.js` مستقبلًا.

---

## F-04 — فحص authority القديم كان blind للـturn — مؤكد ومصلح

العميل القديم كان يفحص `authority_state.sequence` تقريبًا فقط. لذلك الحالة:

```text
server: sequence=[2,0], turn=[1]
client: sequence=[2,0], turn=[0]
```

كانت تمر كأنها متزامنة.

الآن:

- **546–548**: نوافذ grace/retry/max-wait.
- **555–561**: `authorityMismatch()` يقارن `sequence + turn + gameOver`.
- **563–596**: يحفظ أحدث authority مع `authorityEpoch/revision` ويرفض revision أقدم.
- **606–640**: mismatch لا يضيع إذا وصل أثناء animation أو local optimistic move أو snapshot busy؛ يعاد فحصه، وبعد استمرار الاختلاف يطلب resync.
- **633–637**: لا يمسح mismatch لحظة إرسال طلب resync؛ يبقى حتى يطبق snapshot ويثبت التطابق.
- move/authority_alarm/authority_state كلها تدخل نفس reconciliation path.

`tests/browser_runtime_race_regression.js` يثبت:

- `sameSequenceTurnMismatchDetected=true`
- `staleRevisionRejected=true`
- `animatingMismatchRetained=true`

---

## F-05 — authority ordering لم يكن يصل كاملًا للمتصفح — مؤكد ومصلح

GameHost لديه `authorityEpoch` و`revision`، لكن bridge القديم لم يكن يمررهما بصورة كافية للعميل. بدون ذلك يصعب على العميل معرفة أن authority أقدم وصلت بعد أحدث منها.

`backend/app.py` في `_on_gamehost_event` يمرر الآن:

- `authorityEpoch`
- `revision`
- `turn`
- `sequence`
- `gameOver`

لـ`authority_state` و`authority_alarm`، كما أن move response يحمل authority metadata نفسها.

العميل يستخدم epoch/revision لمنع فحص state قديمة فوق state أحدث.

---

## F-06 — resync كان يستطيع إعادة Store checkpoint أقدم من GameHost — مؤكد بنيويًا ومصلح

المسار القديم لرسالة `resync` كان يعتمد على `store.resync()` فقط. لكن انتقالات timer/turn server-generated قد تغير الحالة الحية قبل أن تكون آخر checkpoint المخزنة مكافئة لها في كل لحظة. لذلك قد يطلب العميل «الحقيقة» ثم يتلقى durable snapshot أقدم من GameHost الحي.

الإصلاح:

- `backend/app.py` **171–185**: `_persist_live_authority()` يحفظ sequence/snapshot آمنة آتية من GameHost فقط.
- **187–207**: `_authoritative_resync()` يطلب الحالة الحية من GameHost صاحب lease أولًا، يحدث Store، ثم يرسل resync state؛ وإذا GameHost غير متاح يبقى fallback للـStore.
- **625–627**: WebSocket `resync` يستخدم `_authoritative_resync()`.
- `backend/store.py` **399–423** و**934–952**: تمت إضافة `snapshotRevision` حتى يمكن لـsnapshot أحدث authority-wise أن تستبدل snapshot بنفس `moveCount` من غير أن يرجع state إلى revision أقدم.

`tests/live_resync_regression.py` يبدأ عمدًا بـStore stale ويثبت:

```text
staleStoreReplaced = true
snapshotRevision   = 9
turn               = [1]
sequence           = [2,0]
authorityEpoch     = 4
revision           = 9
```

---

## F-07 — mismatch كان يضيع أثناء animation — مؤكد ومصلح

السلوك القديم كان يستطيع تجاهل authority mismatch إذا كان العالم يتحرك أو snapshot/resync جاريًا، من دون queue مضمونة تعيد فحص نفس authority بعد استقرار الحالة.

الآن `pendingAuthority` تبقى محفوظة، و`evaluateAuthority()` يعيد الفحص حتى:

- يحصل التطابق؛ أو
- يستمر الاختلاف خارج grace؛ ثم يطلب snapshot authoritative.

لا يتم اعتبار مجرد وصول resync نجاحًا؛ يجب أن تتطابق الحالة بعدها.

---

## F-08 — timeout أثناء replay كان يُعامل كأنه نجاح — اكتشفه post-fix audit ومصلح

`waitUntilWorldSettles()` كان لا يميز بصورة صريحة بين «العالم استقر» و«انتهت المهلة». هذا خطر لأن recovery يمكن أن يكمل replay فوق عالم ما زال يتحرك.

الأسطر **477–489** تعيد الآن:

- `true` إذا توقفت animation.
- `false` إذا تجاوزت 12 ثانية.

`replayHistory()` يتوقف عند false ويعيد طلب authoritative recovery بدل تركيب moves فوق state غير مستقرة.

تم توسيع `tests/client_resync_regression.js` لالتقاط هذا المسار.

---

## F-09 — waiting overlay يعود فوق المباراة — مؤكد ومصلح

`game/samidev-network.js` كان يحتفظ بـlisteners لمرحلة انتظار اللاعبين حتى بعد `start`. أي `room_state` لاحقة (مثل runtime_ready) تستطيع إعادة رسالة الانتظار فوق Canvas.

الأسطر **241–269** الآن تسجل listeners مؤقتة وتلغيها في `finally` فور انتهاء `startPromise`.

---

## F-10 — `/platform/` يرجع 404 عند الرجوع من اللعبة — مؤكد ومصلح

`backend/app.py`:

- `/platform` -> redirect إلى `/platform/`
- `/platform/` -> index مباشرة

المسارات الحالية عند **737–738** و**789–790** تمنع سقوط `/platform/` إلى static file handler كأنه filename.

---

## F-11 — mixed runtime بسبب cache — مؤكد كعيب deployment ومصلح

HTML/JS/CSS/JSON ذات أسماء ثابتة كانت قابلة للتخزين بمدة طويلة نسبيًا، ما يسمح بعد deploy بتحميل `browser-runtime.js` من إصدار و`main.js`/HTML من إصدار آخر.

الإصلاح:

- `client-config.js` = `no-store` ويحمل SHA لـ`main.js`.
- runtime files الثابتة ذات أسماء غير fingerprinted = `no-cache, must-revalidate`.
- `browser-runtime.js` السطر **788** يحمل `main.js?v=<sha-prefix>`.
- nginx يعكس نفس السياسة.

---

# الاختبارات النهائية على نفس ملفات الحزمة

## GameHost / main.js

`node tests/gamehost_conformance.js`

```text
settingsCombinations = 60
checksPassed         = 369
checksFailed         = 0
mainJsSha256         = f4c0ceb9e4eedfcf161848d33f673dfd26ce848be9ce556c01e3d23410351d2b
```

## إعادة إنتاج race الدور

`node tests/turn_resize_race_regression.js`

```text
serverTurn         = 1
brokenClientTurn   = 0
repairedClientTurn = 1
sameSequenceBroken = true
sameSequenceRepaired = true
mainJsUntouched    = true
```

## startup/authority browser bridge

`node tests/browser_runtime_race_regression.js`

كل الآتي PASS:

- collapsed surface recovery
- early ResizeObserver safety
- visual resize preserves turn timer
- same-sequence turn mismatch detection
- stale revision rejection
- mismatch retained during animation

## resync

- `tests/client_resync_regression.js`: PASS
- `tests/live_resync_regression.py`: PASS
- stale Store replaced by live GameHost: PASS

## باقي regression

PASS:

- `turn_authority_regression.js`
- `timeout_afk_regression.js`
- `alarm_authority_regression.js`
- `state_checkpoint_regression.js`
- `striker_move_regression.js`
- `platform_v1_regression.py`
- `store_sequence_regression.py`
- `store_authority_epoch_regression.py`
- كل JS syntax عبر `node --check`
- Python `compileall`

## اختبار stack حي: Gateway + GameHost + WebSocket

تم تشغيل GameHost الفعلي مع backend الفعلي من هذه النسخة ثم تشغيل الاختبارات عبر WebSocket حقيقي. PASS:

- legal move replicated على العميلين
- wrong-turn move rejected
- browser snapshot غير authoritative وتم تجاهله
- resync يحمل server snapshot
- timeout يغير turn إلى `[1]` على authority
- resync بعد timeout يحمل snapshot turn `[1]` وsequence `[2,0]`
- اللاعب التالي يستطيع الحركة
- reconnect epoch/security lifecycle
- room leave
- web chat/reconnect history
- invite one-time flow وclient-config no-store

### قيد الاختبار الوحيد

محاولة تشغيل Chromium/Playwright داخل بيئة الفحص نفسها مُنعت بسياسة البيئة (`ERR_BLOCKED_BY_ADMINISTRATOR` عند navigation إلى localhost/file). لذلك **لا أدعي** أن browser E2E حقيقي عبر Chromium مر هنا. عوضًا عنه توجد:

1. اختبارات VM مباشرة لكود browser-runtime؛
2. اختبار race يستخدم `main.js` الحقيقي؛
3. اختبارات WebSocket حقيقية بين Gateway وGameHost.

يوصى مع ذلك بعمل smoke test على المتصفح الفعلي بعد deploy، خصوصًا mobile resize/orientation/background-resume.

---

# المخاطر المتبقية — ليست جذورًا مثبتة للمشكلتين

## R-01 — GameHost -> Gateway authority events عبر SSE غير durable — متوسط

`gamehost/server.js` يكتب event إلى عملاء SSE المتصلين حاليًا فقط؛ لا يوجد event backlog أو Last-Event-ID replay. انقطاع قصير في event stream يستطيع إسقاط authority event.

الإصلاح الحالي يقلل الضرر لأن:

- العميل يحتفظ بمismatch ويطلب resync؛
- resync الآن يسحب state حية من GameHost؛
- move/authority لاحقة تعيد reconciliation.

لكن للحصول على at-least-once delivery حقيقي يلزم durable event/outbox أو replayable stream. هذا hardening معماري، وليس السبب الذي استُخدم لإعادة إنتاج bug الدور الحالي.

## R-02 — accept revision قبل fanout — متوسط

في `_on_gamehost_event` يتم قبول authority revision في Store قبل fanout. لو حصل فشل استثنائي بين القبول والتوزيع، إعادة نفس revision لاحقًا قد ترفض باعتبارها مكررة. يمكن تحسينه مستقبلًا بنمط claim/complete أو outbox durable.

## R-03 — send failures داخل fanout ليست observability قوية — منخفض/متوسط

إرسال sockets يستخدم تجميعًا يسمح باستمرار الباقي عند فشل socket، لكن retry/logging لكل destination محدود. reconnect/resync يقلل أثره، إلا أن metrics/logging أدق سيكون أفضل للإنتاج.

## R-04 — asset load failures قد تُخفى — متوسط

بعض image/text loading paths تسمح بالاستمرار أو fallback عند فشل asset. هذا مفيد لعدم crash الكلي لكنه قد يخفي ملفًا ناقصًا. يفضل production asset manifest/hash + telemetry إذا استمر أي rendering anomaly.

## R-05 — الاعتماد على `_syncCalledFlag` خاص بالbundle الحالي — صيانة

الإصلاح لا يعدل `main.js`، لكنه يعرف semantics لحقل private في هذا SHA المثبت. أي استبدال لـ`main.js` يجب أن يعيد تشغيل `turn_resize_race_regression.js` وconformance suite قبل deploy.

## R-06 — GameHost room retention طويل — موارد، ليس bug الدور

الـroom idle TTL الافتراضي طويل نسبيًا ولا يوجد cleanup فوري عند game-over في كل المسارات. هذا قد يحتفظ بinstances أطول من اللازم تحت حمل كبير، لكنه غير مرتبط بالشاشة البيضاء/اختلاف الدور.

---

# الحكم بعد التدقيق

- مشكلة الدور: **كانت موجودة فعليًا، أُعيد إنتاجها بنفس `main.js` الحقيقي، والإصلاح الحالي يمنع مسارها ويضيف detection + authoritative recovery كطبقة ثانية.**
- الشاشة البيضاء: **تم إغلاق startup collapsed-surface race، عيب early observer الذي اكتشف أثناء التدقيق، فقدان render request بعد exception، وWebGL context-loss recovery.**
- `main.js`: **لم يتغير حرفًا واحدًا**.
- server authority: ما زال GameHost هو المصدر الأساسي للحقيقة؛ العميل لا يستطيع فرض snapshot.
- لا توجد نتيجة تدقيق تقول إن النظام خالٍ من كل bug ممكن مستقبلًا؛ المخاطر المتبقية أعلاه موثقة بدل إخفائها.
