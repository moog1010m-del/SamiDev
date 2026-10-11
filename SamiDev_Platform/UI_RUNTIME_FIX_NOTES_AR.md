# إصلاحات واجهة اللعبة والـ Runtime

تم الإصلاح بدون تعديل `game/main.js`.

## ما تم إصلاحه

- إيقاف حلقة `resize` غير المنتهية في `game/chat-ui.js`؛ لم يعد معالج `resize` يطلق حدث `resize` جديد كل frame.
- جعل إشعار تغيير حجم اللعبة من واجهة الشات coalesced ومرة واحدة عند تغير التخطيط الحقيقي.
- منع `game/browser-runtime.js` من إرسال `Surface Change` إذا لم تتغير أبعاد السطح فعليًا.
- تجاهل القياسات المؤقتة المنهارة (مثل `1x1`) بدل مزامنة اللعبة عليها.
- بعد أي resync/synchronize تتم إعادة بث موضع الـ Striker الحالي عبر منطق اللعبة نفسه حتى يظهر بصريًا ولا يبقى `visible=false`.
- إيقاف Trace/Debug في الإنتاج. لتفعيلها أضف `?debug=1` إلى رابط اللعبة.
- إبقاء التحذيرات والأخطاء المهمة في الـ Console مع تقليل الضوضاء.
- منع طلب favicon الافتراضي المفقود حتى لا يبقى 404 في الـ Console.

## الاختبارات

نجحت الاختبارات التالية بعد التعديل:

- `node tests/striker_move_regression.js`
- `node tests/timeout_afk_regression.js`
- `node tests/client_resync_regression.js`
- `node tests/state_checkpoint_regression.js`
- `python tests/platform_v1_regression.py`

SHA256 لملف `game/main.js` بقي كما هو:

`f4c0ceb9e4eedfcf161848d33f673dfd26ce848be9ce556c01e3d23410351d2b`
