# ملخص إصلاح مشكلة الدور والشاشة البيضاء

## تم إصلاحه

- منع resize البصري من إلغاء turn timer داخل `main.js` عبر `_syncCalledFlag`.
- فحص authority أصبح يقارن `turn + sequence + gameOver` بدل `sequence` فقط.
- الاحتفاظ بأحدث authority mismatch وإعادة فحصه بعد animation/snapshot بدل إسقاطه.
- تمرير `authorityEpoch/revision` من GameHost إلى المتصفح لمنع state قديمة من التغلب على الحديثة.
- resync يسحب checkpoint حية من GameHost أولًا، مع Store fallback.
- إضافة `snapshotRevision` للـStore حتى snapshot أحدث بنفس moveCount لا تضيع.
- إصلاح collapsed Canvas startup race؛ لا يختفي loader قبل Surface صالحة.
- إضافة ResizeObserver مع حماية من early-observer poisoning قبل تحميل `main.js`.
- retry محدود إذا فشل أول draw بدل فقدان frame request نهائيًا.
- WebGL context loss/restore recovery.
- replay لا يعامل world-settle timeout كنجاح.
- إزالة waiting-room listeners بعد بدء المباراة.
- إصلاح `/platform/` 404.
- منع mixed JS versions عبر cache policy و`main.js?v=<sha>`.

## إثبات رئيسي

اختبار يستخدم `main.js` الحقيقي أعاد إنتاج الحالة القديمة:

```text
serverTurn=1
brokenClientTurn=0
sameSequenceBroken=true
```

ثم مع الإصلاح:

```text
serverTurn=1
repairedClientTurn=1
sameSequenceRepaired=true
```

## main.js

لم يتغير. SHA-256:

`f4c0ceb9e4eedfcf161848d33f673dfd26ce848be9ce556c01e3d23410351d2b`

## الاختبارات

- GameHost conformance: **369/369 PASS**.
- race/authority/resync/timeout/alarm/state/striker regression: PASS.
- Python platform/store/authority/live-resync regression: PASS.
- Gateway + GameHost + WebSocket integration: PASS.
- JS syntax + Python compile: PASS.

راجع `FORENSIC_AUDIT_AR.md` للتفاصيل والمخاطر المتبقية.
