# SamiDev Authoritative Carrom Backend

هذه النسخة تنقل SamiDev من **Relay Multiplayer** إلى **Authoritative Game Server** فعلي.

## ما تغير؟

الحركة لم تعد تذهب مباشرة من اللاعب إلى بقية اللاعبين. المسار أصبح:

```text
Player -> SamiDev Gateway -> Headless main.js GameLogic -> Accept/Reject -> Broadcast
```

نفس `main.js` يعمل على السيرفر بـ:

```text
server === true
localSeat === undefined
```

وبالتالي القواعد، turn validation، sequence، timers، `serialize/deserialize` ومسار `WorldState / ServerTrust` تمر عبر GameLogic الموجود في اللعبة نفسها بدل إعادة كتابة قواعد Carrom يدويًا.

## أهم تغييرات الأمان

- حركة خارج الدور: **ترفض من GameLogic ولا يتم Broadcast لها**.
- Packet مكرر/sequence خاطئ: **يرفض**.
- `__info` وWorldState: يمران عبر Server GameLogic.
- Snapshot القادم من العميل: **يتم تجاهله** ولا يستطيع الكتابة فوق حالة Redis.
- Snapshot الرسمي للـreconnect/resync: يأتي من `GameLogic.serialize()` على GameHost.
- `main.js` مربوط ببصمة SHA-256؛ GameHost يرفض الإقلاع إذا تغير الملف بدون تحديث مقصود.
- Backend Docker يعمل بمستخدم non-root.

## GameHost موزع

Docker Compose يشغل افتراضيًا:

- 3 × SamiDev Gateway
- 3 × SamiDev Authoritative GameHost
- Redis
- Nginx

الغرف توزع على GameHosts باستخدام **Rendezvous Hashing**. إذا تغير عدد GameHosts، لا تنتقل كل الغرف؛ فقط جزء منها. والغرفة التي تصل إلى Shard جديد يمكن استعادتها من Snapshot السيرفر الموجود في Redis.

## تحسين مهم للذاكرة

في أول Prototype كنا نشغل VM كامل من `main.js` لكل Room، وهذا كان مكلفًا. النسخة الحالية تحمل `main.js` **مرة واحدة داخل كل GameHost** ثم تنشئ GameLogic instance مستقلة لكل غرفة من نفس constructor.

هذا حافظ على نفس منطق السيرفر مع تخفيض كبير في الذاكرة.

## الاختبارات المنفذة على النسخة الحالية

### Conformance للـGameHost

`tests/gamehost_conformance.js`:

- 60 تركيبة إعدادات.
- 369 check نجحت.
- 0 failures.
- server mode مؤكد.
- wrong-turn rejection مؤكد.
- duplicate sequence rejection مؤكد.
- server snapshot مؤكد.
- WorldState / ServerTrust path مؤكد.

راجع:

```text
AUTHORITY_TEST_REPORT.json
```

### WebSocket integration

تم اختبار عميلين حقيقيين ضد Gateway + GameHost:

1. P1 وP2 يدخلان نفس الغرفة.
2. GameHost يبدأ بـ`server=true`.
3. P1 يرسل start packet قانوني -> يقبل ويصل للطرفين.
4. P2 يرسل حركة مزورة وهو خارج دوره -> `MOVE_REJECTED` ولا تبث.
5. P2 يرسل Snapshot مزور -> `snapshot_ignored`.
6. resync يرجع Snapshot رسمي من Server GameLogic ولا يحتوي التعديل المزور.

### حمل Authoritative فعلي

على Node/Gateway واحدة + GameHost واحدة داخل بيئة البناء:

- 1000 لاعب 1v1 = 500 غرفة: **500/500 نجحت**؛ GameHost RSS بعد الاختبار النظيف ≈ **227 MB**.
- 1000 لاعب 2v2 = 250 غرفة: **250/250 نجحت**؛ GameHost RSS بعد الاختبار النظيف ≈ **154 MB**.
- اختبار 3 GameHost shards: 60 غرفة توزعت **22 / 14 / 24**، ونجحت 60/60.

هذه الاختبارات الآن تمر عبر `GameLogic.move()` على السيرفر؛ ليست أرقام Relay القديمة.

الأرقام المحلية ليست وعدًا لسعة VPS معين. السعة النهائية تعتمد على CPU/RAM والشبكة وطول المباريات وتردد WorldState، لذلك يجب إعادة benchmark على سيرفر الإنتاج.

## تشغيل التطوير

المتطلبات:

- Python 3.11+
- Node.js 22+

Windows:

```bat
START_WINDOWS_DEV.bat
```

Linux/macOS:

```bash
./START_MAC_LINUX_DEV.sh
```

المشغل يختار منافذ فارغة تلقائيًا حتى لا تتكرر مشكلة port 8080/8088، ثم يشغل GameHost والGateway ويفتح المتصفح.

## تشغيل Docker production topology

```bat
START_PRODUCTION_DOCKER.bat
```

ثم افتح:

```text
http://127.0.0.1:8088/
```

إيقاف:

```bat
STOP_PRODUCTION_DOCKER.bat
```

قبل النشر الحقيقي غيّر `SAMIDEV_ALLOWED_ORIGINS` إلى دومين SamiDev الحقيقي وأضف TLS/WSS.

## إعادة اختبارات GameLogic

```bash
node tests/gamehost_conformance.js
```

اختبار الحمل:

```bash
python tools/load_test.py --players 1000 --seats 2 --concurrency 100 --hold 0
```

2v2:

```bash
python tools/load_test.py --players 1000 --seats 4 --concurrency 100 --hold 0
```

## منصة الحسابات واللوبي

أضيفت Platform V1 فوق محرك اللعبة الحالي وتشمل تسجيل/دخول، جلسات مشتركة عبر Redis، Lobby يعرض الغرف الحقيقية، إنشاء/دخول الغرف، أصدقاء وطلبات صداقة وحالة اتصال، ولوحة Admin للأدوار والحظر والإحصائيات الأساسية. دخول المباراة يستخدم Game Ticket أحادي الاستخدام قصير العمر، بينما إعادة الاتصال تعتمد على جلسة الحساب + player token الموجودين أصلًا. راجع `PLATFORM_V1_AR.md`.

## قبل فتح الخدمة لعامة المستخدمين

1. تشغيل HTTPS/WSS حقيقي خلف الدومين النهائي وتغيير كلمة مرور الأدمن الافتراضية.
2. إضافة قاعدة بيانات دائمة إذا ستوجد عملات، مشتريات، سجل مباريات أو إحصائيات طويلة الأجل؛ Platform V1 تحفظ الحسابات الاجتماعية في Redis حاليًا.
3. Replay tests لمباريات كاملة وحالات Queen/Foul/AFK/Resign/Reconnect/GameOver.
4. Fuzz/mutation tests للبروتوكول.
5. Benchmark طويل متعدد Gateways + Redis + GameHost shards على هاردوير الإنتاج.
6. بناء وتوقيع عملاء Desktop/Android/iOS قبل التوزيع في المتاجر.

## ملكية SamiDev

الكود الجديد هنا — Gateways، GameHost orchestration، Redis integration، room routing، reconnect، deployment والتوسعة — هو طبقة SamiDev. `main.js` وأصول اللعبة الأصلية تبقى خاضعة لحقوق وترخيص صاحبها الأصلي؛ تغيير أسماء الواجهات لا يغير ملكيتها القانونية.

## Web Production + In-Room Chat

النسخة الحالية تعمل كتطبيق ويب مستقل. اسم اللاعب يأتي من واجهة اللعبة، وإعادة الاتصال تعتمد على room/player token، والدعوات روابط ويب مؤقتة أحادية الاستخدام، والشات داخل المباراة باقٍ كما هو.

`game/main.js` لم يتغير.
