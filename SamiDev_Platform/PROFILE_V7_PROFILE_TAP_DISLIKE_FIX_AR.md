# إصلاح V7 — فتح بروفايل الخصم وعدم الإعجاب

## ما تم إصلاحه

- عدم الإعجاب بعد المباراة يخصم نقطة واحدة من سمعة اللاعب.
- السمعة لا يمكن أن تنزل تحت صفر.
- الإعجاب يبقى +1 سمعة.
- لا يزال التقييم مسموحًا مرة واحدة فقط لنفس الخصم في نفس المباراة.
- إصلاح الضغط على صورة الخصم داخل المباراة:
  - لم تعد مناطق الضغط تُحذف وتُنشأ كل 500ms.
  - أصبحت مناطق الضغط ثابتة ويتم تحديث مكانها فقط.
  - يتم فتح البروفايل من `pointerdown` لتجنب ضياع click على اللمس.
  - تمت إضافة fallback مباشر يعتمد على إحداثيات الضغط داخل canvas.
- البطاقة المفتوحة تعرض بيانات الحساب الفعلية: لاعب منذ، الفوز، السمعة، الصورة، الصداقة، السمعة والبلاغ.

## ملفات تغيرت

- `backend/social_platform.py`
- `game/player-profile-ui.js`
- `tests/player_profile_social_regression.py`
- `tests/player_profile_click_regression.py` (جديد)

## التحقق

- `profile_ui_regression.py`: PASS
- `player_profile_social_regression.py`: PASS
- `player_profile_click_regression.py`: PASS
- `profile_game_avatar_regression.py`: PASS
- `profile_win_stats_regression.py`: PASS
- `avatar_exit_regression.py`: PASS
- `platform_v1_regression.py`: PASS
- GameHost conformance: 369/369
- `game/main.js` لم يتغير.
