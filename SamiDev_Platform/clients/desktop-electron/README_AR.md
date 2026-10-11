# SamiDev Desktop — Chromium

هذا العميل يستخدم Electron، وبالتالي اللعبة والمنصة تعملان داخل Chromium مضمّن فعليًا، وليس WebView النظام.

تشغيل التطوير:

```bash
npm install
SAMIDEV_PLATFORM_URL=https://game.example.com/platform/ npm start
```

بناء الحزم:

```bash
npm run dist
```

ينتج Windows/macOS/Linux حسب نظام البناء المتاح.
