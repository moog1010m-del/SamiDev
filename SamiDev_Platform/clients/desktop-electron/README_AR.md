# SamiDev Desktop — Chromium

هذا العميل يستخدم Electron، وبالتالي اللعبة والمنصة تعملان داخل Chromium مضمّن فعليًا، وليس WebView النظام.

تشغيل التطوير:

```bash
npm install
SAMIDEV_PLATFORM_URL=https://YOUR_REAL_HOST/platform/ npm start
```

بناء الحزم:

```bash
npm run dist
```

ينتج Windows/macOS/Linux حسب نظام البناء المتاح.

الحزمة المبنية تتطلب ضبط `SAMIDEV_PLATFORM_URL` على HTTPS الحقيقي؛ لا يوجد عنوان إنتاج افتراضي. localhost متاح للتطوير غير المحزّم فقط.

استبدل YOUR_REAL_HOST بنطاقك الحقيقي قبل تنفيذ المثال.
