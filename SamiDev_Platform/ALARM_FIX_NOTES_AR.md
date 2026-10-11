# SamiDev Alarm Authority Fix

## السبب المثبت من سجل المتصفح

سجل العميل أظهر التسلسل التالي بعد نجاح تحقق الفيزياء:

- `validateAnimationClient - anim 1 VERIFIED`
- `Unexpected client alarm: expected=3, data=undefined`
- `[SamiDev] authority alarm rejected ... alarmId: 2`
- ثم `in-place resync`
- وبعد الضربة التالية `desync ... expected: 0, actual: 1`

هذا يثبت أن مسار Physics/WorldState كان قد وصل إلى VERIFIED، ثم كسر Alarm قديم/غير صالح حالة العميل وأدخل المباراة في resync، وبعده ظهر sequence mismatch.

## الخلل الأول: العميل Online كان يشغل Alarm محليًا

`installLocalHost(logic)` كان يربط `onSetAlarm` بـ `setTimeout` محلي حتى في Online Authoritative mode.

الآن:

- Local/Hotseat: المتصفح يشغل الـAlarm محليًا.
- Online: السيرفر وحده يشغل الـAlarm.
- العميل يحتفظ بتوقيت BaseLogic الداخلي لعرض العد التنازلي، لكنه لا ينفذ `logic.alarm()` بنفسه.

## الخلل الثاني: GameHost كان يبث Alarm مرفوض

المؤقت القديم يمكن أن يبقى بعد إلغاء/استبدال Alarm داخل GameLogic. عندما يطلق لاحقًا، `main.js` يرفضه لأنه لا يطابق `_nextAlarmId`.

الإصدار السابق كان يبث `authority_alarm` حتى لو `logic.alarm()` أعاد `false`، وغالبًا بدون reveal. هذا يجعل Client BaseLogic يدخل مسار resync عمدًا.

الآن GameHost:

1. يلغي timers القديمة عند استبدال Alarm بآخر.
2. قبل تنفيذ timer يتحقق أن:
   - `_pendingAlarm === true`
   - `_nextAlarmId === alarmId`
3. إذا كان timer قديمًا: يسجله `stale_alarm_ignored` ولا يدخله إلى GameLogic.
4. إذا `logic.alarm()` رفضه: لا يبثه.
5. إذا لم ينتج authoritative reveal: لا يبثه.

## حماية العميل

العميل يرفض أي `authority_alarm` بدون `reveal` بدل تمريره إلى `logic.alarm(undefined, id)`.

كما يتجاهل Alarm أقدم من `nextAlarmId` دفاعيًا.

## Backend

تم فصل إرسال `authority_alarm` عن وجود Snapshot. الـAlarm الصحيح لا يجب أن يضيع فقط لأن Physics checkpoint غير قابل للـserialize في تلك اللحظة.

## اختبارات

- `tests/alarm_authority_regression.js`: PASS
  - stale alarm لا يُبث.
  - superseded timer يُلغى.
- GameLogic Conformance: `369/369` PASS.
- State checkpoint regression: PASS.
- WebSocket integration: PASS.

## ملاحظة WebGL

في السجل الجديد للمستخدم لم تعد تظهر أخطاء `Status=36061` أو `INVALID_FRAMEBUFFER_OPERATION`. المشكلة المتبقية التي ظهرت في السجل كانت Alarm/sequence.
