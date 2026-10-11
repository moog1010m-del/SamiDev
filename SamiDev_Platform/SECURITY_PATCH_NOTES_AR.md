# باتش الحماية والتكامل — SamiDev

هذه ملاحظات باتش سابق. تفاصيل إصلاحات اللعب بتاريخ 8 أكتوبر 2026 موجودة في `GAME_SECURITY_FIX_AR.md`.

هذا الباتش لا يغيّر `game/main.js` ولا قواعد/فيزياء اللعبة. التغييرات محصورة في دورة الاتصال والـ Gateway/GameHost والتشغيل.

## ما تم إصلاحه

- منع الحركة قبل اكتمال `runtime_ready` لكل المقاعد (`MATCH_NOT_READY`).
- منع WebSocket واحد من إنشاء/دخول غرفة ثانية وترك لاعب شبح (`ALREADY_IN_ROOM`).
- إضافة `connectionEpoch` لكل مقعد. إعادة الاتصال ترفع الرقم، تغلق الاتصال القديم، والـ GameHost يرفض الجيل القديم بنفسه.
- جعل تحديث reconnect في Redis ذريًا حتى لا ينتج اتصالان بنفس الجيل عند reconnect متزامن.
- إضافة lease للـ GameHost: `authorityShard` + `authorityEpoch` + `authorityRevision`.
- تثبيت الغرفة على shard مخزّن بدل إعادة حساب shard بصمت عند تغير قائمة GameHosts.
- أحداث GameHost تحمل epoch/revision، وRedis يقبل كل revision مرة واحدة فقط؛ هذا يزيل تكرار fanout عبر 3 Gateways ويرفض أحداث authority قديمة.
- منع snapshot authority أقدم من الكتابة فوق snapshot أحدث عند تساوي `moveCount` بواسطة `snapshotRevision`.
- إضافة مفتاح خدمة داخلي بين Gateway وGameHost (`X-SamiDev-Service-Key`).
- إخفاء stack trace الداخلي من استجابات GameHost مع إبقائه في سجل السيرفر.
- تحقق صارم من room code وreconnect token.
- limits مستقلة لإنشاء/دخول الغرف بالإضافة إلى limit للـ WebSocket في nginx.
- حماية `/metrics` للشبكات الخاصة فقط في nginx.
- إضافة security headers أساسية وCSP محافظة.
- إزالة استخدام `innerHTML` من مسار خطأ المتصفح.
- تثبيت إصدارات مكتبات Python المباشرة على نسخ محددة ومختبرة بدل ranges متغيرة.
- إضافة مثال TLS/WSS للإنتاج. الشهادة والدومين لا يمكن تضمينهما في المشروع ويجب ربطهما عند النشر.

## متغير مهم قبل الإنتاج

غيّر القيمة الافتراضية حتمًا:

```env
SAMIDEV_GAMEHOST_SERVICE_KEY=ضع_هنا_قيمة_عشوائية_طويلة_جداً
```

القيمة الافتراضية الموجودة في الكود/Compose مخصصة فقط لعدم كسر التشغيل المحلي الحالي.

## TLS

`docker-compose.yml` الحالي يبقى HTTP على `localhost:8088` حتى يظل اختبار التطوير والـ load test يعملان مباشرة. قبل فتح الخدمة على الإنترنت، استخدم TLS termination (Cloudflare/ALB/Reverse Proxy) أو عدّل إعداد nginx بالاعتماد على `deploy/nginx/nginx.tls.example.conf` وشهادتك الحقيقية.
