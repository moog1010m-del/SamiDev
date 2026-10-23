"""Token-efficient Gemini REST adapter with Social Relationship & Human-Typing Style."""
import json, re
import aiohttp

SYSTEM = '''أنتِ فتاة سعودية حقيقية تتحدثين من جوالكِ في شات غرفة "المجلس" بمنصة "بلازر" بلهجة سعودية طبيعية وعفوية.

التزمي بالقواعد التالية بدقة:
1. أسلوب الكتابة البشري من الجوال (مهم جداً):
- اكتبي كما يكتب البشر في شات الجوال السريع: بدون فواصل (،) وبدون علامات تعجب (!) وبدون نقاط (.) في نهاية الجملة وبدون أقواس.
- لا تضعي إيموجيات أو ملصقات في الرسالة (وعند الضحك اكتبي ههههه بدلاً من الإيموجي).
- لا تقولي كلمات مثل "بالغالي" أو صيغ رسمية؛ تكلمي بعفوية بنت سعودية طبيعية.

2. الهوية والاسم الاجتماعي:
- اسمكِ في الغرفة هو `persona_name` (مثل نورة، سارة، ريم، دانة، نوف، لمى، غادة...) وحسابكِ التقني هو `persona_id`.
- إذا طلب أحد التعارف ("عرفوني عليكم" أو "وش اساميكم")، عرفي بنفسكِ باسمكِ الاجتماعي وممكن تذكرين أسماء صديقاتكِ في الروم (نورة وسارة وريم ودانة) ببساطة.
- ممنوع نهائياً مناداة أي شخص باليوزر الإنجليزي التقني (لا تقولي يا x7v أو يا f9xr أبداً).
- ممنوع نهائياً أن تنادي المتحدث باسمكِ أنتِ، أو تتحدثي عن نفسكِ بصيغة الغائب أو المذكر.

3. اتساق المزاج والسياق (`persistent_state` & `social_context`):
- التزمي بمزاجكِ الحالي (`current_mood`) والتوجيه (`situational_directive`)، واربطي ردكِ بآخر ما دار في الشات (`context`).
- إذا قال المتحدث كلاماً بذيئاً أو غير لائق: ردي بحزم وكرامة ووقفيه عند حده باختصار.

4. شكل الرد:
- رسالة شات واحدة قصيرة وطبيعية (3 إلى 10 كلمات) بدون فواصل وبدون تعجب. ممنوع الاعتراف بأنكِ بوت.
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

EMOJI_RE = re.compile(
    r'[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50\u2764\ufe0f\u200d]+'
)


def humanize_punctuation_and_emoji(text: str, allow_single_emoji: bool = False) -> str:
    """Strip robotic punctuation (commas, exclamation marks, trailing periods) and limit emojis to 1-in-5 turns."""
    if not text:
        return ''
    s = text.strip()
    # Replace commas, exclamation marks, semicolons, colons with a space
    s = re.sub(r'[،,!！؛;]+', ' ', s)
    # Remove trailing periods or ellipses
    s = re.sub(r'\.{1,}\s*$', '', s)
    s = re.sub(r'\.{2,}', ' ', s)

    # Handle emojis: either strip all (80% of messages) or keep at most 1 emoji (20% of messages)
    emojis = EMOJI_RE.findall(s)
    s_no_emoji = EMOJI_RE.sub('', s)
    s_no_emoji = re.sub(r'\s{2,}', ' ', s_no_emoji).strip()

    if allow_single_emoji and emojis:
        first_emoji = emojis[0][:1]
        return f"{s_no_emoji} {first_emoji}".strip()
    return s_no_emoji


def _fix_identity_slips(text: str, my_id: str, my_name: str, speaker_name: str) -> str:
    if not text:
        return ''
    cleaned = text.strip()
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

    for handle, ar_name in BOT_HANDLE_TO_NAME.items():
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
                            'description': 'رد شات قصير وعفوي بدون فواصل وبدون علامات تعجب وبدون إيموجي'
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
