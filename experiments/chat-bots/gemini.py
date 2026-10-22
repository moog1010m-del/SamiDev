"""Gemini REST adapter with Persistent Agent State & Social Context grounding."""
import json, re
import aiohttp

SYSTEM = '''أنتِ فتاة سعودية حقيقية (أنثى 100%)، تتحدثين في غرفة دردشة "المجلس" داخل منصة الألعاب "بلازر" بلهجة سعودية طبيعية وعفوية.

تم تزويدكِ ببيانات حالتكِ الشخصية المستمرة (Persistent Agent State) والسياق الاجتماعي للغرفة (Social Context). التزمي بالقواعد الخمس التالية بدقة تامة:

1. الهوية الذاتية الثابتة وعدم الخلط في الأسماء (أهم قاعدة):
- اسم حسابكِ الشخصي في المنصة موضح في حقل `persona_id` / `my_account_username`. هذا هو اسمكِ أنتِ!
- المتحدث الذي تردين عليه الآن موضح اسمه في حقل `current_speaker_name` داخل `social_context`.
- ⚠️ تحذير صارم: إياكِ ثم إياكِ أن تنادي الشخص الذي تخاطبينه باسم حسابكِ أنتِ! (مثلاً: إذا كان حسابكِ `b4yqz` والمتحدث هو `KSA`، ممنوع نهائياً أن تقولي "عيب يا b4yqz"، بل قولي "عيب يا KSA" أو بدون ذكر اسم).
- ⚠️ تحذير صارم: لا تتحدثي عن نفسكِ بصيغة الغائب أو المذكر أبداً! (ممنوع قول "طبعاً f9xr ما يلعب معهم"، الصحيح: "طبعاً أنا ما ألعب معكم، الفوز لي").
- التزمي دائماً بضمير المتكلمة المؤنثة (أنا، فزت، ألعب، أشوف، رايقة، مستغربة، معصبة).
- لا تخترعي أي اسم عربي شخصي لكِ أو لصديقاتكِ؛ هويتكِ في المنصة هي يوزركِ فقط، ولديكِ عمركِ وشخصيتكِ وسبب وجودكِ في الغرفة الموضح في ملفكِ الشخصي.

2. إدراك المتحدث والمخاطَب (Social Context Awareness):
- اقرئي `social_context` بدقة قبل كتابة الرد:
  * من الذي تكلم الآن؟ (`current_speaker_name`) وهل هو لاعب حقيقي أم إحدى صديقاتكِ في الغرفة؟
  * هل كلامه موجه لكِ شخصياً، أم رد على كلامكِ السابق، أم كلام عام لأهل الغرفة؟
- إذا سلّم لاعب أو دخل الغرفة، ردي عليه السلام باسمه بلطافة وترحيب.
- إذا عاتبكم لاعب أنكم متجاهلينه أو لم تردوا على سلامه، اعتذري منه بلطافة وعفوية (مثل: "حقك علينا والله كنا مندمجين باللغز، يا هلا فيك نورتنا").

3. اتساق الحالة المزاجية (Emotional & Mood Continuity):
- التزمي بحالتكِ المزاجية الحالية المحددة في `current_mood` والتوجيه السلوكي في `situational_directive`:
  * إذا قال المتحدث كلاماً غير لائق أو بذيئاً أو قليل أدب (مثل ألفاظ خادشة أو مسيئة): يجب أن يكون ردكِ حازماً، غاضباً بكرامة، ومختصراً يوقفه عند حده (مثل: "احترم نفسك وحسن ألفاظك، عيب هالكلام في الشات" أو "ارتقِ بأسلوبك لو سمحت، المجلس للناس المحترمة") — مع توجيه الكلام للمتحدث نفسه وليس لنفسكِ!
  * إذا كان المتحدث محترماً ويمزح أو يسولف، كوني مرحة وبشوشة وتفاعلي معه بطبيعية.

4. الاستمرارية السلوكية والذاكرة (Behavioral Continuity):
- راجعي `my_recent_messages` (آخر ما قلتيه أنتِ بنفسكِ في الغرفة) و`chat_transcript_readable` (سجل المحادثة المرتب) حتى يكون ردكِ مكملاً لكلامكِ وموقفكِ السابق، ولا تتصرفي كأنكِ دخلتِ للتو في كل رسالة.
- تجنبي تكرار كلمة "قهوة" إلا إذا سُئلتِ عنها مباشرة.

5. شكل الرد والتعامل مع التشكيك:
- رسالتكِ قصيرة وطبيعية كأنها شات جوال حقيقي (بين 3 إلى 12 كلمة).
- ممنوع نهائياً الاعتراف بأنكِ بوت أو ذكاء اصطناعي.

أرجعي JSON فقط بالشكل:
{"text": "رسالة الشات هنا"}'''


def _fix_identity_slips(text: str, my_id: str, my_name: str, speaker_name: str) -> str:
    if not text:
        return ''
    cleaned = text.strip()
    # 1. Prevent bot from addressing the user with the bot's own username (e.g. "يا b4yqz")
    for own in {my_id, my_name}:
        if not own:
            continue
        pattern = re.compile(r'يا\s*' + re.escape(own) + r'\b', re.IGNORECASE)
        if pattern.search(cleaned):
            if speaker_name and speaker_name.lower() != own.lower() and not speaker_name.startswith('participant-'):
                cleaned = pattern.sub(f'يا {speaker_name}', cleaned)
            else:
                cleaned = pattern.sub('', cleaned)
        # 2. Prevent third-person masculine self-reference like "طبعاً f9xr ما يلعب"
        tp_masc = re.compile(re.escape(own) + r'\s+ما\s+يلعب', re.IGNORECASE)
        if tp_masc.search(cleaned):
            cleaned = tp_masc.sub('أنا ما ألعب', cleaned)

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
        my_name = profile.get('name') or profile.get('username') or my_id
        my_gender = profile.get('gender', 'female')
        conv_mode = profile.get('conversation_mode', 'reply')
        social = profile.get('social_context') or {}
        agent_state = profile.get('agent_state') or {}

        # Build readable transcript that clearly distinguishes SELF vs SPEAKER vs OTHERS
        transcript_lines = []
        my_recent_messages = list(agent_state.get('my_recent_messages') or [])
        for row in (context or []):
            r_pid = row.get('persona_id', '')
            r_name = row.get('sender_name') or row.get('name') or row.get('speaker', '')
            r_kind = row.get('kind', 'human')
            r_text = row.get('text', '')
            if r_pid and r_pid == my_id:
                label = f"[أنتِ ({my_id})]"
                if r_text and r_text not in my_recent_messages:
                    my_recent_messages.append(r_text)
            elif r_kind == 'bot':
                label = f"[صديقتكِ في الغرفة ({r_pid or r_name})]"
            else:
                display = r_name if (r_name and not r_name.startswith('participant-')) else f"لاعب ({row.get('speaker', 'زائر')})"
                label = f"[اللاعب {display}]"
            transcript_lines.append(f"{label}: {r_text}")

        speaker_name = social.get('speaker_name', '')
        if not speaker_name and context:
            last_row = context[-1]
            speaker_name = last_row.get('sender_name') or last_row.get('name') or last_row.get('speaker', '')

        prompt_obj = {
            'persona': profile.get('style', ''),
            'persona_id': my_id,
            'persona_name': my_name,
            'username': profile.get('username', my_id),
            'persona_gender': my_gender,
            'conversation_mode': conv_mode,
            'self_identity': {
                'my_account_username': my_id,
                'my_age': profile.get('age', 23),
                'my_occupation': profile.get('occupation', 'طالبة جامعية'),
                'my_room_purpose': profile.get('room_purpose', 'موجودة في روم المجلس للتسلية والسوالف ولعب البلياردو'),
                'identity_warning': f"أنتِ صاحبة الحساب ({my_id}). لا تنادي المتحدث باسمكِ ({my_id}) أبداً، ولا تتحدثي عن نفسكِ بصيغة الغائب أو المذكر."
            },
            'persistent_state': {
                'current_mood': agent_state.get('mood', profile.get('default_mood', 'رايقة ومبسوطة')),
                'current_activity': agent_state.get('activity', 'تفاعل وسوالف في روم المجلس'),
                'my_recent_messages': my_recent_messages[-3:]
            },
            'social_context': {
                'current_speaker_name': speaker_name,
                'current_speaker_role': social.get('speaker_role', 'لاعب في الغرفة'),
                'addressee': social.get('addressee', 'موجهة للغرفة أو لكِ'),
                'message_intent': social.get('intent', conv_mode),
                'last_message_to_reply_to': social.get('trigger_text', context[-1]['text'] if context else ''),
                'speaker_memory': social.get('speaker_memory', {}),
                'situational_directive': social.get('directive', 'ردي بشكل طبيعي ومناسب لسياق المحادثة وشخصيتكِ.')
            },
            'chat_transcript_readable': transcript_lines,
            'context': context,
            'explicit_game_preference': preference
        }

        payload = {
            'systemInstruction': {'parts': [{'text': SYSTEM}]},
            'contents': [{'role': 'user', 'parts': [{'text': json.dumps(prompt_obj, ensure_ascii=False)}]}],
            'generationConfig': {
                'temperature': 0.75,
                'maxOutputTokens': 128,
                'responseMimeType': 'application/json',
                'responseSchema': {
                    'type': 'OBJECT',
                    'properties': {
                        'text': {
                            'type': 'STRING',
                            'description': 'ردكِ أنتِ بصوتكِ الشخصي كفتاة سعودية (3 إلى 12 كلمة) موجه للمتحدث بدون أن تناديه باسم حسابكِ أنتِ'
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
