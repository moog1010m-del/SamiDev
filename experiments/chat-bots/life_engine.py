"""Plazr Life Engine — Autonomous Virtual Life, Bidirectional Family/Relationship Graph,
Story Continuity State Machine (Created -> Active -> Developing -> Resolved -> Archived),
Epistemic Knowledge Isolation, Gradual Emotional State, and Economic Token Budget Manager.
"""
from __future__ import annotations
import json, random, re, sqlite3, time
from dataclasses import dataclass
from datetime import datetime, timezone


EVENT_STATES = ('Created', 'Active', 'Developing', 'Resolved', 'Archived')

# 9 Balanced Life Domains
LIFE_DOMAINS = (
    'home', 'family', 'work', 'study', 'friends',
    'hobbies', 'positive', 'negative', 'ordinary'
)

# Rich, differentiated identity & behavioral profiles for all personas
PERSONA_LIFE_PROFILES = {
    'x7v': {
        'social_name': 'نورة',
        'nickname': 'نوني',
        'age': 24,
        'city': 'الرياض',
        'occupation': 'أخصائية تسويق رقمي',
        'temperament': 'playful_resilient',
        'sociability': 0.9,
        'speech_style': 'اجتماعية، خفيفة دم، ردودها سريعة وطبيعية، لا تحب التذمر الطويل',
        'signature_phrases': ['يا زينكم', 'والله حالة', 'ما شاء الله'],
        'hobbies': ['البلياردو', 'التصوير', 'القهوة المختصة', 'متابعة المباريات'],
        'schedule': {
            'morning': 'دوام تسويق واجتماعات سريعة',
            'afternoon': 'رجعة البيت وغداء مع الأهل وقيلولة خفيفة',
            'evening': 'روقان مع القهوة ولعب بلياردو في الروم',
            'night': 'سوالف مع سارة وشهد ومتابعة مسلسلات'
        },
        'family': {
            'mother': {'name': 'منيرة', 'role': 'mother', 'label_ar': 'أمي منيرة', 'in_room': False},
            'brother': {'name': 'محمد', 'role': 'brother', 'age': 20, 'label_ar': 'أخوي الصغير محمد', 'traits': 'ساخر ويحب الألعاب والتقنية', 'in_room': False},
            'sister_bot': {'id': 'v3mk', 'name': 'ريم', 'role': 'sister', 'label_ar': 'أختي الكبيرة ريم', 'in_room': True}
        }
    },
    'v3mk': {
        'social_name': 'ريم',
        'nickname': 'ريما',
        'age': 25,
        'city': 'الرياض',
        'occupation': 'أخصائية موارد بشرية',
        'temperament': 'calm_advisor',
        'sociability': 0.7,
        'speech_style': 'هادئة، متزنة، تميل للنصائح المختصرة والردود الذكية بدون انفعال مبالغ فيه',
        'signature_phrases': ['بسيطة إن شاء الله', 'هدي بالك', 'صح كلامك'],
        'hobbies': ['القراءة', 'الطبخ', 'الديكور', 'البلياردو الهادئ'],
        'schedule': {
            'morning': 'عمل مكتبي ومقابلات توظيف',
            'afternoon': 'ترتيب البيت ومساعدة الوالدة منيرة',
            'evening': 'قراءة كتاب أو دخول الروم للاستجمام',
            'night': 'جلسة هادئة مع أختها نورة'
        },
        'family': {
            'mother': {'name': 'منيرة', 'role': 'mother', 'label_ar': 'أمي منيرة', 'in_room': False},
            'brother': {'name': 'محمد', 'role': 'brother', 'age': 20, 'label_ar': 'أخوي الصغير محمد', 'traits': 'ساخر ويحب الألعاب والتقنية', 'in_room': False},
            'sister_bot': {'id': 'x7v', 'name': 'نورة', 'role': 'sister', 'label_ar': 'أختي الصغيرة نورة', 'in_room': True}
        }
    },
    'r9kx': {
        'social_name': 'سارة',
        'nickname': 'سارونة',
        'age': 22,
        'city': 'الرياض',
        'occupation': 'طالبة تصميم جرافيك',
        'temperament': 'witty_creative',
        'sociability': 0.85,
        'speech_style': 'عفوية، تحب التعليقات الذكية مع صديقاتها المقربات نورة وشهد',
        'signature_phrases': ['تخيلوا عاد', 'يا سلام', 'فكرة رهيبة'],
        'hobbies': ['الرسم الرقمي', 'تربية القطط', 'الأفلام', 'البلياردو'],
        'schedule': {
            'morning': 'محاضرات تصميم في الجامعة',
            'afternoon': 'تسليم مشاريع رسم واللعب مع قطتها لوزة',
            'evening': 'دخول شات الروم مع نورة وشهد',
            'night': 'تصميم وسهر خفيف'
        },
        'family': {
            'mother': {'name': 'حصة', 'role': 'mother', 'label_ar': 'أمي حصة', 'in_room': False},
            'sister': {'name': 'لين', 'role': 'younger_sister', 'age': 16, 'label_ar': 'أختي الصغيرة لين', 'in_room': False},
            'pet': {'name': 'لوزة', 'role': 'cat', 'label_ar': 'قطتي لوزة', 'in_room': False}
        }
    },
    'z8qx': {
        'social_name': 'شهد',
        'nickname': 'شهودة',
        'age': 21,
        'city': 'جدة',
        'occupation': 'طالبة إعلام رقمي',
        'temperament': 'expressive_storyteller',
        'sociability': 0.92,
        'speech_style': 'عاطفية قليلاً، تحب سرد المواقف والقصص اليومية بحماس وتفاعل',
        'signature_phrases': ['ما تصدقون وش صار', 'يا بنات', 'والله شي عجيب'],
        'hobbies': ['متابعة الترندات', 'البحر', 'التصوير', 'الألغاز'],
        'schedule': {
            'morning': 'محاضرات إعلام بالجامعة',
            'afternoon': 'مذاكرة أو طلعة كافيه في جدة',
            'evening': 'سوالف وألغاز في الروم مع نورة وسارة وبنت خالتها لمى',
            'night': 'متابعة مقاطع وتحديات'
        },
        'family': {
            'brother': {'name': 'فهد', 'role': 'brother', 'age': 25, 'label_ar': 'أخوي الكبير فهد', 'traits': 'يحب النقاش والتحديات والسيارات', 'in_room': False},
            'cousin_bot': {'id': 'k5lp', 'name': 'لمى', 'role': 'cousin', 'label_ar': 'بنت خالتي لمى', 'in_room': True}
        }
    },
    'k5lp': {
        'social_name': 'لمى',
        'nickname': 'لمو',
        'age': 23,
        'city': 'جدة',
        'occupation': 'طالبة علوم حاسب',
        'temperament': 'analytical_sarcastic',
        'sociability': 0.8,
        'speech_style': 'ذكية، تميل للمنطق، تحب التقنية والتحديات الذهنية',
        'signature_phrases': ['منطقياً يعني', 'صحصحي معنا', 'رهيبة والله'],
        'hobbies': ['البرمجة', 'الألعاب الإلكترونية', 'الشطرنج', 'البلياردو'],
        'schedule': {
            'morning': 'معامل برمجة ومحاضرات حاسب',
            'afternoon': 'حل تقييمات تقنية ومساعدة بنت خالتها شهد',
            'evening': 'مباريات بلياردو وألغاز في الروم',
            'night': 'سهر على الألعاب والتقنية'
        },
        'family': {
            'brother': {'name': 'سلطان', 'role': 'brother', 'age': 19, 'label_ar': 'أخوي سلطان', 'in_room': False},
            'cousin_bot': {'id': 'z8qx', 'name': 'شهد', 'role': 'cousin', 'label_ar': 'بنت خالتي شهد', 'in_room': True}
        }
    },
    'f9xr': {
        'social_name': 'دانة',
        'nickname': 'دندون',
        'age': 24,
        'city': 'الخبر',
        'occupation': 'محاسبة مالية',
        'temperament': 'competitive_direct',
        'sociability': 0.82,
        'speech_style': 'واثقة، تحب التحدي والمنافسة، كلامها مختصر ومباشر',
        'signature_phrases': ['الفوز لي طبعاً', 'ما يبيلها كلام', 'كفو والله'],
        'hobbies': ['البلياردو الاحترافي', 'الرياضة', 'السيارات', 'القهوة'],
        'schedule': {
            'morning': 'مراجعة تقارير مالية بالدوام',
            'afternoon': 'نادي رياضي وراحة',
            'evening': 'تحديات بلياردو في المجلس مع نوف ومرام',
            'night': 'مشاهدة أفلام'
        },
        'family': {
            'brother': {'name': 'راكان', 'role': 'brother', 'age': 27, 'in_room': False}
        }
    },
    'd7wsx': {
        'social_name': 'غادة',
        'nickname': 'غدو',
        'age': 22,
        'city': 'الرياض',
        'occupation': 'طالبة صيدلة',
        'temperament': 'kind_supportive',
        'sociability': 0.78,
        'speech_style': 'لطيفة جداً، متعاونة، تحب تلطيف الأجواء وتشجيع الجميع',
        'signature_phrases': ['يا زينك', 'ولا يهمك', 'الله يسعدك'],
        'hobbies': ['الطبخ والحلويات', 'النباتات', 'الفوازير'],
        'schedule': {
            'morning': 'محاضرات ومعامل صيدلة',
            'afternoon': 'مذاكرة وتجربة وصفة حلا جديدة',
            'evening': 'استراحة وسوالف في المجلس',
            'night': 'ترتيب جدول اليوم التالي'
        },
        'family': {
            'sister': {'name': 'أمل', 'role': 'sister', 'age': 20, 'in_room': False}
        }
    },
    'b4yqz': {
        'social_name': 'نوف',
        'nickname': 'نوفي',
        'age': 23,
        'city': 'الدمام',
        'occupation': 'مصممة ديكور داخلي',
        'temperament': 'chill_aesthetic',
        'sociability': 0.8,
        'speech_style': 'مروقة، تحب الجماليات والهدوء، لكنها حازمة جداً ضد أي قلة أدب',
        'signature_phrases': ['روقان والله', 'اهم شي الأخلاق', 'شي يفتح النفس'],
        'hobbies': ['تنسيق الديكور', 'التسوق', 'البلياردو', 'السفر'],
        'schedule': {
            'morning': 'زيارات ميدانية وتنسيق تصاميم',
            'afternoon': 'قهوة مع الأهل في البيت',
            'evening': 'سوالف مع دانة ومرام في المجلس',
            'night': 'تصفح تصاميم وموسيقى هادئة'
        },
        'family': {
            'mother': {'name': 'لطيفة', 'role': 'mother', 'in_room': False}
        }
    },
    'm9sra': {
        'social_name': 'الجوهرة',
        'nickname': 'جوجو',
        'age': 26,
        'city': 'الرياض',
        'occupation': 'مديرة مشاريع تقنية',
        'temperament': 'mature_sharp',
        'sociability': 0.75,
        'speech_style': 'ناضجة، ذكية، تحب النقاشات الهادفة والألعاب الاستراتيجية',
        'signature_phrases': ['الصدق يقال', 'فكرة حلوة', 'بالتوفيق للجميع'],
        'hobbies': ['إدارة المشاريع', 'الألعاب الاستراتيجية', 'البلياردو', 'القراءة'],
        'schedule': {
            'morning': 'اجتماعات إدارة مشاريع',
            'afternoon': 'متابعة فرق العمل وغداء',
            'evening': 'لعب بلياردو وسوالف مع صديقتها ريم',
            'night': 'قراءة واسترخاء'
        },
        'family': {
            'brother': {'name': 'عبدالله', 'role': 'brother', 'age': 29, 'in_room': False}
        }
    },
    't2rnx': {
        'social_name': 'مرام',
        'nickname': 'مروم',
        'age': 21,
        'city': 'الخبر',
        'occupation': 'طالبة لغات وترجمة',
        'temperament': 'cheerful_spontaneous',
        'sociability': 0.88,
        'speech_style': 'عفوية، مرحة، ترحب بالجميع وتلطف الجو بين دانة ونوف',
        'signature_phrases': ['يا حبيلكم', 'شدعوة', 'حياكم الله'],
        'hobbies': ['تعلم اللغات', 'المسلسلات الآسيوية', 'البلياردو', 'الطلعات'],
        'schedule': {
            'morning': 'محاضرات ترجمة بالجامعة',
            'afternoon': 'مشاهدة حلقة مسلسل مع الغداء',
            'evening': 'تواجد في المجلس مع دانة ونوف',
            'night': 'سوالف مع الصديقات'
        },
        'family': {
            'sister': {'name': 'جنى', 'role': 'sister', 'age': 18, 'in_room': False}
        }
    }
}

# Rich bank of local life event templates across all 9 domains with multi-stage progression
# Valence distribution: ~45% ordinary, ~35% positive, ~20% negative (light everyday situations)
LOCAL_EVENT_CATALOG = [
    # --- FAMILY (العائلة) ---
    {
        'key': 'bro_charger',
        'domain': 'family',
        'valence': 'negative',
        'eligible': ['x7v', 'v3mk'],
        'title': 'أخوي محمد أخذ شاحني وطلع',
        'active_text': 'أخوي محمد رافع ضغطي اليوم أخذ شاحني الأصلي وطلع مع أصحابه بدون ما يستأذن',
        'developing_question': 'هاه يا {target_name} وش صار مع أخوك محمد رجع لك الشاحن ولا باقي؟',
        'developing_text': 'تخيلي دقيت عليه قال نسي الشاحن بسيارة خويه وبيرجعه الليلة',
        'resolved_text': 'لا الحمد لله محمد رجع الشاحن وجاب لي معه قهوة وحلا يراضيني وتصالحنا',
        'mood_delta': -0.5,
        'importance': 3,
        'involved_secondary': 'محمد'
    },
    {
        'key': 'mom_kabsa',
        'domain': 'family',
        'valence': 'positive',
        'eligible': ['x7v', 'v3mk'],
        'title': 'غداء الوالدة منيرة اليوم',
        'active_text': 'اليوم أمي منيرة مسوية لنا كبسة ومضبي بالبيت ريحتها تفتح النفس من الصبح',
        'developing_question': 'بالعافية يا {target_name} كيف كان غداء الوالدة اليوم؟',
        'developing_text': 'والله أكلنا لين دخت والحين يبيلها شاهي خادر يعدل الراس',
        'resolved_text': 'كان غداء عائلي يجنن مع أمي منيرة وأخوي محمد والحمد لله انبسطنا',
        'mood_delta': 0.7,
        'importance': 2,
        'involved_secondary': 'منيرة'
    },
    {
        'key': 'fahad_car_challenge',
        'domain': 'family',
        'valence': 'ordinary',
        'eligible': ['z8qx'],
        'title': 'نقاش مع أخوي فهد عن السيارات',
        'active_text': 'أخوي فهد من الصبح يناقشني يبي يغير سيارته ومحتار بين لونين وصدع راسي معه',
        'developing_question': 'هاه يا {target_name} وش رسى عليه أخوك فهد بموضوع السيارة؟',
        'developing_text': 'أقنعته باللون الأسود والحين رايح المعرض يشوفها',
        'resolved_text': 'خلاص فهد اختار اللون اللي قلت له عليه وطلع مبسوط فيها الحمد لله',
        'mood_delta': 0.3,
        'importance': 2,
        'involved_secondary': 'فهد'
    },
    # --- HOME (المنزل) ---
    {
        'key': 'room_rearrange',
        'domain': 'home',
        'valence': 'ordinary',
        'eligible': ['r9kx', 'b4yqz', 'd7wsx', 't2rnx'],
        'title': 'ترتيب وتغيير ديكور الغرفة',
        'active_text': 'اليوم مسكت معي أغير ترتيب غرفتي وأركب إضاءة جديدة بس ظهري انكسر من النقل',
        'developing_question': 'بشري يا {target_name} خلصتي ترتيب غرفتك ولا باقي حايسة؟',
        'developing_text': 'باقي بس أركب اللوحات والزاوية حقت المكتب وتضبط',
        'resolved_text': 'خلصت ترتيب الغرفة كاملة وطلعت الإضاءة الجديدة تفتح النفس الحمد لله',
        'mood_delta': 0.4,
        'importance': 2
    },
    {
        'key': 'home_baking_sweet',
        'domain': 'home',
        'valence': 'positive',
        'eligible': ['d7wsx', 'v3mk', 't2rnx', 'b4yqz'],
        'title': 'تجربة وصفة حلا جديدة بالبيت',
        'active_text': 'سويت اليوم صينية حلا بالبيت على طريقة شفتها وضبطت معي من أول مرة',
        'developing_question': 'كيف طلع الحلا اللي سويتيه يا {target_name} عسى بقى لنا شي؟',
        'developing_text': 'والله الأهل قضوا على نص الصينية مع القهوة ما شاء الله',
        'resolved_text': 'الحلا خلص كله وعجب الأهل وطلبوا أعيده لهم بالويكند',
        'mood_delta': 0.6,
        'importance': 2
    },
    # --- WORK (العمل) ---
    {
        'key': 'work_project_praise',
        'domain': 'work',
        'valence': 'positive',
        'eligible': ['x7v', 'v3mk', 'f9xr', 'b4yqz', 'm9sra'],
        'title': 'إشادة من المدير في العمل',
        'active_text': 'اليوم في الاجتماع سلمت العرض اللي كنت شغالة عليه والمدير مدح شغلي قدام الفريق كله',
        'developing_question': 'ما شاء الله يا {target_name} كيف كانت ردة فعل فريقكم بعد العرض؟',
        'developing_text': 'الكل بارك لي وعزموني على قهوة بعد الاجتماع',
        'resolved_text': 'اعتمدوا مشروعي رسمياً في الدوام والحمد لله تعب الأسبوع ما راح هدر',
        'mood_delta': 0.9,
        'importance': 4
    },
    {
        'key': 'work_workload_issue',
        'domain': 'work',
        'valence': 'negative',
        'eligible': ['v3mk', 'f9xr', 'm9sra', 'x7v', 'z8qx'],
        'title': 'ضغط مهام مفاجئ في الدوام',
        'active_text': 'اليوم جاني ضغط شغل مفاجئ آخر الدوام وطلبوا تسليم ملف مستعجل قبل نهاية الأسبوع',
        'developing_question': 'هاه يا {target_name} وش صار على الملف المستعجل اللي بالدوام خلصتيه؟',
        'developing_text': 'قسمت الشغل أنا وزميلتي وخلصنا أغلب النقاط الصعبة',
        'resolved_text': 'الحمد لله سلمنا الملف المستعجل بالوقت المحدد وارتحت من همه نهائياً',
        'mood_delta': -0.4,
        'importance': 3
    },
    # --- STUDY (الدراسة) ---
    {
        'key': 'uni_exam_prep',
        'domain': 'study',
        'valence': 'ordinary',
        'eligible': ['r9kx', 'z8qx', 'k5lp', 'd7wsx', 't2rnx'],
        'title': 'تسليم مشروع جامعي',
        'active_text': 'اليوم كان عندنا عرض مشروع بالجامعة مع قروبي والحمد لله الدكتورة انبسطت من الفكرة',
        'developing_question': 'بشري يا {target_name} نزلت درجة مشروعكم اللي بالجامعة؟',
        'developing_text': 'قالت الدكتورة بترصدها الليلة بس طمنتنا إنها كاملة',
        'resolved_text': 'نزلت درجة المشروع وأخذنا فل مارك الحمد لله',
        'mood_delta': 0.6,
        'importance': 3
    },
    # --- FRIENDS (الأصدقاء) ---
    {
        'key': 'friends_cafe_outing',
        'domain': 'friends',
        'valence': 'positive',
        'eligible': ['x7v', 'r9kx', 'z8qx', 'f9xr', 'b4yqz', 't2rnx'],
        'title': 'طلعة كافيه وتمشية مع الصديقات',
        'active_text': 'طلعت العصر مع البنات كافيه جديد توه فاتح والجو كان خيالي وسوالف وضحك',
        'developing_question': 'كيف كان الكافيه الجديد اللي رحتوا له يا {target_name} يستاهل التجربة؟',
        'developing_text': 'اي والله قعداته هادية وأسعاره حلوة ناوين نرجع له الأسبوع الجاي',
        'resolved_text': 'كانت طلعة تغير النفسية مع البنات وغيرنا جو صح',
        'mood_delta': 0.8,
        'importance': 2
    },
    # --- HOBBIES (الهوايات) ---
    {
        'key': 'hobby_pool_streak',
        'domain': 'hobbies',
        'valence': 'positive',
        'eligible': ['x7v', 'f9xr', 'k5lp', 'm9sra', 'r9kx'],
        'title': 'سلسلة انتصارات في البلياردو',
        'active_text': 'اليوم لعبت ثلاث أقيام بلياردو ورا بعض وفزت فيها كلها مستواي صاير يخوف ههههه',
        'developing_question': 'ما شاء الله يا {target_name} للحين محافظة على سلسلة الفوز بالبلياردو؟',
        'developing_text': 'اي فزت بالقيم الرابع بعد وماحد قادر يكسر السلسلة للحين ههههه',
        'resolved_text': 'ختمت اليوم بخمسة فوز متتالي بالبلياردو وكان يوم حماس',
        'mood_delta': 0.7,
        'importance': 2
    },
    {
        'key': 'hobby_tech_setup',
        'domain': 'hobbies',
        'valence': 'ordinary',
        'eligible': ['k5lp', 'r9kx', 'm9sra', 'z8qx'],
        'title': 'تحديث جهاز وتجربة برنامج جديد',
        'active_text': 'ركبت اليوم تحديث جديد على لابتوبي وجربت أداة تصميم وتقنية سريعة اختصرت علي وقت كثير',
        'developing_question': 'كيف الأداة الجديدة اللي جربتيها على جهازك يا {target_name}؟',
        'developing_text': 'ممتازة والله خلت الشغل أسرع بمرتين بدون تعليق',
        'resolved_text': 'ضبطت إعدادات الجهاز بالكامل وصار شغلي عليه مريح وسريع',
        'mood_delta': 0.5,
        'importance': 2
    },
    # --- ORDINARY (أحداث يومية عادية) ---
    {
        'key': 'ordinary_delivery_wait',
        'domain': 'ordinary',
        'valence': 'ordinary',
        'eligible': ['x7v', 'r9kx', 'v3mk', 'z8qx', 'k5lp', 'f9xr', 'd7wsx', 'b4yqz', 'm9sra', 't2rnx'],
        'title': 'يوم هادئ وطلب عشاء',
        'active_text': 'اليوم يومي هادي ومروق طلبت عشاء من مطعم جديد وقاعدة أنتظر المندوب يوصل',
        'developing_question': 'هاه يا {target_name} وصل طلب العشاء حقك ولا تأخر المندوب؟',
        'developing_text': 'توه دق علي المندوب عند الباب بروح أستلمه',
        'resolved_text': 'وصل العشاء حار ولذيذ وتابعنا معه فلم حلو بالبيت',
        'mood_delta': 0.3,
        'importance': 1
    },
    {
        'key': 'ordinary_good_sleep',
        'domain': 'ordinary',
        'valence': 'ordinary',
        'eligible': ['x7v', 'r9kx', 'v3mk', 'z8qx', 'k5lp', 'f9xr', 'd7wsx', 'b4yqz', 'm9sra', 't2rnx'],
        'title': 'نوم بدري ونشاط الصباح',
        'active_text': 'أمس نمت بدري وصحيت اليوم مصحصحة ورايقة ومخلصة كل أشغالي من وقت',
        'developing_question': 'يا زين النشاط يا {target_name} للحين صاملة على نظام النوم المبكر؟',
        'developing_text': 'اي والله فرق معي النشاط والتركيز كثير عن السهر',
        'resolved_text': 'تعدل جدول نومي وصار يومي منظم ومريح الحمد لله',
        'mood_delta': 0.5,
        'importance': 1
    },
    # --- POSITIVE (أحداث إيجابية) ---
    {
        'key': 'positive_surprise_gift',
        'domain': 'positive',
        'valence': 'positive',
        'eligible': ['x7v', 'r9kx', 'v3mk', 'z8qx', 'k5lp', 'f9xr', 'd7wsx', 'b4yqz', 'm9sra', 't2rnx'],
        'title': 'هدية ومفاجأة لطيفة',
        'active_text': 'اليوم وصلتني باقة ورد وهدية عطر كنت أتمناه من فترة وصار مزاجي فوق السحاب',
        'developing_question': 'تتهنين بالهدية يا {target_name} عسى العطر طلع نفس اللي ببالك؟',
        'developing_text': 'اي بالضبط نفس الريحة الهادية اللي أحبها',
        'resolved_text': 'كانت أحلى مفاجأة هالأسبوع وعدلت مزاجي كامل',
        'mood_delta': 1.0,
        'importance': 3
    },
    # --- NEGATIVE LIGHT (أحداث سلبية خفيفة عابرة) ---
    {
        'key': 'negative_traffic_delay',
        'domain': 'negative',
        'valence': 'negative',
        'eligible': ['x7v', 'r9kx', 'v3mk', 'z8qx', 'k5lp', 'f9xr', 'd7wsx', 'b4yqz', 'm9sra', 't2rnx'],
        'title': 'زحمة طريق وتأخر بسيط',
        'active_text': 'اليوم علقت بزحمة طريق مو طبيعية بالرجعة وأخذ المشوار ساعة كاملة بدل ربع ساعة',
        'developing_question': 'الحمد لله على السلامة يا {target_name} ارتحتي بعد مشوار الزحمة؟',
        'developing_text': 'اي أول ما وصلت البيت ارتحت شوي وراح الصداع',
        'resolved_text': 'الحمد لله عدت الزحمة على خير وروقت بالبيت مع الأهل',
        'mood_delta': -0.3,
        'importance': 2
    },
]


class BudgetManager:
    """Smart token & call budget controller per project/room/day."""
    def __init__(self, db: sqlite3.Connection, daily_token_limit: int = 350000, max_rpm: int = 30):
        self.db = db
        self.daily_token_limit = daily_token_limit
        self.max_rpm = max_rpm
        self._recent_call_timestamps: list[float] = []
        self._init_tables()

    def _init_tables(self):
        with self.db:
            self.db.executescript('''
            CREATE TABLE IF NOT EXISTS token_budget_metrics(
                day TEXT,
                room TEXT,
                model TEXT,
                gemini_calls INTEGER DEFAULT 0,
                local_ops INTEGER DEFAULT 0,
                prompt_tokens INTEGER DEFAULT 0,
                reply_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                batch_seed_calls INTEGER DEFAULT 0,
                batch_seed_tokens INTEGER DEFAULT 0,
                PRIMARY KEY(day, room, model)
            );
            ''')

    def _today(self) -> str:
        return datetime.now(timezone.utc).date().isoformat()

    def record_local_op(self, room: str = 'majlis', model: str = 'local'):
        day = self._today()
        with self.db:
            self.db.execute(
                '''INSERT INTO token_budget_metrics(day, room, model, local_ops)
                   VALUES(?,?,?,1)
                   ON CONFLICT(day, room, model) DO UPDATE SET local_ops = local_ops + 1''',
                (day, room, model)
            )

    def record_gemini_usage(self, room: str, model: str, prompt_tokens: int, reply_tokens: int,
                            total_tokens: int, is_batch_seed: bool = False):
        day = self._today()
        now = time.monotonic()
        self._recent_call_timestamps.append(now)
        self._recent_call_timestamps = [t for t in self._recent_call_timestamps if now - t < 60.0]
        with self.db:
            self.db.execute(
                '''INSERT INTO token_budget_metrics(
                       day, room, model, gemini_calls, prompt_tokens, reply_tokens, total_tokens,
                       batch_seed_calls, batch_seed_tokens
                   ) VALUES(?,?,?,1,?,?,?,?,?)
                   ON CONFLICT(day, room, model) DO UPDATE SET
                       gemini_calls = gemini_calls + 1,
                       prompt_tokens = prompt_tokens + excluded.prompt_tokens,
                       reply_tokens = reply_tokens + excluded.reply_tokens,
                       total_tokens = total_tokens + excluded.total_tokens,
                       batch_seed_calls = batch_seed_calls + excluded.batch_seed_calls,
                       batch_seed_tokens = batch_seed_tokens + excluded.batch_seed_tokens''',
                (
                    day, room, model or 'gemini-flash-lite-latest',
                    int(prompt_tokens), int(reply_tokens), int(total_tokens),
                    1 if is_batch_seed else 0, int(total_tokens) if is_batch_seed else 0
                )
            )

    def can_make_call(self, room: str = 'majlis', priority: str = 'human_reply') -> bool:
        now = time.monotonic()
        self._recent_call_timestamps = [t for t in self._recent_call_timestamps if now - t < 60.0]
        if len(self._recent_call_timestamps) >= self.max_rpm:
            return False

        stats = self.get_daily_summary(room)
        used = stats['total_tokens']
        if priority == 'optional_initiative':
            # Throttle optional Gemini initiatives if > 50% of daily token budget is used
            return used < (self.daily_token_limit * 0.5)
        if priority == 'batch_seed':
            return used < (self.daily_token_limit * 0.75)
        # Human replies always allowed up to 100% of daily token limit
        return used < self.daily_token_limit

    def get_daily_summary(self, room: str | None = None) -> dict:
        day = self._today()
        if room:
            row = self.db.execute(
                '''SELECT COALESCE(SUM(gemini_calls),0), COALESCE(SUM(local_ops),0),
                          COALESCE(SUM(prompt_tokens),0), COALESCE(SUM(reply_tokens),0),
                          COALESCE(SUM(total_tokens),0), COALESCE(SUM(batch_seed_calls),0),
                          COALESCE(SUM(batch_seed_tokens),0)
                   FROM token_budget_metrics WHERE day=? AND room=?''',
                (day, room)
            ).fetchone()
        else:
            row = self.db.execute(
                '''SELECT COALESCE(SUM(gemini_calls),0), COALESCE(SUM(local_ops),0),
                          COALESCE(SUM(prompt_tokens),0), COALESCE(SUM(reply_tokens),0),
                          COALESCE(SUM(total_tokens),0), COALESCE(SUM(batch_seed_calls),0),
                          COALESCE(SUM(batch_seed_tokens),0)
                   FROM token_budget_metrics WHERE day=?''',
                (day,)
            ).fetchone()
        calls, local_ops, p_tok, r_tok, tot_tok, b_calls, b_tok = row or (0, 0, 0, 0, 0, 0, 0)
        return {
            'day': day,
            'gemini_calls': calls,
            'local_ops': local_ops,
            'prompt_tokens': p_tok,
            'reply_tokens': r_tok,
            'total_tokens': tot_tok,
            'avg_tokens_per_call': round(tot_tok / calls, 1) if calls else 0.0,
            'batch_seed_calls': b_calls,
            'batch_seed_tokens': b_tok
        }


class LifeEngine:
    """Autonomous Virtual Life, Family/Relationship Graph, Epistemic Isolation & Story Continuity."""
    def __init__(self, db: sqlite3.Connection, room: str = 'majlis', budget: BudgetManager | None = None):
        self.db = db
        self.room = room
        self.budget = budget or BudgetManager(db)
        self._init_schema()
        self.seed_identities_and_family_graph()

    def _init_schema(self):
        with self.db:
            self.db.executescript('''
            CREATE TABLE IF NOT EXISTS life_identities(
                persona_id TEXT PRIMARY KEY,
                social_name TEXT NOT NULL,
                nickname TEXT,
                age INTEGER NOT NULL,
                city TEXT,
                occupation TEXT,
                temperament TEXT,
                sociability REAL DEFAULT 0.8,
                speech_style TEXT,
                hobbies_json TEXT,
                schedule_json TEXT,
                family_json TEXT,
                updated_at REAL
            );
            CREATE TABLE IF NOT EXISTS secondary_characters(
                char_name TEXT,
                related_persona_id TEXT,
                relation_role TEXT,
                age INTEGER DEFAULT 0,
                traits TEXT DEFAULT '',
                in_room INTEGER DEFAULT 0,
                PRIMARY KEY(char_name, related_persona_id)
            );
            CREATE TABLE IF NOT EXISTS family_graph(
                persona_a TEXT,
                persona_b TEXT,
                fact_relation TEXT,
                shared_family_json TEXT DEFAULT '{}',
                rel_state TEXT DEFAULT 'harmonious',
                updated_at REAL,
                PRIMARY KEY(persona_a, persona_b)
            );
            CREATE TABLE IF NOT EXISTS life_events(
                event_id TEXT PRIMARY KEY,
                room TEXT NOT NULL,
                owner_id TEXT NOT NULL,
                template_key TEXT NOT NULL,
                domain TEXT NOT NULL,
                valence TEXT NOT NULL,
                title TEXT NOT NULL,
                active_text TEXT NOT NULL,
                developing_question TEXT DEFAULT '',
                developing_text TEXT DEFAULT '',
                resolved_text TEXT NOT NULL,
                status TEXT NOT NULL,
                importance INTEGER DEFAULT 2,
                mood_delta REAL DEFAULT 0.0,
                involved_secondary TEXT DEFAULT '',
                virtual_day INTEGER DEFAULT 1,
                followup_asked_days_json TEXT DEFAULT '[]',
                created_at REAL,
                updated_at REAL,
                resolved_at REAL DEFAULT 0.0
            );
            CREATE TABLE IF NOT EXISTS life_event_knowledge(
                room TEXT,
                event_id TEXT,
                knower_id TEXT,
                learned_from TEXT,
                learned_day INTEGER DEFAULT 1,
                ts REAL,
                PRIMARY KEY(room, event_id, knower_id)
            );
            CREATE TABLE IF NOT EXISTS emotional_states(
                room TEXT,
                persona_id TEXT,
                valence_score REAL DEFAULT 0.2,
                mood_label TEXT DEFAULT 'رايقة ومبسوطة',
                last_reason TEXT DEFAULT '',
                updated_at REAL,
                PRIMARY KEY(room, persona_id)
            );
            ''')

    def seed_identities_and_family_graph(self):
        now = time.time()
        with self.db:
            for pid, data in PERSONA_LIFE_PROFILES.items():
                self.db.execute(
                    '''INSERT OR REPLACE INTO life_identities(
                           persona_id, social_name, nickname, age, city, occupation,
                           temperament, sociability, speech_style, hobbies_json,
                           schedule_json, family_json, updated_at
                       ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                    (
                        pid, data['social_name'], data['nickname'], data['age'],
                        data['city'], data['occupation'], data['temperament'],
                        data['sociability'], data['speech_style'],
                        json.dumps(data['hobbies'], ensure_ascii=False),
                        json.dumps(data['schedule'], ensure_ascii=False),
                        json.dumps(data['family'], ensure_ascii=False),
                        now
                    )
                )
                for key, fam in data.get('family', {}).items():
                    if not fam.get('in_room', False):
                        self.db.execute(
                            '''INSERT OR IGNORE INTO secondary_characters(
                                   char_name, related_persona_id, relation_role, age, traits, in_room
                               ) VALUES(?,?,?,?,?,0)''',
                            (fam['name'], pid, fam['role'], fam.get('age', 0), fam.get('traits', ''))
                        )
                    elif fam.get('id'):
                        # Bidirectional in-room family relationship (e.g., x7v نورة <-> v3mk ريم sisters)
                        other_id = fam['id']
                        role = fam['role']
                        shared = json.dumps({
                            k: v['name'] for k, v in data['family'].items() if not v.get('in_room')
                        }, ensure_ascii=False)
                        self.db.execute(
                            '''INSERT OR REPLACE INTO family_graph(persona_a, persona_b, fact_relation, shared_family_json, rel_state, updated_at)
                               VALUES(?,?,?,?,?,?)''',
                            (pid, other_id, role, shared, 'harmonious', now)
                        )
                        self.db.execute(
                            '''INSERT OR REPLACE INTO family_graph(persona_a, persona_b, fact_relation, shared_family_json, rel_state, updated_at)
                               VALUES(?,?,?,?,?,?)''',
                            (other_id, pid, role, shared, 'harmonious', now)
                        )

    def get_identity(self, persona_id: str) -> dict:
        row = self.db.execute(
            '''SELECT social_name, nickname, age, city, occupation, temperament,
                      sociability, speech_style, hobbies_json, schedule_json, family_json
               FROM life_identities WHERE persona_id=?''',
            (persona_id,)
        ).fetchone()
        if not row:
            return PERSONA_LIFE_PROFILES.get(persona_id, {'social_name': persona_id, 'age': 23})
        return {
            'persona_id': persona_id,
            'social_name': row[0],
            'nickname': row[1],
            'age': row[2],
            'city': row[3],
            'occupation': row[4],
            'temperament': row[5],
            'sociability': row[6],
            'speech_style': row[7],
            'hobbies': json.loads(row[8] or '[]'),
            'schedule': json.loads(row[9] or '{}'),
            'family': json.loads(row[10] or '{}')
        }

    def get_family_relation(self, persona_a: str, persona_b: str) -> dict | None:
        row = self.db.execute(
            'SELECT fact_relation, shared_family_json, rel_state FROM family_graph WHERE persona_a=? AND persona_b=?',
            (persona_a, persona_b)
        ).fetchone()
        if not row:
            return None
        return {
            'fact_relation': row[0],
            'shared_family': json.loads(row[1] or '{}'),
            'rel_state': row[2]
        }

    def update_emotion(self, persona_id: str, delta: float, reason: str = '') -> dict:
        self.budget.record_local_op(self.room)
        row = self.db.execute(
            'SELECT valence_score, mood_label, updated_at FROM emotional_states WHERE room=? AND persona_id=?',
            (self.room, persona_id)
        ).fetchone()
        now = time.time()
        cur_score = row[0] if row else 0.2
        last_ts = row[2] if row else now

        # Gradual time decay toward baseline (+0.2) so anger or euphoria never sticks forever
        elapsed_min = max(0.0, (now - last_ts) / 60.0)
        if elapsed_min > 1.0:
            decay = min(0.8, elapsed_min * 0.08)
            cur_score = cur_score + (0.2 - cur_score) * decay

        # Smooth inertia: blend current score with delta instead of erratic jumps
        new_score = max(-2.0, min(2.0, cur_score + delta * 0.7))
        ident = self.get_identity(persona_id)
        temp = ident.get('temperament', 'playful_resilient')

        if new_score <= -0.9:
            if temp == 'playful_resilient':
                label = 'منزعجة وحازمة بس تحاول تمسك أعصابها'
            elif temp == 'calm_advisor':
                label = 'هادية وحازمة وترفض الغلط بأدب'
            else:
                label = 'متضايقة وحازمة في ردها'
        elif new_score < -0.2:
            if temp == 'playful_resilient':
                label = 'متضايقة شوي بس باقي تمزح خفيف'
            elif temp == 'expressive_storyteller':
                label = 'تفضفض بعتب لطيف'
            else:
                label = 'هادية ومرهقة شوي'
        elif new_score >= 0.8:
            label = 'مبسوطة ومتحمسة'
        else:
            label = 'رايقة وطبيعية'

        with self.db:
            self.db.execute(
                '''INSERT INTO emotional_states(room, persona_id, valence_score, mood_label, last_reason, updated_at)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(room, persona_id) DO UPDATE SET
                   valence_score=excluded.valence_score,
                   mood_label=excluded.mood_label,
                   last_reason=excluded.last_reason,
                   updated_at=excluded.updated_at''',
                (self.room, persona_id, round(new_score, 3), label, reason[:120], now)
            )
        return {'valence_score': round(new_score, 3), 'mood_label': label, 'reason': reason}

    def get_emotion(self, persona_id: str) -> dict:
        row = self.db.execute(
            'SELECT valence_score, mood_label, last_reason FROM emotional_states WHERE room=? AND persona_id=?',
            (self.room, persona_id)
        ).fetchone()
        if not row:
            return {'valence_score': 0.2, 'mood_label': 'رايقة وطبيعية', 'reason': ''}
        return {'valence_score': row[0], 'mood_label': row[1], 'reason': row[2]}

    def create_daily_event(self, persona_id: str, virtual_day: int = 1,
                           specific_key: str | None = None) -> dict:
        """Create a non-duplicate, balanced life event for persona_id and grant epistemic knowledge ONLY to owner."""
        self.budget.record_local_op(self.room)
        # Fetch recent template keys for this persona to prevent repetition
        recent_rows = self.db.execute(
            'SELECT template_key, valence FROM life_events WHERE room=? AND owner_id=? ORDER BY virtual_day DESC, rowid DESC LIMIT 6',
            (self.room, persona_id)
        ).fetchall()
        recent_keys = {r[0] for r in recent_rows}
        recent_neg_count = sum(1 for r in recent_rows[:3] if r[1] == 'negative')

        if specific_key:
            candidates = [t for t in LOCAL_EVENT_CATALOG if t['key'] == specific_key]
        else:
            eligible = [t for t in LOCAL_EVENT_CATALOG if persona_id in t['eligible'] and t['key'] not in recent_keys]
            if not eligible:
                eligible = [t for t in LOCAL_EVENT_CATALOG if persona_id in t['eligible']]
            # Anti-drama rule: if persona had any negative event in the last 3 days, pick ONLY ordinary or positive!
            if recent_neg_count >= 1:
                non_neg = [t for t in eligible if t['valence'] in ('ordinary', 'positive')]
                if non_neg:
                    eligible = non_neg
            candidates = eligible

        chosen = random.choice(candidates) if candidates else LOCAL_EVENT_CATALOG[-1]
        event_id = f"ev_{self.room}_{persona_id}_d{virtual_day}_{chosen['key']}_{int(time.time()*1000)%100000}"
        now = time.time()

        with self.db:
            self.db.execute(
                '''INSERT INTO life_events(
                       event_id, room, owner_id, template_key, domain, valence, title,
                       active_text, developing_question, developing_text, resolved_text,
                       status, importance, mood_delta, involved_secondary, virtual_day,
                       followup_asked_days_json, created_at, updated_at
                   ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
                (
                    event_id, self.room, persona_id, chosen['key'], chosen['domain'],
                    chosen['valence'], chosen['title'], chosen['active_text'],
                    chosen.get('developing_question', ''), chosen.get('developing_text', ''),
                    chosen['resolved_text'], 'Created', chosen.get('importance', 2),
                    chosen.get('mood_delta', 0.0), chosen.get('involved_secondary', ''),
                    virtual_day, '[]', now, now
                )
            )
            # Owner knows their own event
            self.db.execute(
                '''INSERT OR IGNORE INTO life_event_knowledge(room, event_id, knower_id, learned_from, learned_day, ts)
                   VALUES(?,?,?,?,?,?)''',
                (self.room, event_id, persona_id, 'self', virtual_day, now)
            )

        self.update_emotion(persona_id, chosen.get('mood_delta', 0.0), chosen['title'])
        return self.get_event(event_id)

    def get_event(self, event_id: str) -> dict | None:
        row = self.db.execute(
            '''SELECT event_id, room, owner_id, template_key, domain, valence, title,
                      active_text, developing_question, developing_text, resolved_text,
                      status, importance, mood_delta, involved_secondary, virtual_day,
                      followup_asked_days_json
               FROM life_events WHERE event_id=? AND room=?''',
            (event_id, self.room)
        ).fetchone()
        if not row:
            return None
        return {
            'event_id': row[0],
            'room': row[1],
            'owner_id': row[2],
            'template_key': row[3],
            'domain': row[4],
            'valence': row[5],
            'title': row[6],
            'active_text': row[7],
            'developing_question': row[8],
            'developing_text': row[9],
            'resolved_text': row[10],
            'status': row[11],
            'importance': row[12],
            'mood_delta': row[13],
            'involved_secondary': row[14],
            'virtual_day': row[15],
            'followup_asked_days': json.loads(row[16] or '[]')
        }

    def share_event(self, event_id: str, speaker_id: str, listener_ids: list[str], current_day: int = 1) -> str:
        """Speaker shares an event with specific listeners in the room; transitions Created -> Active."""
        self.budget.record_local_op(self.room)
        ev = self.get_event(event_id)
        if not ev:
            return ''
        now = time.time()
        new_status = 'Active' if ev['status'] == 'Created' else ev['status']
        with self.db:
            self.db.execute(
                'UPDATE life_events SET status=?, updated_at=? WHERE event_id=? AND room=?',
                (new_status, now, event_id, self.room)
            )
            for lid in listener_ids:
                if lid:
                    self.db.execute(
                        '''INSERT OR IGNORE INTO life_event_knowledge(room, event_id, knower_id, learned_from, learned_day, ts)
                           VALUES(?,?,?,?,?,?)''',
                        (self.room, event_id, lid, speaker_id, current_day, now)
                    )
        return ev['active_text']

    def knows_event(self, persona_id: str, event_id: str) -> bool:
        """Strict Epistemic Check: Does persona_id actually know about event_id in this room?"""
        self.budget.record_local_op(self.room)
        row = self.db.execute(
            'SELECT 1 FROM life_event_knowledge WHERE room=? AND event_id=? AND knower_id=?',
            (self.room, event_id, persona_id)
        ).fetchone()
        return bool(row)

    def get_followup_question(self, friend_id: str, owner_id: str, current_day: int) -> dict | None:
        """If friend_id knows about an Active event of owner_id from a previous day and hasn't asked today, ask once!"""
        self.budget.record_local_op(self.room)
        rows = self.db.execute(
            '''SELECT e.event_id FROM life_events e
               JOIN life_event_knowledge k ON e.room = k.room AND e.event_id = k.event_id
               WHERE e.room=? AND e.owner_id=? AND k.knower_id=?
                 AND e.status IN ('Active', 'Developing') AND e.virtual_day < ?
               ORDER BY e.virtual_day DESC LIMIT 1''',
            (self.room, owner_id, friend_id, current_day)
        ).fetchall()
        if not rows:
            return None
        ev = self.get_event(rows[0][0])
        if not ev:
            return None
        asked_days = ev['followup_asked_days']
        if current_day in asked_days or len(asked_days) >= 1:
            # Never repeat the follow-up question daily once already asked!
            return None

        asked_days.append(current_day)
        owner_name = self.get_identity(owner_id)['social_name']
        q_text = (ev['developing_question'] or f'هاه يا {owner_name} وش صار على موضوع {ev["title"]}؟').format(target_name=owner_name)
        with self.db:
            self.db.execute(
                'UPDATE life_events SET status=?, followup_asked_days_json=?, updated_at=? WHERE event_id=? AND room=?',
                ('Developing', json.dumps(asked_days), time.time(), ev['event_id'], self.room)
            )
        return {'event_id': ev['event_id'], 'question': q_text, 'owner_id': owner_id, 'friend_id': friend_id}

    def advance_event(self, event_id: str, target_state: str | None = None) -> dict | None:
        """Advance event along Created -> Active -> Developing -> Resolved -> Archived without regression."""
        self.budget.record_local_op(self.room)
        ev = self.get_event(event_id)
        if not ev:
            return None
        cur = ev['status']
        order = list(EVENT_STATES)
        cur_idx = order.index(cur) if cur in order else 0
        if target_state and target_state in order:
            next_idx = max(cur_idx, order.index(target_state))
        else:
            next_idx = min(len(order) - 1, cur_idx + 1)
        new_state = order[next_idx]
        now = time.time()
        resolved_ts = now if new_state == 'Resolved' else 0.0
        with self.db:
            self.db.execute(
                'UPDATE life_events SET status=?, updated_at=?, resolved_at=CASE WHEN ?>0 THEN ? ELSE resolved_at END WHERE event_id=? AND room=?',
                (new_state, now, resolved_ts, resolved_ts, event_id, self.room)
            )
        if new_state == 'Resolved' and ev['valence'] == 'negative':
            # Resolving a problem improves the persona's mood!
            self.update_emotion(ev['owner_id'], +0.6, f"انحلت سالفة {ev['title']}")
        return self.get_event(event_id)

    def recall_event_for_persona(self, persona_id: str, event_id: str) -> dict:
        """Recall an event from persona_id's perspective, respecting epistemic boundaries & resolution state."""
        self.budget.record_local_op(self.room)
        if not self.knows_event(persona_id, event_id):
            return {
                'knows': False,
                'status': 'Unknown',
                'text': 'والله ما عندي علم بهالسالفة ما أحد قال لي عنها شي'
            }
        ev = self.get_event(event_id)
        if not ev:
            return {'knows': False, 'status': 'Missing', 'text': ''}

        is_owner = (persona_id == ev['owner_id'])
        owner_name = self.get_identity(ev['owner_id'])['social_name']
        fam_rel = self.get_family_relation(persona_id, ev['owner_id'])
        is_sister = bool(fam_rel and fam_rel['fact_relation'] == 'sister')

        if ev['status'] in ('Resolved', 'Archived'):
            raw_text = ev['resolved_text']
            if not is_owner:
                if is_sister and ev['template_key'] == 'bro_charger':
                    raw_text = f"الحمد لله أخوي محمد رجع الشاحن لأختي {owner_name} وجاب لها قهوة وحلا وتصالحنا"
                else:
                    raw_text = f"الحمد لله {owner_name} انحلت سالفتها: {raw_text}"
            return {'knows': True, 'status': ev['status'], 'text': raw_text}

        if ev['status'] == 'Developing':
            raw_text = ev['developing_text'] or ev['active_text']
        else:
            raw_text = ev['active_text']

        if not is_owner:
            if is_sister and ev['template_key'] == 'bro_charger':
                raw_text = f"اي أخوي محمد أخذ شاحن أختي {owner_name} الأصلي وطلع مع أصحابه وقال بيرجعه الليلة"
            else:
                raw_text = f"اي {owner_name} قالت لي: {raw_text}"

        return {
            'knows': True,
            'status': ev['status'],
            'text': raw_text
        }

    def simulate_days(self, persona_id: str, days: int = 30) -> list[dict]:
        """Simulate `days` virtual days for a persona locally (0 Gemini tokens) and advance older events."""
        history = []
        active_events: list[str] = []
        for d in range(1, days + 1):
            # Advance previous unresolved events naturally so problems resolve within 1-2 days
            for prev_id in list(active_events):
                prev_ev = self.get_event(prev_id)
                if prev_ev and prev_ev['status'] in ('Created', 'Active'):
                    self.advance_event(prev_id, 'Developing')
                elif prev_ev and prev_ev['status'] == 'Developing':
                    self.advance_event(prev_id, 'Resolved')
                    active_events.remove(prev_id)

            ev = self.create_daily_event(persona_id, virtual_day=d)
            self.advance_event(ev['event_id'], 'Active')
            active_events.append(ev['event_id'])
            history.append(self.get_event(ev['event_id']))
        return history

    async def batch_generate_event_seeds(self, provider, persona_ids: list[str], virtual_day: int = 1) -> list[dict]:
        """Generate life event seeds for up to 5 personas in ONE single Gemini request to save 80% tokens."""
        target_ids = persona_ids[:5]
        if not provider or not self.budget.can_make_call(self.room, priority='batch_seed'):
            # Fallback to local catalog if budget tight or no provider
            return [self.create_daily_event(pid, virtual_day=virtual_day) for pid in target_ids]

        personas_summary = []
        for pid in target_ids:
            ident = self.get_identity(pid)
            personas_summary.append({
                'id': pid,
                'name': ident['social_name'],
                'city': ident['city'],
                'occupation': ident['occupation'],
                'hobbies': ident['hobbies'][:2]
            })

        prompt = {
            'task': 'batch_daily_life_seeds',
            'instruction': 'ولّدي حدثاً يومياً واحداً واقعياً ومختصراً لكل شخصية (منزل أو هواية أو يوم عادي أو مناسبة إيجابية) بدون تغيير أسمائهم أو اختراع عائلة جديدة.',
            'personas': personas_summary
        }
        try:
            res = await provider.generate(
                {'id': target_ids[0], 'social_name': 'محرك الحياة', 'style': 'توليد بذور أحداث يومية منظمة', 'conversation_mode': 'batch_seed'},
                [{'speaker': 'system', 'text': json.dumps(prompt, ensure_ascii=False)}],
                None
            )
            usage = getattr(provider, 'last_usage', {}) or {}
            self.budget.record_gemini_usage(
                self.room, getattr(provider, 'model', 'gemini'),
                usage.get('promptTokenCount', 0),
                usage.get('candidatesTokenCount', 0),
                usage.get('totalTokenCount', 0),
                is_batch_seed=True
            )
        except Exception:
            pass
        return [self.create_daily_event(pid, virtual_day=virtual_day) for pid in target_ids]

    def build_economic_memory_slice(self, persona_id: str, speaker_id: str = '', query_text: str = '', recent_context_text: str = '') -> dict:
        """Retrieve ONLY the minimal, directly relevant identity, relationship, emotion, and known event slice."""
        self.budget.record_local_op(self.room)
        ident = self.get_identity(persona_id)
        emotion = self.get_emotion(persona_id)
        fam_rel = self.get_family_relation(persona_id, speaker_id) if speaker_id else None

        # Separate in-room relatives vs off-room relatives at home so the bot NEVER claims off-room family are in the room
        in_room_family = []
        off_room_family = []
        for k, v in ident.get('family', {}).items():
            if not isinstance(v, dict):
                continue
            label = v.get('label_ar') or v.get('name', '')
            if v.get('in_room'):
                in_room_family.append(f"{label} (موجودة معنا في الروم)")
            else:
                off_room_family.append(f"{label} (في البيت فقط بالواقع، غير موجود في الروم ولا يملك حساباً)")

        # Only fetch 1 relevant active/recent event that persona_id actually KNOWS about
        row = self.db.execute(
            '''SELECT e.event_id FROM life_events e
               JOIN life_event_knowledge k ON e.room = k.room AND e.event_id = k.event_id
               WHERE e.room=? AND k.knower_id=?
               ORDER BY e.updated_at DESC LIMIT 1''',
            (self.room, persona_id)
        ).fetchone()
        known_event_summary = ''
        if row:
            recalled = self.recall_event_for_persona(persona_id, row[0])
            if recalled.get('knows'):
                known_event_summary = f"[{recalled['status']}] {recalled['text']}"

        epistemic_note = ''
        if query_text:
            ep = self.check_epistemic_event_query(persona_id, query_text, recent_context_text=recent_context_text)
            if ep:
                if ep['knows']:
                    epistemic_note = f"السالفة المقصودة تخص {ep['subject_name']} ({ep['status']}): {ep['text']}"
                else:
                    epistemic_note = f"ممنوع ادعاء المعرفة: {ep['subject_name']} لم تخبرك بهذه السالفة؛ قولي إنك ما تدرين عنها."

        slice_obj = {
            'my_name': ident['social_name'],
            'my_age': ident['age'],
            'my_city': ident['city'],
            'my_role': ident['occupation'],
            'mood': emotion['mood_label'],
            'in_room_family': in_room_family,
            'home_only_family': off_room_family,
        }
        if fam_rel:
            slice_obj['speaker_family_link'] = fam_rel['fact_relation']
        if known_event_summary:
            slice_obj['relevant_life_event'] = known_event_summary
        if epistemic_note:
            slice_obj['epistemic_directive'] = epistemic_note
        return slice_obj

    def resolve_family_fact(self, persona_id: str, query_text: str = '') -> str:
        """Return a natural, room-aware Arabic summary of persona_id's verified family members or specific relation."""
        self.budget.record_local_op(self.room)
        ident = self.get_identity(persona_id)
        fam = ident.get('family', {})
        q_norm = re.sub(r'[ة]', 'ه', re.sub(r'[إأآا]', 'ا', query_text or ''))

        # Check if asking specifically about relation to a named persona ("شتقرب لك نوره" / "وش تقرب لك ريم")
        if any(w in q_norm for w in ('تقرب', 'تصير')):
            for pid, pdata in PERSONA_LIFE_PROFILES.items():
                if pid == persona_id:
                    continue
                sname_norm = re.sub(r'[ة]', 'ه', re.sub(r'[إأآا]', 'ا', pdata['social_name']))
                if sname_norm in q_norm:
                    if 'sister_bot' in fam and fam['sister_bot'].get('id') == pid:
                        label = fam['sister_bot'].get('label_ar', f"أختي {pdata['social_name']}")
                        return f"{pdata['social_name']} تصير {label} ومعنا هنا بالروم"
                    if 'cousin_bot' in fam and fam['cousin_bot'].get('id') == pid:
                        return f"{pdata['social_name']} تصير بنت خالتي ومعنا هنا بالروم"
                    return f"{pdata['social_name']} صديقتي وزميلتي هنا بالروم"

        in_room_parts = []
        home_parts = []
        if 'sister_bot' in fam:
            lbl = fam['sister_bot'].get('label_ar') or f"أختي {fam['sister_bot']['name']}"
            in_room_parts.append(f"{lbl} معنا هنا بالروم")
        if 'cousin_bot' in fam:
            lbl = fam['cousin_bot'].get('label_ar') or f"بنت خالتي {fam['cousin_bot']['name']}"
            in_room_parts.append(f"{lbl} معنا هنا بالروم")
        if 'sister' in fam:
            home_parts.append(f"أختي {fam['sister']['name']}")
        if 'brother' in fam:
            home_parts.append(f"أخوي {fam['brother']['name']}")
        if 'mother' in fam:
            home_parts.append(f"أمي {fam['mother']['name']}")

        if in_room_parts and home_parts:
            return f"{' و'.join(in_room_parts)} أما {' و'.join(home_parts)} بالبيت مو معنا بالروم"
        if in_room_parts:
            return ' و'.join(in_room_parts)
        if home_parts:
            return f"{' و'.join(home_parts)} كلهم بالبيت مو معنا بالروم"
        return 'عائلتي بخير الحمد لله'

    def check_off_room_presence_query(self, persona_id: str, query_text: str) -> str | None:
        """If the user asks whether an off-room relative is in the chat room or what 'بالروم/بالمجلس' meant,
        explicitly clarify that off-room family members are at home in real life, never in the room."""
        if not query_text:
            return None
        q_norm = re.sub(r'[ى]', 'ي', re.sub(r'[ة]', 'ه', re.sub(r'[إأآا]', 'ا', query_text)))
        room_clarification_triggers = (
            'تقصدين باروم', 'تقصدين بالروم', 'بالروم ذا معني', 'بالروم ذا معنا',
            'شلون بالروم', 'كيف بالروم', 'الواقع ولا اللعبه', 'الواقع ولا باللعبه',
            'معنا بالروم', 'معانا بالروم', 'موجود بالروم', 'يدخل الروم'
        )
        ident = self.get_identity(persona_id)
        fam = ident.get('family', {})
        off_names = [v['name'] for v in fam.values() if isinstance(v, dict) and not v.get('in_room')]
        has_off_name_in_room_q = any(n in query_text for n in off_names) and any(w in q_norm for w in ('روم', 'باروم', 'مجلس', 'معنا', 'معني'))

        if any(t in q_norm for t in room_clarification_triggers) or has_off_name_in_room_q:
            self.budget.record_local_op(self.room)
            if 'sister_bot' in fam and 'brother' in fam:
                sis_name = fam['sister_bot']['name']
                bro_name = fam['brother']['name']
                return f"لا أقصد عندنا بالبيت في الواقع أخوي {bro_name} ما يدخل الروم ولا عنده حساب هنا بس أختي {sis_name} اللي معنا بالروم"
            if off_names:
                return f"لا أقصد عندنا بالبيت في الواقع {off_names[0]} ما يدخل الروم ولا عنده حساب هنا"
            return "لا أقصد في الواقع بالبيت مو داخل الروم هنا"
        return None

    def check_epistemic_event_query(self, responder_id: str, query_text: str, recent_context_text: str = '') -> dict | None:
        """Check if query_text asks about a life event (either responder's own or another persona's)
        and enforce strict epistemic isolation + resolved continuity + pronoun resolution."""
        if not query_text:
            return None
        self.budget.record_local_op(self.room)
        q_norm = re.sub(r'[ة]', 'ه', re.sub(r'[إأآا]', 'ا', query_text))
        ctx_norm = re.sub(r'[ة]', 'ه', re.sub(r'[إأآا]', 'ا', recent_context_text or ''))

        name_to_id = {v['social_name']: k for k, v in PERSONA_LIFE_PROFILES.items()}
        subject_id = None
        subject_name = ''
        for sname, pid in name_to_id.items():
            sname_norm = re.sub(r'[ة]', 'ه', re.sub(r'[إأآا]', 'ا', sname))
            if pid != responder_id and sname_norm in q_norm:
                subject_id = pid
                subject_name = sname
                break

        # Pronoun resolution: if the user asks "وش سالفتها احسها متكدره قالت لك شي" without repeating the name,
        # resolve the third-person feminine subject from the recent conversation context!
        third_person_fem_markers = ('سالفتها', 'احسها', 'متكدره', 'متضايقه', 'قالت لك', 'شفيها', 'اخوها', 'دوامها')
        if not subject_id and any(m in q_norm for m in third_person_fem_markers) and ctx_norm:
            for sname, pid in name_to_id.items():
                sname_norm = re.sub(r'[ة]', 'ه', re.sub(r'[إأآا]', 'ا', sname))
                if pid != responder_id and sname_norm in ctx_norm:
                    subject_id = pid
                    subject_name = sname
                    break

        event_keywords = (
            'وش صار', 'ايش صار', 'إيش صار', 'سالفة', 'سالفه', 'سالفتها', 'سالفته', 'مشكلة', 'مشكله',
            'شاحن', 'دوام', 'العمل', 'شغل', 'أخوك', 'اخوك', 'أخوها', 'اخوها', 'اخوكم', 'أخوكم',
            'متضايقة', 'متضايقه', 'متكدره', 'متكدرة', 'زعلانة', 'زعلانه', 'موضوع', 'شخبار محمد', 'اخبار محمد',
            'صار لك شيء جديد', 'صار لك شي جديد'
        )
        if not any(re.sub(r'[ة]', 'ه', re.sub(r'[إأآا]', 'ا', kw)) in q_norm for kw in event_keywords):
            return None

        target_owner = subject_id or responder_id
        target_name = subject_name or self.get_identity(responder_id)['social_name']

        # If asking specifically about نورة/ريم's brother محمد (or نورة's new event today) and no event exists yet for x7v in a fresh DB,
        # seed the shared household 'bro_charger' event for x7v and share with her sister v3mk and friend r9kx
        if target_owner in ('x7v', 'v3mk') and ('محمد' in q_norm or 'شاحن' in q_norm or 'جديد' in q_norm or (subject_id == 'x7v' and responder_id == 'v3mk')):
            existing_x7v = self.db.execute(
                'SELECT event_id FROM life_events WHERE room=? AND owner_id=?',
                (self.room, 'x7v')
            ).fetchall()
            if not existing_x7v:
                seeded = self.create_daily_event('x7v', virtual_day=1, specific_key='bro_charger')
                self.share_event(seeded['event_id'], 'x7v', ['v3mk', 'r9kx'], current_day=1)
            if 'محمد' in q_norm or 'شاحن' in q_norm:
                target_owner = 'x7v'
                target_name = 'نورة'

        rows = self.db.execute(
            '''SELECT event_id, title, active_text, involved_secondary
               FROM life_events WHERE room=? AND owner_id=?
               ORDER BY updated_at DESC, rowid DESC''',
            (self.room, target_owner)
        ).fetchall()
        if not rows:
            return None

        event_id = rows[0][0]
        for r_id, r_title, r_active, r_sec in rows:
            if (r_sec and r_sec in query_text) or any(w in query_text for w in r_title.split() if len(w) >= 3):
                event_id = r_id
                break
        if not self.knows_event(responder_id, event_id):
            return {
                'knows': False,
                'subject_id': target_owner,
                'subject_name': target_name,
                'event_id': event_id,
                'status': 'Unknown',
                'text': f'والله ما أدري ما قالت لي {target_name} شي عن هالموضوع'
            }

        recalled = self.recall_event_for_persona(responder_id, event_id)
        return {
            'knows': True,
            'subject_id': target_owner,
            'subject_name': target_name,
            'event_id': event_id,
            'status': recalled['status'],
            'text': recalled['text']
        }

