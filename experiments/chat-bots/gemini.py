"""Token-efficient Gemini REST adapter with Social Relationship & Human-Typing Style."""
import json, re
import aiohttp

SYSTEM = '''أنتِ فتاة سعودية تتحدثين من جوالكِ في شات "بلازر" بلهجة سعودية طبيعية وعفوية.
القواعد:
1. كتابة جوال: بدون فواصل (،) أو تعجب (!) أو نقاط (.) أو إيموجي. ممنوع كتابة "ههههه" إلا للنكت الصريحة وممنوع قول "يالطيب" أو "يالغالي".
2. الهوية: اسمكِ الثابت `persona_name` وحسابكِ `persona_id` وعمركِ `my_age`؛ لا تخلطي نفسكِ بشخصية أخرى ولا تذكري عمركِ أو مهنتكِ دون سؤال.
3. الغرفة والعائلة: فقط `in_room_family` معنا بالروم؛ أما `home_only_family` فبالبيت في الواقع فقط وليسوا بالروم أبداً.
4. ردي برسالة واحدة قصيرة (3 إلى 10 كلمات) بصيغة JSON فقط: {"text": "ردك هنا"}'''


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

    # Only replace "يا <handle>" or "@<handle>" when addressing another bot so she can still state account usernames if asked
    for handle, ar_name in BOT_HANDLE_TO_NAME.items():
        if handle != my_id.lower():
            cleaned = re.sub(r'يا\s*@?' + re.escape(handle) + r'\b', f'يا {ar_name}', cleaned, flags=re.IGNORECASE)
            cleaned = re.sub(r'@' + re.escape(handle) + r'\b', ar_name, cleaned, flags=re.IGNORECASE)
        if my_name and ar_name != my_name:
            # Prevent identity confusion: never claim to be another bot's social name ("أنا شهد" / "اسمي شهد" when my_name is "ريم")
            cleaned = re.sub(r'\b(أنا|انا|اسمي|أسمي)\s+' + re.escape(ar_name) + r'\b', rf'\1 {my_name}', cleaned)

    cleaned = re.sub(r'\s{2,}', ' ', cleaned).strip()
    return cleaned


class Gemini:
    def __init__(self, session, key, model):
        if isinstance(key, (list, tuple)):
            raw_keys = [str(k).strip() for k in key if str(k).strip()]
        elif isinstance(key, str):
            raw_keys = [k.strip() for k in key.split(',') if k.strip()]
        else:
            raw_keys = []
        # Deduplicate while preserving order
        self.keys = list(dict.fromkeys(raw_keys))
        if not self.keys or not re.fullmatch(r'[A-Za-z0-9._-]+', model):
            raise ValueError('Configure GEMINI_API_KEY and GEMINI_MODEL')
        self.key = self.keys[0]
        self.session = session
        self.model = model
        self.last_usage = {}
        self._key_index = 0
        self._cooldown_until = {}  # key -> monotonic timestamp

    def _ordered_candidate_keys(self) -> list[str]:
        import time as _time
        now = _time.monotonic()
        n = len(self.keys)
        healthy = []
        cooling = []
        for i in range(n):
            k = self.keys[(self._key_index + i) % n]
            if self._cooldown_until.get(k, 0) <= now:
                healthy.append(k)
            else:
                cooling.append(k)
        self._key_index = (self._key_index + 1) % n
        return healthy if healthy else cooling

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

        recent_context = (context or [])[-3:] if profile.get('life_slice') else (context or [])[-6:]
        life_slice = profile.get('life_slice')
        if life_slice:
            prompt_obj = {
                'persona_id': my_id,
                'persona_name': my_name,
                'persona_gender': my_gender,
                'conversation_mode': conv_mode,
                'life_slice': life_slice,
                'social_context': {
                    'speaker_name': speaker_name,
                    'relationship': social.get('relationship_label', 'لاعب'),
                    'situational_directive': social.get('directive', '')
                },
                'context': context if len(context or []) <= 3 else recent_context,
            }
            if preference:
                prompt_obj['explicit_game_preference'] = preference
        else:
            prompt_obj = {
                'persona': profile.get('style', ''),
                'persona_id': my_id,
                'my_account_handle': my_id,
                'persona_name': my_name,
                'nickname': profile.get('nickname', ''),
                'age': profile.get('age', 23),
                'persona_gender': my_gender,
                'conversation_mode': conv_mode,
                'known_room_accounts': BOT_HANDLE_TO_NAME,
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
        import time as _time
        data = None
        last_err = None
        for current_key in self._ordered_candidate_keys():
            try:
                async with self.session.post(url, json=payload, headers={'x-goog-api-key': current_key}, timeout=aiohttp.ClientTimeout(total=15), allow_redirects=False) as response:
                    if response.status == 200:
                        data = await response.json()
                        self.key = current_key
                        break
                    # Cooldown failed/rate-limited key (5 min for 429, 15 min for 401/403) and immediately try next partner key
                    cooldown_sec = 900 if response.status in (400, 401, 403) else 300
                    self._cooldown_until[current_key] = _time.monotonic() + cooldown_sec
                    last_err = RuntimeError('Model unavailable')
            except Exception as exc:
                self._cooldown_until[current_key] = _time.monotonic() + 120
                last_err = exc
        if data is None:
            raise (last_err or RuntimeError('Model unavailable'))
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
