# SamiDev iOS

على iOS التوزيع العادي لتطبيقات المتجر يعتمد WebKit/WKWebView، لذلك هذا القالب يستخدم WKWebView مع Cookie Store مشترك داخل التطبيق. أنشئ مشروع iOS App في Xcode باسم SamiDev ثم استبدل ملفي Swift بهذين الملفين، وعدّل الدومين.

هذا ليس Gecko/Chromium لأن iOS له قيود مختلفة عن Android. المنصة نفسها تبقى Responsive والمباراة Canvas/WebSocket كما هي.

أضف إلى Info.plist مفتاح String باسم `SamiDevPlatformURL` وقيمته عنوان نطاق المنصة الفعلي عبر HTTPS. إن غاب أو كان غير صالح تظهر رسالة إعداد، دون طلب شبكة إلى دومين تجريبي.
