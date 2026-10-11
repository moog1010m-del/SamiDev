# SamiDev State Checkpoint Fix

## السبب الجذري الذي تم إثباته

`GameLogic.serialize()` في Carrom ليس getter خاملًا في وضع السيرفر. لأن اللعبة تضبط:

- `ValidationMode.ServerTrust`
- `ExecForSerialization.AllButLatest`

فإن `serialize()` قد يستدعي `validateOrExecute(true)` أثناء وجود animation معلقة.

في الاختبار قبل الإصلاح:

```text
قبل serialize:
noAnimations=1
lastState=0
lastValidAnim=0
animValidation=[1]

بعد serialize:
noAnimations=1
lastState=1
lastValidAnim=1
animValidation=[]
```

أي أن مجرد أخذ snapshot كان يغيّر حالة السيرفر قبل اكتمال WorldState من العملاء.

## الإصلاح

1. منع `serialize()` أثناء أي animation validation معلقة.
2. إنشاء snapshot فقط عند safe checkpoint:
   - لا توجد `animValidation` معلقة.
   - `lastValidAnim >= noAnimations`.
   - لا يوجد pending physics execution.
3. إذا snapshot أقدم من `moveCount`، يعيد resync الحركات التالية للـsnapshot بدل حذف history.
4. client resync يعمل `deserialize(snapshot)` ثم replay للحركات بعد snapshot.
5. إعادة إصلاح WebGL packed depth/stencil باستخدام `DEPTH_STENCIL_ATTACHMENT`.
6. إضافة gate يمنع أي serialize آمن من تغيير حالة GameLogic؛ إذا تغيرت الحالة يرمي GameHost خطأ بدل تخزين snapshot فاسد.

## نتائج الاختبار

`STATE_CHECKPOINT_REPORT.json`:

- pending snapshot deferred: PASS
- pending server state unchanged: PASS
- one WorldState still deferred: PASS
- stable snapshot produced after full validation: PASS
- stable serialize is pure: PASS

GameHost conformance:

- **369/369 passed**
- 60 settings combinations

WebSocket integration:

- legal authoritative move: PASS
- wrong-turn rejection: PASS
- client snapshot ignored: PASS
- server resync snapshot: PASS

## لماذا هذا مختلف عن إصلاحات reveal السابقة؟

إصلاح reveal يعالج نقل قرار validation إلى العميل. هذا الإصلاح يمنع GameHost نفسه من **تغيير قرار الفيزياء أثناء إنشاء snapshot** قبل أن يكتمل validation. المشكلتان مستقلتان، ولذلك reveal الصحيح وحده لم يكن كافيًا.
