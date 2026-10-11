# SamiDev Android — GeckoView

هذا العميل لا يستخدم Android System WebView. شاشة المنصة واللعبة تعمل داخل GeckoView (محرك Firefox المضمّن).

قبل البناء عدّل `PLATFORM_URL` في `app/build.gradle.kts` إلى HTTPS الخاص بك. نسخة GeckoView مثبتة في `gradle.properties`؛ إذا تغيرت إحداثيات Maven عند Mozilla حدّث `geckoviewVersion` لأحدث Stable.

البناء:

```bash
./gradlew assembleRelease
```

> لم يتم تضمين Gradle Wrapper binaries داخل الحزمة؛ افتح المشروع في Android Studio أو أنشئ wrapper محليًا.
