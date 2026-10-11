# V20 — ترتيب غرف اللعب + المشاهدة + حذف المباراة المنتهية من الروم

## ما تم التحقق منه قبل التنفيذ
- `game/main.js` يحتوي دعمًا صريحًا لوضع المشاهد عبر `isLocalObserver()`.
- عند تشغيل GameLogic مع `localSeat = -1` يتعرّف المحرك على العميل كمشاهد، ولا يعتبره Server.
- تم اختبار أن نسخة المشاهد تستطيع تطبيق حركة لاعب واردة بدون إرسال حركة منها.

## التغييرات
- إضافة `watch_room` في الباكند بدون حجز Seat.
- المشاهد يستخدم `seat = -1` وحالة `spectator = true`.
- اتصال المشاهد Read-only: لا يسمح بإرسال حركات أو شات المباراة، ويسمح بالمزامنة والخروج.
- الأحداث المخصصة حسب المقعد تدفع المشاهد لطلب authoritative resync بدل استخدام كشف خاص بمقعد لاعب.
- دعم المشاهد في وضع Redis متعدد العقد عبر تسجيل node المشاهد ضمن الغرفة.
- إضافة زر `مشاهدة` للمباراة الجارية في الروم.
- إعادة ترتيب صفوف المباريات على الكمبيوتر بدون horizontal overflow.
- المباراة المنتهية تُعلّم `finished` وتُزال فورًا من قائمة الروم العامة، بينما تبقى حالة المباراة مؤقتًا لتكملة شاشة النهاية والرجوع.
- المشاهد عند نهاية المباراة يرجع للروم بدون نافذة تقييم لاعبين.

## أمان المشاهدة
- المشاهد لا يملك Seat ولا Token لاعب.
- `move` مرفوض للمشاهد بكود `SPECTATOR_READ_ONLY`.
- المشاهد لا يدخل في roster اللاعبين ولا يستهلك مقعدًا.
- مباراة منتهية ترفض مشاهدًا جديدًا بكود `MATCH_FINISHED`.

## اختبارات
- `SPECTATOR_LIFECYCLE_REGRESSION_PASS`
- main.js observer regression: PASS
- Community Hub: PASS
- Lobby rows: PASS
- V17 room cleanup: PASS
- V18 chat security: PASS
- Platform UI: PASS
- Room leave: PASS
- Avatar: PASS
- GameHost: 369/369
- Turn authority: PASS
- Timeout/AFK: PASS

## main.js
لم يتم تعديل `game/main.js` في V20.
SHA-256:
`a1fc9c5b3d1da91ea6999951eae0691f2346139e10ea16567914542b2afda45c`
