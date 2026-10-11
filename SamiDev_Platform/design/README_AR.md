# مصادر الرسومات والصوتيات الجديدة

هذه الملفات تخص تحديث الكيرم وكرة الطاولة وكريزي 8. مصادر الصور المولدة ووصف توليدها محفوظة في `original-assets`، مع خرائط إحداثيات الأطالس اللازمة للمحرك. لا تحتوي هذه المصادر على قصاصات من الصور السابقة.

- `build_assets.cjs`: يقص الصور المولدة ويركب الأطالس، ويرسم أرقام الأوراق ورموز القواعد والأيقونات ومؤشرات الأنيميشن من أشكال ومسارات جديدة. يحتاج Node.js ومكتبة `sharp`.
- `build_football_assets.cjs`: يركب ملعب كرة الطاولة من العشب المولد، ويرسم الخطوط والمرميين ويجهز الكرة وتصميمي الفريقين وأطلس اللعبة، ثم ينسخ الملحقات المشتركة الجديدة. يُشغّل بعد `build_assets.cjs`.
- `build_audio.py`: يؤلف مؤثرات قصيرة باستخدام موجات ونبضات وضوضاء محسوبة، ويصدر AAC عبر `ffmpeg`. لا يأخذ عينات صوتية من التسجيلات السابقة.
- `original-assets/generation-prompts.json`: وصف التوليد النهائي، باستخدام أداة الصور المدمجة. الصور المولدة مرفقة؛ إعادة تركيب الأصول لا تعيد التوليد ولا تحتاج مفتاح API.

لإعادة البناء من مجلد المشروع:

```bash
npm install --prefix design
node design/build_assets.cjs
node design/build_football_assets.cjs
python design/build_audio.py
python tools/update_original_asset_index.py
python tools/update_ui_build.py
python tools/update_game_integrity.py
```

ملفات مصدر التصميم خارج مجلد `game` ولا تُحمّل إلى المتصفح أثناء اللعب. يجب تحديث سجل بصمات `ORIGINAL_ASSETS_MANIFEST.json` عمدًا عند اعتماد تعديل جديد على الرسومات؛ يفحص `tests/original_assets.py` تطابق النسخة المسجلة مع الملفات الفعلية.

بعد اعتماد البصمات، شغّل `python tests/verify_original_release.py` لفحوص المحركات والاتصال والأصول. يحفظ النتائج الفعلية في `ORIGINAL_ASSETS_TEST_REPORT.json`.
