# إصلاح V11 — منطقة ضغط Native للأفاتار

## السبب
النسخ V7–V9 اعتمدت على مناطق HTML فوق الـcanvas، وV10 وصل `SamiDev.showProfile` بشكل صحيح، لكن بقيت المشكلة قبل هذا الجسر: منطقة الضغط الأصلية الخاصة بـ `ImageNode` لم تكن موثوقة في Web build، لذلك المستخدم قد يرى الأفاتار دون أن يلتقط المحرك اللمسة عليه.

## الإصلاح
تم تعديل `game/main.js` نفسه داخل كلاس `Avatar` وإضافة Node تفاعل Native مستقل لكل مقعد:

- الاسم الداخلي: `AVATAR_PROFILE_TAP_<seat>`
- المقاس: `180 × 180` وحدة.
- يقع في مركز الأفاتار نفسه.
- هو آخر child داخل Avatar حتى تكون له أولوية hit-test على عناصر الأفاتار الأخرى.
- يستخدم `onDrag(... status === "end")`، وهو نفس مسار الإدخال المستخدم في عناصر تحكم اللعبة التفاعلية، ثم يستدعي `_onImageTap()` الأصلي.
- `_onImageTap()` يستمر إلى `SamiDev.showProfile(seat)` ثم `SamiDevPlayerProfileUI.openSeat(seat)`.

لم تعد هناك حاجة لأي DOM hit-area أو حساب إحداثيات تقديري للأفاتارات.

## GameHost
بما أن `main.js` تغير عمدًا، تم تحديث SHA-256 المسموح به في GameHost وDocker والاختبارات دون تعطيل التحقق الأمني.

SHA-256 الجديد لـ `game/main.js`:

`a1fc9c5b3d1da91ea6999951eae0691f2346139e10ea16567914542b2afda45c`

## الاختبارات
- Profile native hit-target regression: PASS
- Player profile social regression: PASS
- Profile game avatar regression: PASS
- Avatar/exit regression: PASS
- Profile win stats regression: PASS
- Profile UI regression: PASS
- GameHost conformance: 369/369 PASS
- Alarm authority: PASS
- AFK timeout: PASS
- Turn resize race: PASS
- Striker move: PASS
- Client resync: PASS
- Turn authority: PASS
- State checkpoint: PASS
- Browser runtime race: PASS
