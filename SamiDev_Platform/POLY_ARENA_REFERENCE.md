# مرجع المشروع المفتوح المصدر المستخدم في تصميم طبقة المنصة

تم بناء طبقة الحسابات/اللوبي/الأصدقاء/الإدارة في SamiDev بالاستفادة من **نمط معماري موجود في مشروع فعلي** وليس مكتبة منفردة:

- المشروع: **Poly Arena — cross-platform-multiplayer-game**
- المصدر: https://github.com/Ilyes-Jamoussi/cross-platform-multiplayer-game
- الترخيص المعلن في المستودع: **MIT**
- صاحب الحقوق كما يظهر في المستودع: © 2026 Ilyes Jamoussi and the Poly Arena contributors

Poly Arena يجمع في مشروع واحد Web + Flutter mobile + Electron desktop + backend authoritative، ويحتوي Accounts/Friends/Lobby/Chat/Admin. في هذه الحزمة لم يتم نسخ NestJS/Firebase ومحرك لعب Poly Arena فوق مشروع SamiDev؛ تم تكييف **نفس فصل المسؤوليات** مع الباك الحالي حتى لا يصبح لدينا محركا لعب أو قاعدتا مصادقة متعارضتان:

- SamiDev GameHost/Gateway/Redis يبقى مسؤولًا عن المباراة.
- طبقة Platform الجديدة تستخدم Redis الموجود للحسابات والجلسات والأصدقاء.
- Game Ticket قصير العمر يربط حساب المنصة باتصال اللعبة.
- Electron يوفر Chromium للديسكتوب.
- Android scaffold يستخدم GeckoView بدل Android System WebView.

هذا الملف للتوثيق ونَسب المرجع. لم يتم إدخال كود Poly Arena كاملًا داخل الحزمة؛ المقصود هو الاعتماد على المشروع كمرجع معماري عملي مع إبقاء كود SamiDev متماسكًا بدل دمج Stack كامل ثانٍ.
