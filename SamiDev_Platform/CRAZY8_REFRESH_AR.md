# تحديث كريزي 8: الكود والأصول

> هذا المستند يصف تحديث إزالة الهوية السابق. التحديث الأحدث استبدل جميع الوسائط وأضاف خلفيات جديدة للكيرم وكريزي 8؛ راجع `ORIGINAL_ASSETS_AR.md`.

هذه الحزمة هي المشروع الكامل، وتشمل دمج كريزي 8 مع الباك إند ثم تنظيف هويتها وتحديث رسومات الأوراق. فك ZIP كاملًا في مجلد جديد وشغّل `START_SAMIDEV.bat`؛ تفاصيل التشغيل في `README_AR.md`.

## التغييرات

- أزيلت أسماء الهوية القديمة من ملفات الكود والبيانات داخل `game/games/crazy8`، بما فيها أسماء الأنواع والدوال وحقول السمات.
- أزيلت استدعاءات المتجر والمشتريات والمراسلة وبث الموسيقى الخاصة بالمضيف السابق. لم تكن الحزمة تحتوي عنوان API خارجيًا خاصًا به؛ الربط الفعلي بالأونلاين يستخدم خدمات SamiDev المدمجة في المشروع.
- أفرغت كتالوجات الأشكال الاختيارية غير المتاحة، وأخفي مدخل متجر اللعبة القديم. بقي تصميم الأوراق الأساسي.
- حذف الشعار من بكسلات السبرايت شيت ومن وصف عناصره وكود رسم ظهر الورقة.
- عدلت الألوان المشبعة في الشيت الأساسي بتعتيم خفيف قدره 6%، مع الحفاظ على الرموز البيضاء وإحداثيات العناصر وأبعاد الصورة `1142×1071` وقنوات الشفافية خارج منطقة الشعار المحذوفة.
- أنشئ ظهر ورقة جديد بلون بنفسجي أغمق وزخرفة هندسية بسيطة، بدون كتابة أو علامة تجارية. حفظ في شيت مستقل بمقاس `164×228` وربط بمحمل الأصول وكود الرسم.
- التشابه البصري المطلوب هدف تصميمي تقريبي، وليس قياسًا رياضيًا لنسبة 80%. المقاسات وإحداثيات القص مطابقة لما يتوقعه محرك اللعبة.
- عطلت الموسيقى ومؤثرات اللعب التي لم تكن ملفاتها موجودة في المصدر المرفق، بدل محاولة تحميلها. بقيت الأصوات المحلية المتوفرة لإعدادات الواجهة وردود الفعل والدور.

## الأصول النهائية

| المسار داخل المشروع | الاستخدام |
| --- | --- |
| `game/games/crazy8/images/MainSheet.webp` | الشيت الأساسي بعد تعديل الألوان وحذف الشعار |
| `game/games/crazy8/images/CardBackSheet.webp` | ظهر الورقة الجديد |
| `game/games/crazy8/images/CardBackSheet.json` | إطار القص `card_back_clean` |
| `game/games/crazy8/__assets.json` | فهرس الأصول المحلية الموجودة فعليًا |

التنظيف المذكور يخص كريزي 8. الكيرم وكرة الطاولة تحتفظان بدمجهما الموجود في المنصة.

## التحقق

نجحت الاختبارات الثمانية المسجلة في `CRAZY8_TEST_REPORT.json`، ومنها 60 مباراة مكتملة بجميع تراكيب المقاعد والمؤقت والأوراق الخاصة، واختبارات HTTP/WebSocket بحسابات مؤقتة، وإعادة الاتصال والمشاهدة وخصوصية الأوراق واستعادة GameHost. نجحت اختبارات الكيرم وكرة الطاولة المشتركة أيضًا.

فحص جسر المتصفح تحقق من تحميل شيت ظهر الورقة الجديد وأن طلبات موارده محلية. يستخدم هذا الفحص WebGL وصوتًا محاكيين؛ الصور نفسها فُحصت بصريًا، لكن لم تُنفذ مباراة داخل متصفح رسومي فعلي. لم يُختبر Redis أو Docker أو تشغيل Windows في هذه البيئة.

## وصف إنشاء ظهر الورقة

استخدمت أداة إنشاء الصور المدمجة، مع الشيت الأصلي مرجعًا للأسلوب. قُص الناتج إلى حدود الشفافية وضُبط إلى مقاس الإطار النهائي، ثم حفظ داخل المشروع بالمسار المذكور أعلاه. النص النهائي المستخدم:

```text
Use case: precise-object-edit / game asset. The reference is a packed game sprite sheet; it is a STYLE REFERENCE ONLY, do not reproduce the whole sheet. Create ONE isolated rectangular playing-card BACK texture for integration into that sprite sheet. Match about 80% of the simple casual flat-to-soft-gradient visual style and original deep purple card panel in the reference (at x359,y476,166x230), but make it two subtle shades deeper/cooler, dark muted plum-indigo with a very subtle lavender inner outline, and a restrained small abstract geometric oval motif in the center. The main request is brand removal and a mild palette refresh. The back must have NO words, NO letters, NO numerals, NO brand logos, NO watermark. In particular do not place any company name or recognizable brand emblem. Keep the card entirely symmetrical, front-on orthographic, no perspective, no drop shadow, no 3D tilt, no scene, no other assets. One tall rectangle, aspect ratio exactly 166:230, with minimally rounded corners (radius approx 4 at final 166px width). Fill almost the full canvas while preserving a genuinely transparent tight margin outside the card. Clean edges, smooth broad colors that remain legible when reduced to 166x230 pixels. This must be a usable small game texture, not a mockup.
```
