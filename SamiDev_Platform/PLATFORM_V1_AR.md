# SamiDev Platform V1

## الموجود فعليًا

- Register / Login / Logout بجلسة HttpOnly cookie.
- كلمات المرور PBKDF2-SHA256 مع salt منفصل لكل حساب.
- أسماء مستخدمين فريدة وغير حساسة لحالة الأحرف.
- Lobby يعرض الغرف الحقيقية الموجودة في MemoryStore أو RedisStore.
- فلترة الغرف حسب 1v1 / 2v2 / انتظار / بدأت.
- إنشاء غرفة من اللوبي والدخول إليها بنقرة واحدة.
- Game Ticket قصير العمر وأحادي الاستخدام لربط حساب المنصة باتصال اللعبة.
- عند إعادة WebSocket الاتصال يمكن استخدام Session Cookie، لذلك لا ينكسر reconnect بعد استهلاك الـGame Ticket.
- Friends + incoming requests + accept/reject/remove + user search + online presence.
- Admin / Moderator: إحصائيات، قائمة مستخدمين، ban/unban. Admin فقط يستطيع تغيير roles.
- Redis AOF الحالي يخزن بيانات المنصة في الإنتاج بدون إضافة قاعدة بيانات جديدة.
- واجهة Responsive للكمبيوتر والهاتف.

## مسارات مهمة

- `/platform/` المنصة.
- `/index.html?...` شاشة/محرك اللعبة الحالي.
- `/api/*` REST للمنصة.
- `/ws` WebSocket للمباراة.

## أول مدير

في `.env` ضع:

```env
SAMIDEV_ADMIN_USERNAME=admin
SAMIDEV_ADMIN_PASSWORD=ضع_هنا_كلمة_مرور_قوية
```

يتم إنشاء الحساب الإداري عند بدء السيرفر لأول مرة إذا لم يكن موجودًا.

## التشغيل

لإنتاج Docker استخدم نفس أوامر المشروع السابقة بعد تحديث `.env`. `SAMIDEV_REQUIRE_GAME_AUTH=1` مفعّل في المثال حتى لا يمكن دخول اللعب Online بدون حساب.

## ملاحظات V1

- Presence حاليًا مبني على TTL (heartbeat) وليس نظام presence event-bus مستقل.
- قائمة اللوبي تعمل Polling كل ~3.5 ثوانٍ؛ هذا مناسب لأول إصدار و1000 لاعب، ويمكن تحويلها لاحقًا إلى SSE/WebSocket events.
- Ban يمنع الجلسات/الاتصالات الجديدة؛ فصل Socket موجود بالفعل كآلية في السيرفر ويمكن ربطه بالـBan لاحقًا لقطع اللاعب في نفس اللحظة.
- Android/iOS الموجودان قوالب مصدر وليسا APK/IPA مبنيين داخل هذه الحزمة.
