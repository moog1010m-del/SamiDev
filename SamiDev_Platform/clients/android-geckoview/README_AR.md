# SamiDev Android — GeckoView

هذا العميل لا يستخدم Android System WebView. شاشة المنصة واللعبة تعمل داخل GeckoView (محرك Firefox المضمّن).

قبل البناء اضبط خاصية Gradle `samidevPlatformUrl` على عنوان HTTPS الخاص بك. نسخة GeckoView مثبتة في `gradle.properties`؛ إذا تغيرت إحداثيات Maven عند Mozilla حدّث `geckoviewVersion` لأحدث Stable.

البناء:

```bash
./gradlew assembleRelease
```

> لم يتم تضمين Gradle Wrapper binaries داخل الحزمة؛ افتح المشروع في Android Studio أو أنشئ wrapper محليًا.

ضبط العنوان الآن من خاصية Gradle `samidevPlatformUrl`، بتمرير `-PsamidevPlatformUrl=https://YOUR_REAL_HOST/platform/` مع أمر البناء. استبدل YOUR_REAL_HOST بنطاقك الفعلي. يفشل البناء إذا غاب العنوان أو لم يكن HTTPS صالحًا؛ لا يوجد رابط تجريبي افتراضي.
