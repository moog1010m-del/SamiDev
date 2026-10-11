# حالة بناء SamiDev Platform V1

## تم تنفيذه واختباره

- تسجيل حساب / تسجيل دخول / خروج بجلسة HttpOnly.
- Game Ticket أحادي الاستخدام قصير العمر لفتح المباراة بدون تمرير كلمة المرور للعبة.
- WebSocket يسترجع هوية الحساب من الجلسة عند إعادة الاتصال.
- Lobby يعرض الغرف الحقيقية الموجودة في Store، مع إنشاء ودخول 1v1 و2v2.
- اسم المضيف داخل الغرفة يأتي من الحساب الموثق وليس من اسم يرسله العميل.
- أصدقاء، طلبات صداقة، بحث مستخدمين وحالة Online/Offline.
- Admin: إحصائيات أساسية، مستخدمون، حظر/فك حظر، وأدوار.
- Redis مشترك بين الـGateways للحسابات والجلسات والوجود الاجتماعي.
- لعبة SamiDev وGameHost بقيا منفصلين عن طبقة المنصة.

## اختبارات نهائية

- `python tests/platform_v1_regression.py` : PASS
- `node tests/gamehost_conformance.js` : 369/369 PASS
- Python compile: PASS (`backend/app.py`, `backend/store.py`, `backend/social_platform.py`)
- JavaScript syntax: PASS (`game/platform/platform.js`, `game/samidev-network.js`)

## عملاء المنصات

- `clients/desktop-electron`: مصدر Electron/Chromium جاهز للتثبيت والبناء بعد `npm install`.
- `clients/android-geckoview`: مشروع Android مصدر يستخدم GeckoView وليس Android System WebView. يحتاج Android Studio/Gradle وتهيئة الدومين النهائي قبل APK/AAB.
- `clients/ios-wkwebview`: قالب iOS مصدر بـWKWebView؛ يحتاج Xcode والتوقيع وBundle ID قبل IPA/TestFlight.

## قبل الإنتاج

- غيّر `SAMIDEV_ADMIN_PASSWORD` من القيمة المثال.
- شغّل خلف HTTPS/WSS.
- Redis في هذه النسخة يحمل بيانات الحسابات الاجتماعية؛ إن كنت ستضيف مشتريات/اقتصاد/سجل دائم، أضف PostgreSQL أو قاعدة دائمة مناسبة.
