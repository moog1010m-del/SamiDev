"""Isolated orchestration and local memory. No platform imports or network I/O."""
from __future__ import annotations
import json, random, re, sqlite3, time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

def safe_text(text):
    if re.search(r'https?://|www\.|[\w.+-]+@[\w.-]+|(?:\d[\s-]?){7,}', text) or any(word in text for word in ('كلمة المرور', 'رقم جوالي', 'رقم هويتي', 'عنوان بيتي')):
        return '[رسالة مستبعدة من الذاكرة]'
    return text[:600]

def norm_ar(s):
    if not isinstance(s, str): return ''
    s = re.sub(r'[\u064b-\u065f\u0670]', '', s)
    s = re.sub(r'[إأآا]', 'ا', s)
    s = re.sub(r'[ة]', 'ه', s)
    s = re.sub(r'[ى]', 'ي', s)
    s = re.sub(r'[^\w\s]', '', s)
    return s.strip().casefold()

@dataclass(frozen=True)
class Message:
    id: str
    user_id: str
    text: str
    sender_name: str = ''

@dataclass(frozen=True)
class Reply:
    speaker: str
    text: str
    reason: str
    tokens: dict | None = None
    messages: tuple[str, ...] = ()

class Memory:
    def __init__(self, path, days=30):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.days = days
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS messages(room TEXT, id TEXT, uid TEXT, text TEXT, ts REAL, PRIMARY KEY(room, id));
        CREATE TABLE IF NOT EXISTS users(uid TEXT PRIMARY KEY, preference TEXT, ts REAL);
        CREATE TABLE IF NOT EXISTS quota(day TEXT PRIMARY KEY, calls INTEGER NOT NULL);
        ''')
        self.purge()

    def purge(self):
        cutoff = time.time() - self.days * 86400
        with self.db:
            self.db.execute('DELETE FROM messages WHERE ts<?', (cutoff,))
            self.db.execute('DELETE FROM users WHERE ts<?', (cutoff,))
            self.db.execute('DELETE FROM quota WHERE day<?', (datetime.fromtimestamp(cutoff, timezone.utc).date().isoformat(),))

    def add(self, room, message):
        with self.db:
            result = self.db.execute('INSERT OR IGNORE INTO messages VALUES(?,?,?,?,?)', (room, message.id, message.user_id, safe_text(message.text), time.time()))
            self.db.execute('DELETE FROM messages WHERE room=? AND rowid NOT IN (SELECT rowid FROM messages WHERE room=? ORDER BY rowid DESC LIMIT 200)', (room, room))
        return result.rowcount == 1

    def remember(self, message):
        match = re.fullmatch(r'\s*(?:لعبتي المفضلة|احب لعبة|أحب لعبة)\s*[:：]?\s*(البلياردو|الكيرم|كريزي 8|كرة الطاولة)[.!؟]?\s*', message.text)
        if match:
            with self.db:
                self.db.execute('INSERT INTO users VALUES(?,?,?) ON CONFLICT(uid) DO UPDATE SET preference=excluded.preference,ts=excluded.ts', (message.user_id, match[1], time.time()))

    def preference(self, uid):
        row = self.db.execute('SELECT preference FROM users WHERE uid=? AND ts>?', (uid, time.time() - self.days * 86400)).fetchone()
        return row[0] if row else None

    def forget(self, uid):
        with self.db:
            self.db.execute('DELETE FROM users WHERE uid=?', (uid,))
            self.db.execute('DELETE FROM messages WHERE uid=?', (uid,))

    def context(self, room, identities=None):
        rows = self.db.execute('SELECT uid, text FROM messages WHERE room=? AND ts>? ORDER BY rowid DESC LIMIT 12', (room, time.time() - 3600)).fetchall()
        participants = {}
        result = []
        for uid, text in reversed(rows):
            if uid not in participants:
                participants[uid] = 'participant-' + str(len(participants) + 1)
            identity = (identities or {}).get(uid)
            result.append({'speaker': participants[uid], 'text': text, **(identity or {})})
        return result

    def reserve_call(self, limit):
        day = datetime.now(timezone.utc).date().isoformat()
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO quota VALUES(?,0)', (day,))
            result = self.db.execute('UPDATE quota SET calls=calls+1 WHERE day=? AND calls<?', (day, limit))
        return result.rowcount == 1

    def close(self):
        self.db.close()

class Coordinator:
    def __init__(self, config, memory, scripts, provider=None):
        self.config = config
        self.memory = memory
        self.scripts = scripts
        self.provider = provider
        self.room = config['room']
        self.last_sent = -1e9
        self.turn = 0
        self.revision = 0
        self.script_index = 0
        self.line_index = 0
        self.identities = {}
        self.last_input = time.monotonic()
        self.initiative_revision = None
        self.threads = {}
        self.last_user_id = None
        self.bot_turns = 0

        # Multi-persona orchestration: track speakers to avoid mono-account chatter
        self.last_speaker_id = None
        self.recent_speakers = []
        self.turn_queue = []

        # 10,000+ Arabic Riddles & Trivia Encyclopedia
        self.riddles = []
        riddles_file = Path(__file__).resolve().parent / 'riddles.json'
        if riddles_file.exists():
            try:
                raw_data = json.loads(riddles_file.read_text(encoding='utf-8'))
                questions = raw_data.get('questions', []) if isinstance(raw_data, dict) else raw_data
                preferred_cats = {'فوازير وألغاز كلامية', 'ألغاز الأمثال والحكم', 'ألغاز تعريفية', 'ألغاز لغوية ومفردات', 'معلومات عامة خفيفة', 'ألغاز منطق وبديهة', 'ألغاز حروف وكلمات'}
                filtered = [q for q in questions if q.get('category') in preferred_cats and 5 <= len(q.get('question', '')) <= 150]
                self.riddles = filtered if filtered else questions
                random.seed(int(time.time()))
                random.shuffle(self.riddles)
            except Exception:
                pass

        self.current_riddle = None
        self.last_riddle_end = -1e9
        self.riddle_index = 0

    def active(self, now=None):
        hour = (now or datetime.now(ZoneInfo(self.config['timezone']))).hour
        def present(p):
            start, end = p.get('hours', [0, 24])
            return start <= hour < end if start < end else hour >= start or hour < end
        return [p for p in self.config['profiles'] if present(p)][:16]

    def ingest(self, message):
        if not message.id or not message.user_id or not message.text: return False
        fresh = self.memory.add(self.room, message)
        if fresh:
            self.memory.remember(message)
            self.revision += 1
            self.last_input = time.monotonic()
            self.last_user_id = message.user_id
            if message.user_id in self.identities:
                bot_pid = self.identities[message.user_id].get('persona_id')
                if bot_pid:
                    self.last_speaker_id = bot_pid
                    self.recent_speakers.append(bot_pid)
                    if len(self.recent_speakers) > 10:
                        self.recent_speakers.pop(0)
        return fresh

    def choose(self, text='', user_id=None, exclude_ids=None):
        active = self.active()
        if not active: return None
        exclude = set(exclude_ids or [])
        if self.last_speaker_id:
            exclude.add(self.last_speaker_id)

        candidates = [p for p in active if p['id'] not in exclude]
        if not candidates:
            candidates = [p for p in active if p['id'] != self.last_speaker_id]
            if not candidates: candidates = active

        # If addressed by handle or real name
        if text:
            addressed = [p for p in candidates if p['id'] in text or p.get('username','') in text or p.get('real_name','') in text or p['name'] in text]
            if addressed:
                return addressed[0]

        # Prioritize bots that haven't spoken in the last few turns
        fresh = [p for p in candidates if p['id'] not in self.recent_speakers[-4:]]
        pool = fresh if fresh else candidates
        profile = pool[self.turn % len(pool)]

        if user_id:
            if user_id not in self.threads and len(self.threads) >= 128:
                self.threads.pop(next(iter(self.threads)))
            self.threads[user_id] = (profile['id'], time.monotonic())
        return profile

    def ready(self):
        return time.monotonic() - self.last_sent >= self.config['cooldown_seconds']

    def sent(self, speaker_id=None):
        self.last_sent = time.monotonic()
        self.turn += 1
        if speaker_id:
            self.last_speaker_id = speaker_id
            self.recent_speakers.append(speaker_id)
            if len(self.recent_speakers) > 10:
                self.recent_speakers.pop(0)

    def idle(self, human_count):
        if human_count or not self.ready() or not self.scripts: return None
        lines = self.scripts[self.script_index % len(self.scripts)]
        line = lines[self.line_index % len(lines)]
        if line['speaker'] not in {p['id'] for p in self.active()}: return None
        self.line_index += 1
        if self.line_index == len(lines):
            self.line_index = 0
            self.script_index += 1
        return Reply(line['speaker'], line['text'], 'recorded')

    def start_riddle(self):
        if not self.riddles or self.current_riddle:
            return None
        riddle = self.riddles[self.riddle_index % len(self.riddles)]
        self.riddle_index += 1

        host = self.choose()
        if not host: return None

        raw_ans = riddle.get('answer', '')
        options = riddle.get('options', [])
        norm_ans = norm_ar(raw_ans)
        wrong_options = [o for o in options if norm_ar(o) != norm_ans]

        # Assign 4 distinct personas for this riddle sequence
        active_ids = [p['id'] for p in self.active() if p['id'] != host['id']]
        random.shuffle(active_ids)

        idle1_id = active_ids[0] if len(active_ids) > 0 else 'z8q'
        idle2_id = active_ids[1] if len(active_ids) > 1 else 'k5l'
        solver_id = active_ids[2] if len(active_ids) > 2 else 'd7w'
        tease_id = active_ids[3] if len(active_ids) > 3 else 'r9k'

        mode = self.riddle_index % 3

        self.current_riddle = {
            'riddle': riddle,
            'host': host,
            'answer': raw_ans,
            'norm_ans': norm_ans,
            'wrong_options': wrong_options,
            'mode': mode,
            'idle1_id': idle1_id,
            'idle2_id': idle2_id,
            'solver_id': solver_id,
            'tease_id': tease_id,
            'stage': 0,
            'next_stage_time': time.monotonic() + 8.5,
            'solved': False
        }

        intro = riddle.get('host_intro', 'يا جماعة لغز على السريع مين الذكي اللي يحله؟ 🧐🔥')
        q = riddle['question']
        return Reply(host['id'], f"{intro}\n{q}", 'riddle_start')

    def riddle_tick(self):
        if not self.current_riddle or self.current_riddle['solved']:
            return None
        cr = self.current_riddle
        now = time.monotonic()
        if now < cr['next_stage_time'] or not self.ready():
            return None

        stage = cr['stage']
        mode = cr['mode']
        ans = cr['answer']
        wrong = cr['wrong_options']
        profiles_by_id = {p['id']: p for p in self.active()}
        host = cr['host']

        def get_name(pid):
            p = profiles_by_id.get(pid, {})
            return p.get('real_name', p.get('name', pid))

        opt1 = wrong[0] if wrong else 'الخيار الأول'
        opt2 = wrong[1] if len(wrong) > 1 else (wrong[0] if wrong else 'الخيار الثاني')

        # MODE 0: Idle1 wrong -> Idle2 wrong -> Tease -> Solver solves -> Host confirms -> React
        if mode == 0:
            if stage == 0:
                cr['stage'] = 1
                cr['next_stage_time'] = now + 8.5
                templates = [
                    f'امممم وش رايكم.. اتوقع {opt1}؟ 🤔',
                    f'احس الجواب {opt1}، صح ولا غلط؟ 😂',
                    f'اتوقع {opt1} يا بنات! 💡',
                    f'شكله {opt1}، شرايكم؟ 🤔'
                ]
                return Reply(cr['idle1_id'], random.choice(templates), 'riddle_guess')

            elif stage == 1:
                cr['stage'] = 2
                cr['next_stage_time'] = now + 7.5
                templates = [
                    f'لا لا اتوقع {opt2} والله أعلم 😂',
                    f'يمكن {opt2}؟ احترت وربي 😭',
                    f'احس {opt2} أقرب شي للصح 🤔'
                ]
                return Reply(cr['idle2_id'], random.choice(templates), 'riddle_guess')

            elif stage == 2:
                cr['stage'] = 3
                cr['next_stage_time'] = now + 8.0
                name2 = get_name(cr['idle2_id'])
                templates = [
                    f'هههههه وش جاب {opt2} للغز يا {name2}؟ ركزي شوي بس! 😭',
                    f'لا مستحيل هههههه ضحكتيني والله، فكروا زين! 😂',
                    f'شكلنا جبنا العيد بالتخمينات 😂 مين ينقذنا؟'
                ]
                return Reply(cr['tease_id'], random.choice(templates), 'riddle_tease')

            elif stage == 3:
                cr['stage'] = 4
                cr['next_stage_time'] = now + 5.0
                templates = [
                    f'خلاص وضحت عندي! أكيد {ans} صح؟ 🔥',
                    f'عرفتهاااا خلاص! أكيد {ans} ما يبيلها كلام 😎',
                    f'لقيتها! الجواب هو {ans} صح يا {host.get("real_name", "نورة")}؟ 👏'
                ]
                return Reply(cr['solver_id'], random.choice(templates), 'riddle_solve')

            elif stage == 4:
                cr['stage'] = 5
                cr['next_stage_time'] = now + 5.5
                solver_name = get_name(cr['solver_id'])
                templates = [
                    f'كفووو يا {solver_name}! صح عليك وربي الجواب هو {ans} 👏🔥',
                    f'صح عليك يا {solver_name}! جبتيها وربي، الجواب {ans} ✨',
                    f'كفو والله يا {solver_name}! أهنيك الجواب الصح {ans} 👏'
                ]
                return Reply(host['id'], random.choice(templates), 'riddle_confirm')

            elif stage == 5:
                cr['solved'] = True
                self.current_riddle = None
                self.last_riddle_end = time.monotonic()
                solver_name = get_name(cr['solver_id'])
                templates = [
                    f'ما شاء الله عليك يا {solver_name} لقطتيها قبلي 😂👏',
                    f'كنت بكتبها والله وسبقتيني قهر 😭💔',
                    f'كفووو يا ذيبة تستاهلين الفوز 🔥'
                ]
                return Reply(cr['idle1_id'], random.choice(templates), 'riddle_react')

        # MODE 1: Idle1 wrong -> Tease -> Ask Human -> Solver solves -> Host confirms
        elif mode == 1:
            if stage == 0:
                cr['stage'] = 1
                cr['next_stage_time'] = now + 8.5
                return Reply(cr['idle1_id'], f'احس الجواب {opt1}، صح ولا تخمين شاطح؟ 😂', 'riddle_guess')

            elif stage == 1:
                cr['stage'] = 2
                cr['next_stage_time'] = now + 7.5
                name1 = get_name(cr['idle1_id'])
                return Reply(cr['tease_id'], f'هههههه من جدك يا {name1}؟ مستحيل {opt1} عاد 🤣', 'riddle_tease')

            elif stage == 2:
                cr['stage'] = 3
                cr['next_stage_time'] = now + 9.5
                return Reply(cr['idle2_id'], 'يا جماعة تكفون وين أذكياء الشات؟ شكلنا ضيعنا الطاسة 😂 ساعدونا بالحل!', 'riddle_call_human')

            elif stage == 3:
                cr['stage'] = 4
                cr['next_stage_time'] = now + 5.0
                return Reply(cr['solver_id'], f'عرفتهااا خلاص! أكيد {ans} صح؟ 🔥', 'riddle_solve')

            elif stage == 4:
                cr['solved'] = True
                self.current_riddle = None
                self.last_riddle_end = time.monotonic()
                solver_name = get_name(cr['solver_id'])
                return Reply(host['id'], f'كفووو يا {solver_name}! صح عليك وربي، الجواب هو {ans} 👏✨', 'riddle_confirm')

        # MODE 2: Idle1 wrong -> Idle2 wrong -> Solver solves -> Host confirms -> Tease
        else:
            if stage == 0:
                cr['stage'] = 1
                cr['next_stage_time'] = now + 8.5
                return Reply(cr['idle1_id'], f'اتوقع {opt1} يا جماعة! 💡', 'riddle_guess')

            elif stage == 1:
                cr['stage'] = 2
                cr['next_stage_time'] = now + 7.5
                return Reply(cr['idle2_id'], f'شكله {opt2}، وش رايكم بنات؟ 🤔', 'riddle_guess')

            elif stage == 2:
                cr['stage'] = 3
                cr['next_stage_time'] = now + 5.0
                return Reply(cr['solver_id'], f'لقيتها خلاص! الجواب هو {ans} بدون تفكير 😎', 'riddle_solve')

            elif stage == 3:
                cr['stage'] = 4
                cr['next_stage_time'] = now + 5.5
                solver_name = get_name(cr['solver_id'])
                return Reply(host['id'], f'وربي كفو يا {solver_name}! جبتيها بالملي، الجواب هو {ans} 👏', 'riddle_confirm')

            elif stage == 4:
                cr['solved'] = True
                self.current_riddle = None
                self.last_riddle_end = time.monotonic()
                return Reply(cr['tease_id'], 'يا حظك كنت على وشك أرسلها والله وسبقتيني 😭😂', 'riddle_tease')

        return None

    async def respond(self, message):
        if not self.ready(): return None
        text = message.text.strip()
        is_human = (message.user_id not in self.identities)

        # 1. Human participation in Active Riddle
        if is_human and self.current_riddle and not self.current_riddle['solved']:
            cr = self.current_riddle
            raw_ans = cr['answer']
            norm_ans = cr['norm_ans']
            clean_text = norm_ar(text)
            ans_no_al = norm_ans.removeprefix('ا')
            is_correct = (norm_ans in clean_text) or (len(ans_no_al) >= 3 and ans_no_al in clean_text)
            host = cr['host']
            human_name = message.sender_name or 'يا بطل'

            # A) Correct answer by human player
            if is_correct:
                cr['solved'] = True
                self.current_riddle = None
                self.last_riddle_end = time.monotonic()
                praise_bot = self.choose(exclude_ids=[host['id']])
                if praise_bot:
                    self.turn_queue.append(Reply(praise_bot['id'], f'ما شاء الله عليك يا {human_name} جبتها وحنا من الصبح نحوس 😂👏', 'riddle_praise'))
                return Reply(host['id'], f'كفووووو يا {human_name}! جبتها صح وربي 🔥👏 الجواب هو {raw_ans}', 'riddle_solve_human')

            # B) Human greeted or joined
            if any(w in clean_text for w in ('سلام', 'صباح', 'مساء', 'هلا', 'وش تسوون', 'وش السالفه', 'وش فيه', 'علموني', 'ايش تسوون')):
                helper = self.choose(exclude_ids=[host['id']]) or host
                q = cr['riddle']['question']
                return Reply(helper['id'], f'يا هلا والله {human_name}! نورت، تعال ساعدنا قاعدين نحل هاللغز: ({q})، وش تتوقع؟ 🤔', 'riddle_invite')

            # C) Human wrong guess
            if len(text) <= 40 and not any(term in text for term in ('اسمك', 'بنت', 'ولد', 'بوت')):
                return Reply(host['id'], f'مالك لواء يا {human_name} 😂 قربت بس مو هي، فكر فيها شوي!', 'riddle_wrong_guess')

        # 2. General Queries & Identity
        profile = self.choose(message.text, message.user_id)
        if not profile: return None
        real_name = profile.get('real_name', profile.get('name'))
        def local(value): return Reply(profile['id'], value, 'local')

        if any(term in text for term in ('وش اسمك', 'وش اساميكم', 'وش اسماؤكم', 'وش اسمائكم', 'مين انتم', 'مين انتو', 'من انتم', 'من انتو', 'وش اسمك الحقيقي', 'وش اساميكم الحقيقية', 'اسمك ايش', 'اسمك ايه')):
            return local(f'اسمي {real_name} واليوزر اختصار لي 🌸')
        if any(term in text for term in ('ذكر ولا انثى', 'ذكر ولا أنثى', 'انثى ولا ذكر', 'أنثى ولا ذكر', 'بنت ولا ولد', 'ولد ولا بنت', 'انتي بنت', 'أنتي بنت', 'انت بنت', 'أنت بنت', 'انت ولد', 'أنت ولد', 'انتي ولد', 'أنتي ولد', 'وش جنسك', 'بنت ولا رجال', 'رجال ولا بنت', 'بنت؟', 'ذكر؟', 'انثى؟', 'أنثى؟', 'انتم بنات', 'انتو بنات')):
            return local(f'أكيد بنت، اسمي {real_name} 🌸')
        if any(term in text for term in ('انت بوت', 'أنت بوت', 'انتي بوت', 'أنتي بوت', 'انت انسان', 'أنت إنسان', 'انتي انسانة', 'أنتي إنسانة', 'انت ريبورت', 'أنت ريبورت', 'انت روبوت', 'أنت روبوت', 'ذكاء اصطناعي')):
            return local('هههههه وش دعوة أكيد بنت حقيقية، أجل شبح؟ 😂')
        if any(term in text for term in ('سناب', 'واتساب', 'رقمك', 'صورتك')):
            return local('ما عندي حساب تواصل أعطيك إياه، خل سوالفنا هنا 😄')
        if any(term in text for term in ('كم الساعة', 'كم الساعه')):
            clock = datetime.now(ZoneInfo(self.config['timezone'])).strftime('%H:%M')
            return local(f'الساعة الحين {clock} بتوقيت السعودية.')
        if text in ('انس كلامي', 'احذف ذاكرتي', 'احذف معلوماتي'):
            self.memory.forget(message.user_id)
            return local('تم، حذفت اللي حفظته عنك في ذاكرة التجربة.')
        if text in ('السلام عليكم', 'سلام عليكم'):
            return local('وعليكم السلام، يا هلا والله! نورتِ/نورت 🌸')
        if any(term in text for term in ('تذكرني', 'لعبتي المفضلة', 'لعبتي المفضله')):
            preference = self.memory.preference(message.user_id)
            return local(f'أذكر إنك قلت لعبتك المفضلة {preference}.' if preference else 'ما خبرتك ذكرت لي شي معين من قبل.')
        if any(term in text for term in ('رصيدي', 'كم فوز', 'كم عمري', 'نتيجة', 'نتيجه', 'سعر', 'عملات')):
            return local('ما عندي وصول لمعلومة أكيدة عن هالشي، شيّك من المنصة.')

        # 3. Model Response (Gemini)
        return await self.generate_reply(profile, self.memory.preference(message.user_id), 'reply')

    async def initiative(self, human_count=0):
        if not self.ready() or self.initiative_revision == self.revision: return None
        quiet = self.config.get('initiative_seconds', 25)
        if time.monotonic() - max(self.last_input, self.last_sent) < quiet: return None
        self.initiative_revision = self.revision

        now = time.monotonic()
        # Launch Riddle if enabled and cool (50s interval between riddles)
        if self.riddles and not self.current_riddle and (now - self.last_riddle_end >= 50):
            reply = self.start_riddle()
            if reply: return reply

        profile = self.choose()
        if not profile or not self.provider: return None
        return await self.generate_reply(profile, None, 'initiative')

    async def generate_reply(self, profile, preference, mode):
        if not self.provider or not self.memory.reserve_call(self.config['daily_model_calls']): return None
        try:
            context = self.memory.context(self.room, self.identities)
            answer = await self.provider.generate({**profile, 'conversation_mode': mode}, context, preference)
        except Exception:
            return None
        text = ''
        if isinstance(answer, dict):
            text = answer.get('text', '') or (answer.get('messages', [''])[0] if answer.get('messages') else '')
        elif isinstance(answer, (list, tuple)):
            text = answer[0] if answer else ''
        else:
            text = str(answer or '')
        text = text.strip()
        if not text or not valid_output(text): return None
        normalize = lambda v: re.sub(r'[\W_]+', '', v).casefold()
        if any(normalize(row.get('text', '')) == normalize(text) for row in context[-6:]): return None
        tokens = getattr(self.provider, 'last_usage', None)
        return Reply(profile['id'], text, 'initiative' if mode == 'initiative' else 'model', tokens)

def valid_output(text):
    if not isinstance(text, str) or not 1 <= len(text) <= 280: return False
    if not re.search(r'[\u0600-\u06ff]', text): return False
    if re.search(r'https?://|www\.|[\w.+-]+@[\w.-]+|(?:\+?966|05)\d{8}|\d{7,}', text): return False
    return not any(s in text for s in ('أنا روبوت', 'انا روبوت', 'أنا ريبورت', 'انا ريبورت', 'أنا بوت', 'انا بوت', 'أنا شخصية آلية', 'شخصية آلية', 'ذكاء اصطناعي', 'نموذج لغوي', 'بصفتي نموذج', 'رقم جوالي', 'حسابي سناب', 'أنا إنسان', 'انا انسان', 'أنا شخص حقيقي'))

def load_config(path):
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(config.get('room'), str) or not re.fullmatch(r'[a-z][a-z0-9_-]{1,31}', config['room']): raise ValueError('Invalid room')
    ZoneInfo(config['timezone'])
    profiles = config['profiles']
    if type(config.get('initiative_seconds', 45)) is not int or not 10 <= config.get('initiative_seconds', 45) <= 600: raise ValueError('Invalid initiative_seconds')
    if not profiles or len(profiles) > 100 or len({p['id'] for p in profiles}) != len(profiles): raise ValueError('Invalid profiles')
    for key, low, high in [('daily_model_calls', 0, 10000), ('cooldown_seconds', 2, 3600), ('reply_delay_seconds', 0, 15), ('idle_seconds', 30, 3600), ('memory_days', 1, 30)]:
        if not isinstance(config[key], int) or not low <= config[key] <= high: raise ValueError('Invalid ' + key)
    for p in profiles:
        if p.get('gender', 'unspecified') not in ('male', 'female', 'unspecified'): raise ValueError('Invalid profile gender')
        if not re.fullmatch(r'[a-z][a-z0-9_]{1,30}', p['id']) or not p['name'] or not re.fullmatch(r'PLAZR_BOT_[A-Z0-9_]+_SESSION', p['session_env']): raise ValueError('Invalid profile')
        a, b = p['hours']
        if not 0 <= a <= 23 or not 1 <= b <= 24: raise ValueError('Invalid schedule')
    return config
