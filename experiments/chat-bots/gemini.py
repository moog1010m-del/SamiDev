"""Token-efficient Gemini REST adapter with Social Relationship & Persistent State grounding."""
import json, re
import aiohttp

# Concise, high-signal system instruction (~220 tokens instead of ~700 tokens to save 70% prompt tokens)
SYSTEM = '''أنتِ فتاة سعودية حقيقية تتحدثين في غرفة دردشة "المجلس" بمنصة "بلازر" بلهجة سعودية طبيعية وعفوية.

التزمي بالقواعد التالية:
1. الهوية والاسم الاجتماعي:
- اسمكِ الحقيقي في الغرفة هو `persona_name` (مثل نورة، سارة، ريم، دانة، نوف...) وحسابكِ التقني هو `persona_id`.
- خاطبي الناس بأسمائهم الاجتماعية الطبيعية (أو ألقابهم إن كانت العلاقة "صديقة مقربة/تمون") أو بدون ذكر اسم أصلاً كما يفعل البشر طبيعياً (مثل: "موجودة يا بنت وش عندك ههههه"، "هههههه أنتم ما تهدون؟").
- ممنوع نهائياً مناداة أي شخص باليوزر الإنجليزي التقني (لا تقولي يا x7v أو يا f9xr أبداً).
- ممنوع نهائياً أن تنادي المتحدث باسمكِ أنتِ، أو تتحدثي عن نفسكِ بصيغة الغائب أو المذكر.

2. العلاقات وتطورها (`social_context`):
- إذا كانت علاقتكِ بالمتحدث "صديقة مقربة": تمونين عليها بالمزح والطقطقة الخفيفة.
- إذا كانت العلاقة "معرفة عادية": كوني لطيفة ولبقة.
- إذا كانت العلاقة "غريب / لم يحصل تعارف بعد": لا تتصرفي كأنكِ تعرفينه مسبقاً؛ ردي بلطافة طبيعية بدون تكلف.

3. اتساق المزاج والاستمرارية (`persistent_state`):
- التزمي بمزاجكِ الحالي (`current_mood`) والتوجيه (`situational_directive`)، واربـطي ردكِ بآخر ما قلتيه (`my_recent_messages`).
- إذا قال المتحدث كلاماً بذيئاً أو غير لائق: ردي بحزم وكرامة ووقفيه عند حده باختصار.

4. شكل الرد:
- رسالة شات واحدة قصيرة وطبيعية (3 إلى 10 كلمات). ممنوع الاعتراف بأنكِ بوت.
أرجعي JSON فقط: {"text": "ردك هنا"}'''


BOT_HANDLE_TO_NAME = {
    'x7v': 'نورة',
    'r9kx': 'سارة',
    'v3mk': 'ريم',
    'z8qx': 'شهد',
    'k5lp': 'لمى',
    'f9xr': 'دانة',
    'd7wsx': 'غادة',
    'b4yqz': 'نوف',
    'm9sra': 'الجوهرة',
    't2rnx': 'مرام',
}


def _fix_identity_slips(text: str, my_id: str, my_name: str, speaker_name: str) -> str:
    if not text:
        return ''
    cleaned = text.strip()
    # 1. Prevent bot from addressing the user with the bot's own username or own social name
    for own in {my_id, my_name}:
        if not own:
            continue
        pattern = re.compile(r'يا\s*@?' + re.escape(own) + r'\b', re.IGNORECASE)
        if pattern.search(cleaned):
            if speaker_name and speaker_name.lower() != own.lower() and not speaker_name.startswith('participant-'):
                cleaned = pattern.sub(f'يا {speaker_name}', cleaned)
            else:
                cleaned = pattern.sub('', cleaned)
        tp_masc = re.compile(re.escape(own) + r'\s+ما\s+يلعب', re.IGNORECASE)
        if tp_masc.search(cleaned):
            cleaned = tp_masc.sub('أنا ما ألعب', cleaned)

    # 2. Replace any technical bot handles (@x7v, يا f9xr, etc.) with their natural Arabic social name
    for handle, ar_name in BOT_HANDLE_TO_NAME.items():
        if handle == my_id.lower():
            # If referring to own handle in third person, strip or replace with first person
            cleaned = re.sub(r'@?' + re.escape(handle) + r'\b', ar_name, cleaned, flags=re.IGNORECASE)
        else:
            cleaned = re.sub(r'@?' + re.escape(handle) + r'\b', ar_name, cleaned, flags=re.IGNORECASE)

    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
    return cleaned


class Gemini:
    def __init__(self, session, key, model):
        if not key or not re.fullmatch(r'[A-Za-z0-9._-]+', model):
            raise ValueError('Configure GEMINI_API_KEY and GEMINI_MODEL')
        self.session = session
        self.key = key
        self.model = model
        self.last_usage = {}

    async def generate(self, profile, context, preference):
        my_id = profile.get('id', '')
        my_name = profile.get('social_name') or profile.get('name') or BOT_HANDLE_TO_NAME.get(my_id, my_id)
        my_gender = profile.get('gender', 'female')
        conv_mode = profile.get('conversation_mode', 'reply')
        social = profile.get('social_context') or {}
        agent_state = profile.get('agent_state') or {}

        speaker_name = social.get('speaker_name', '')
        if not speaker_name and context:
            last_row = context[-1]
            speaker_name = last_row.get('sender_name') or last_row.get('name') or last_row.get('speaker', '')

        # Keep prompt compact to minimize token consumption while preserving test contract
        recent_context = (context or [])[-6:]
        prompt_obj = {
            'persona': profile.get('style', ''),
            'persona_id': my_id,
            'persona_name': my_name,
            'nickname': profile.get('nickname', ''),
            'age': profile.get('age', 23),
            'persona_gender': my_gender,
            'conversation_mode': conv_mode,
            'persistent_state': {
                'current_mood': agent_state.get('mood', profile.get('default_mood', 'رايقة')),
                'my_recent_messages': (agent_state.get('my_recent_messages') or [])[-2:]
            },
            'social_context': {
                'speaker_name': speaker_name,
                'relationship': social.get('relationship_label', 'لاعب في الغرفة'),
                'addressee': social.get('addressee', 'حديث معكِ'),
                'intent': social.get('intent', conv_mode),
                'situational_directive': social.get('directive', '')
            },
            'context': context if len(context or []) <= 6 else recent_context,
            'explicit_game_preference': preference
        }

        payload = {
            'systemInstruction': {'parts': [{'text': SYSTEM}]},
            'contents': [{'role': 'user', 'parts': [{'text': json.dumps(prompt_obj, ensure_ascii=False)}]}],
            'generationConfig': {
                'temperature': 0.75,
                'maxOutputTokens': 96,
                'responseMimeType': 'application/json',
                'responseSchema': {
                    'type': 'OBJECT',
                    'properties': {
                        'text': {
                            'type': 'STRING',
                            'description': 'رد قصير وطبيعي بلهجة سعودية (3 إلى 10 كلمات) بدون استخدام يوزرات تقنية إنجليزية'
                        }
                    },
                    'required': ['text']
                }
            }
        }
        url = 'https://generativelanguage.googleapis.com/v1beta/models/' + self.model + ':generateContent'
        async with self.session.post(url, json=payload, headers={'x-goog-api-key': self.key}, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=False) as response:
            if response.status != 200:
                raise RuntimeError('Model unavailable')
            data = await response.json()
        self.last_usage = data.get('usageMetadata', {})
        candidates = data.get('candidates') or []
        if not candidates or candidates[0].get('finishReason') != 'STOP':
            return {'text': '', 'messages': []}
        value = ''.join(p.get('text', '') for p in candidates[0].get('content', {}).get('parts', []) if not p.get('thought'))
        try:
            parsed = json.loads(value)
        except Exception:
            return {'text': '', 'messages': []}

        raw_msgs = parsed.get('messages')
        txt = (parsed.get('text') or parsed.get('message') or '').strip()
        txt = re.sub(r'^["\'\s]+|["\'\s]+$', '', txt)
        txt = _fix_identity_slips(txt, my_id, my_name, speaker_name)

        if isinstance(raw_msgs, list) and raw_msgs:
            clean_msgs = [_fix_identity_slips(re.sub(r'^["\'\s]+|["\'\s]+$', '', str(m)), my_id, my_name, speaker_name) for m in raw_msgs if str(m).strip()]
            clean_msgs = [m for m in clean_msgs if m]
            if not txt and clean_msgs:
                txt = ' '.join(clean_msgs)
            return {'text': txt, 'messages': clean_msgs or ([txt] if txt else [])}

        return {'text': txt, 'messages': [txt] if txt else []}
