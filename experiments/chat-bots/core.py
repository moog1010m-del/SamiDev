"""Isolated orchestration, Persistent Agent State, and Social Context memory."""
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
    if not isinstance(s, str):
        return ''
    s = re.sub(r'[\u064b-\u065f\u0670]', '', s)
    s = re.sub(r'[إأآا]', 'ا', s)
    s = re.sub(r'[ة]', 'ه', s)
    s = re.sub(r'[ى]', 'ي', s)
    s = re.sub(r'[^\w\s]', '', s)
    return s.strip().casefold()


RUDE_TERMS = (
    'سراويل', 'سراويلكم', 'فسخو', 'افسخ', 'فصخو', 'افصخ', 'كل زق', 'كلي زق', 'زق',
    'كلب', 'كلبه', 'حيوان', 'حيوانه', 'غبيه', 'غبي', 'تفو', 'قحبه', 'شرموط', 'منيوك',
    'وسخ', 'وسخه', 'انقلع', 'انقلعي', 'كلي تبن', 'كل تبن', 'تافهين', 'سافل', 'قذر'
)

IGNORED_TERMS = (
    'متجاهلين', 'متجاهليني', 'مطنشين', 'مطنشيني', 'ليش محد يرد', 'محد يرد',
    'ساحبين علي', 'ساحبين علينا', 'ردوا علي', 'ماتردون', 'ما تردون'
)

APOLOGY_TERMS = (
    'اسف', 'آسف', 'اعتذر', 'أعتذر', 'امزح', 'أمزح', 'نمزح', 'حقكم علي', 'سوري', 'معليش'
)


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
        CREATE TABLE IF NOT EXISTS messages(room TEXT, id TEXT, uid TEXT, text TEXT, ts REAL, sender_name TEXT DEFAULT '', PRIMARY KEY(room, id));
        CREATE TABLE IF NOT EXISTS users(uid TEXT PRIMARY KEY, preference TEXT, ts REAL);
        CREATE TABLE IF NOT EXISTS quota(day TEXT PRIMARY KEY, calls INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS agent_state(
            bot_id TEXT PRIMARY KEY,
            mood TEXT,
            activity TEXT,
            last_reply TEXT,
            last_target_uid TEXT,
            last_target_name TEXT,
            ts REAL
        );
        CREATE TABLE IF NOT EXISTS social_profiles(
            uid TEXT PRIMARY KEY,
            display_name TEXT,
            attitude TEXT,
            last_message TEXT,
            interactions INTEGER DEFAULT 0,
            ts REAL
        );
        ''')
        # Ensure sender_name column exists on older SQLite databases
        cols = {row[1] for row in self.db.execute("PRAGMA table_info(messages)").fetchall()}
        if 'sender_name' not in cols:
            with self.db:
                self.db.execute("ALTER TABLE messages ADD COLUMN sender_name TEXT DEFAULT ''")
        self.purge()

    def purge(self):
        cutoff = time.time() - self.days * 86400
        with self.db:
            self.db.execute('DELETE FROM messages WHERE ts<?', (cutoff,))
            self.db.execute('DELETE FROM users WHERE ts<?', (cutoff,))
            self.db.execute('DELETE FROM social_profiles WHERE ts<?', (cutoff,))
            self.db.execute('DELETE FROM quota WHERE day<?', (datetime.fromtimestamp(cutoff, timezone.utc).date().isoformat(),))

    def add(self, room, message):
        clean_sender = (message.sender_name or '').strip()[:64]
        with self.db:
            result = self.db.execute(
                'INSERT OR IGNORE INTO messages(room, id, uid, text, ts, sender_name) VALUES(?,?,?,?,?,?)',
                (room, message.id, message.user_id, safe_text(message.text), time.time(), clean_sender)
            )
            self.db.execute(
                'DELETE FROM messages WHERE room=? AND rowid NOT IN (SELECT rowid FROM messages WHERE room=? ORDER BY rowid DESC LIMIT 200)',
                (room, room)
            )
        return result.rowcount == 1

    def remember(self, message):
        match = re.fullmatch(r'\s*(?:لعبتي المفضلة|احب لعبة|أحب لعبة)\s*[:：]?\s*(البلياردو|الكيرم|كريزي 8|كرة الطاولة)[.!؟]?\s*', message.text)
        if match:
            with self.db:
                self.db.execute(
                    'INSERT INTO users VALUES(?,?,?) ON CONFLICT(uid) DO UPDATE SET preference=excluded.preference,ts=excluded.ts',
                    (message.user_id, match[1], time.time())
                )

    def update_social_profile(self, uid: str, display_name: str, text: str, attitude: str | None = None):
        if not uid:
            return
        now = time.time()
        row = self.db.execute('SELECT display_name, attitude, interactions FROM social_profiles WHERE uid=?', (uid,)).fetchone()
        cur_name = (display_name or (row[0] if row else '') or '').strip()[:64]
        cur_att = attitude or (row[1] if row else 'محترم وطبيعي')
        count = (row[2] if row else 0) + 1
        with self.db:
            self.db.execute(
                '''INSERT INTO social_profiles(uid, display_name, attitude, last_message, interactions, ts)
                   VALUES(?,?,?,?,?,?)
                   ON CONFLICT(uid) DO UPDATE SET
                   display_name=excluded.display_name,
                   attitude=excluded.attitude,
                   last_message=excluded.last_message,
                   interactions=excluded.interactions,
                   ts=excluded.ts''',
                (uid, cur_name, cur_att, safe_text(text)[:200], count, now)
            )

    def get_social_profile(self, uid: str) -> dict:
        if not uid:
            return {}
        row = self.db.execute(
            'SELECT display_name, attitude, last_message, interactions FROM social_profiles WHERE uid=?',
            (uid,)
        ).fetchone()
        pref = self.preference(uid)
        if not row:
            return {'preference': pref} if pref else {}
        return {
            'display_name': row[0] or '',
            'attitude': row[1] or 'طبيعي',
            'last_message': row[2] or '',
            'interactions': row[3] or 0,
            'preference': pref
        }

    def get_agent_state(self, bot_id: str, default_mood: str = 'رايقة ومبسوطة') -> dict:
        row = self.db.execute(
            'SELECT mood, activity, last_reply, last_target_uid, last_target_name, ts FROM agent_state WHERE bot_id=?',
            (bot_id,)
        ).fetchone()
        if not row:
            return {
                'mood': default_mood,
                'activity': 'سوالف وتفاعل في روم المجلس',
                'last_reply': '',
                'last_target_uid': '',
                'last_target_name': ''
            }
        mood, activity, last_reply, last_uid, last_name, ts = row
        # Decay temporary annoyance after 5 minutes of calm
        if time.time() - (ts or 0) > 300:
            mood = default_mood
        return {
            'mood': mood or default_mood,
            'activity': activity or 'سوالف وتفاعل في روم المجلس',
            'last_reply': last_reply or '',
            'last_target_uid': last_uid or '',
            'last_target_name': last_name or ''
        }

    def set_agent_state(self, bot_id: str, mood: str | None = None, activity: str | None = None,
                        last_reply: str | None = None, last_target_uid: str | None = None,
                        last_target_name: str | None = None):
        cur = self.get_agent_state(bot_id)
        with self.db:
            self.db.execute(
                '''INSERT INTO agent_state(bot_id, mood, activity, last_reply, last_target_uid, last_target_name, ts)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(bot_id) DO UPDATE SET
                   mood=excluded.mood,
                   activity=excluded.activity,
                   last_reply=excluded.last_reply,
                   last_target_uid=excluded.last_target_uid,
                   last_target_name=excluded.last_target_name,
                   ts=excluded.ts''',
                (
                    bot_id,
                    mood if mood is not None else cur['mood'],
                    activity if activity is not None else cur['activity'],
                    last_reply if last_reply is not None else cur['last_reply'],
                    last_target_uid if last_target_uid is not None else cur['last_target_uid'],
                    last_target_name if last_target_name is not None else cur['last_target_name'],
                    time.time()
                )
            )

    def recent_bot_messages(self, room: str, bot_uid: str, limit: int = 3) -> list[str]:
        if not bot_uid:
            return []
        rows = self.db.execute(
            'SELECT text FROM messages WHERE room=? AND uid=? ORDER BY rowid DESC LIMIT ?',
            (room, bot_uid, limit)
        ).fetchall()
        return [r[0] for r in reversed(rows) if r[0]]

    def preference(self, uid):
        row = self.db.execute('SELECT preference FROM users WHERE uid=? AND ts>?', (uid, time.time() - self.days * 86400)).fetchone()
        return row[0] if row else None

    def forget(self, uid):
        with self.db:
            self.db.execute('DELETE FROM users WHERE uid=?', (uid,))
            self.db.execute('DELETE FROM social_profiles WHERE uid=?', (uid,))
            self.db.execute('DELETE FROM messages WHERE uid=?', (uid,))

    def context(self, room, identities=None):
        rows = self.db.execute(
            'SELECT uid, text, sender_name FROM messages WHERE room=? AND ts>? ORDER BY rowid DESC LIMIT 12',
            (room, time.time() - 3600)
        ).fetchall()
        participants = {}
        result = []
        for uid, text, sender_name in reversed(rows):
            if uid not in participants:
                participants[uid] = 'participant-' + str(len(participants) + 1)
            identity = (identities or {}).get(uid)
            entry = {'speaker': participants[uid], 'text': text, **(identity or {})}
            if not identity and sender_name:
                entry['sender_name'] = sender_name
                entry['name'] = sender_name
                entry['kind'] = 'human'
            result.append(entry)
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

        # Multi-persona orchestration
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
                preferred_cats = {
                    'فوازير وألغاز كلامية', 'ألغاز الأمثال والحكم', 'ألغاز تعريفية',
                    'ألغاز لغوية ومفردات', 'معلومات عامة خفيفة', 'ألغاز منطق وبديهة', 'ألغاز حروف وكلمات'
                }
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
        if not message.id or not message.user_id or not message.text:
            return False
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
            else:
                # Track human speaker profile in social memory
                norm_txt = norm_ar(message.text)
                attitude = None
                if any(norm_ar(w) in norm_txt for w in RUDE_TERMS):
                    attitude = 'تجاوز حدود الأدب مؤخراً'
                elif any(norm_ar(w) in norm_txt for w in APOLOGY_TERMS):
                    attitude = 'اعتذر ولطّف الأجواء'
                self.memory.update_social_profile(message.user_id, message.sender_name, message.text, attitude)
        return fresh

    def choose(self, text='', user_id=None, exclude_ids=None):
        active = self.active()
        if not active:
            return None
        exclude = set(exclude_ids or [])

        # 1. Explicit mention by username/name in chat ALWAYS wins (even if last_speaker_id)
        if text:
            text_lower = text.casefold()
            for p in active:
                if p['id'] in exclude:
                    continue
                if (
                    p['id'].casefold() in text_lower
                    or p.get('username', '').casefold() in text_lower and p.get('username')
                    or p['name'].casefold() in text_lower
                ):
                    if user_id and user_id not in self.identities:
                        self.threads[user_id] = (p['id'], time.monotonic())
                    return p

        # 2. If human is in an active conversation thread, maintain persona continuity!
        is_human = bool(user_id and user_id not in self.identities)
        if is_human and user_id in self.threads:
            threaded_id, ts = self.threads[user_id]
            if time.monotonic() - ts <= 120 and threaded_id not in exclude:
                matched = next((p for p in active if p['id'] == threaded_id), None)
                if matched:
                    self.threads[user_id] = (matched['id'], time.monotonic())
                    return matched

        # 3. Otherwise rotate among active personas (avoiding same bot talking to itself)
        if self.last_speaker_id:
            exclude.add(self.last_speaker_id)

        candidates = [p for p in active if p['id'] not in exclude]
        if not candidates:
            candidates = [p for p in active if p['id'] != self.last_speaker_id] or active

        fresh = [p for p in candidates if p['id'] not in self.recent_speakers[-4:]]
        pool = fresh if fresh else candidates
        profile = pool[self.turn % len(pool)]

        if is_human:
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
        if human_count or not self.ready() or not self.scripts:
            return None
        lines = self.scripts[self.script_index % len(self.scripts)]
        line = lines[self.line_index % len(lines)]
        if line['speaker'] not in {p['id'] for p in self.active()}:
            return None
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
        if not host:
            return None

        raw_ans = riddle.get('answer', '')
        options = riddle.get('options', [])
        norm_ans = norm_ar(raw_ans)
        wrong_options = [o for o in options if norm_ar(o) != norm_ans]

        active_ids = [p['id'] for p in self.active() if p['id'] != host['id']]
        random.shuffle(active_ids)

        idle1_id = active_ids[0] if len(active_ids) > 0 else 'z8qx'
        idle2_id = active_ids[1] if len(active_ids) > 1 else 'k5lp'
        solver_id = active_ids[2] if len(active_ids) > 2 else 'd7wsx'
        tease_id = active_ids[3] if len(active_ids) > 3 else 'r9kx'

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
        self.memory.set_agent_state(host['id'], mood='متحمسة ومصحصحة', activity=f'طرحت لغز في الغرفة: {q[:50]}')
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
        host = cr['host']

        opt1 = wrong[0] if wrong else 'الخيار الأول'
        opt2 = wrong[1] if len(wrong) > 1 else (wrong[0] if wrong else 'الخيار الثاني')

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
                id2 = cr['idle2_id']
                templates = [
                    f'هههههه وش جاب {opt2} للغز يا {id2}؟ ركزي شوي بس! 😭',
                    f'لا مستحيل يا {id2} هههههه ضحكتيني والله، فكروا زين! 😂',
                    f'شكلنا جبنا العيد بالتخمينات 😂 مين ينقذنا؟'
                ]
                return Reply(cr['tease_id'], random.choice(templates), 'riddle_tease')

            elif stage == 3:
                cr['stage'] = 4
                cr['next_stage_time'] = now + 5.0
                host_id = host['id']
                templates = [
                    f'خلاص وضحت عندي! أكيد {ans} صح؟ 🔥',
                    f'عرفتهاااا خلاص! أكيد {ans} ما يبيلها كلام 😎',
                    f'لقيتها! الجواب هو {ans} صح يا {host_id}؟ 👏'
                ]
                return Reply(cr['solver_id'], random.choice(templates), 'riddle_solve')

            elif stage == 4:
                cr['stage'] = 5
                cr['next_stage_time'] = now + 5.5
                solver_id = cr['solver_id']
                templates = [
                    f'كفووو يا {solver_id}! صح عليك وربي الجواب هو {ans} 👏🔥',
                    f'صح عليك يا {solver_id}! جبتيها وربي، الجواب {ans} ✨',
                    f'كفو والله يا {solver_id}! أهنيك الجواب الصح {ans} 👏'
                ]
                return Reply(host['id'], random.choice(templates), 'riddle_confirm')

            elif stage == 5:
                cr['solved'] = True
                self.current_riddle = None
                self.last_riddle_end = time.monotonic()
                solver_id = cr['solver_id']
                templates = [
                    f'ما شاء الله عليك يا {solver_id} لقطتيها قبلي 😂👏',
                    f'كنت بكتبها والله وسبقتيني قهر 😭💔',
                    f'كفووو يا ذيبة تستاهلين الفوز 🔥'
                ]
                return Reply(cr['idle1_id'], random.choice(templates), 'riddle_react')

        elif mode == 1:
            if stage == 0:
                cr['stage'] = 1
                cr['next_stage_time'] = now + 8.5
                return Reply(cr['idle1_id'], f'احس الجواب {opt1}، صح ولا تخمين شاطح؟ 😂', 'riddle_guess')

            elif stage == 1:
                cr['stage'] = 2
                cr['next_stage_time'] = now + 7.5
                id1 = cr['idle1_id']
                return Reply(cr['tease_id'], f'هههههه من جدك يا {id1}؟ مستحيل {opt1} عاد 🤣', 'riddle_tease')

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
                solver_id = cr['solver_id']
                return Reply(host['id'], f'كفووو يا {solver_id}! صح عليك وربي، الجواب هو {ans} 👏✨', 'riddle_confirm')

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
                solver_id = cr['solver_id']
                return Reply(host['id'], f'وربي كفو يا {solver_id}! جبتيها بالملي، الجواب هو {ans} 👏', 'riddle_confirm')

            elif stage == 4:
                cr['solved'] = True
                self.current_riddle = None
                self.last_riddle_end = time.monotonic()
                return Reply(cr['tease_id'], 'يا حظك كنت على وشك أرسلها والله وسبقتيني 😭😂', 'riddle_tease')

        return None

    def _build_social_and_agent_state(self, profile: dict, message: Message | None, mode: str) -> tuple[dict, dict]:
        my_id = profile['id']
        default_mood = profile.get('default_mood', 'رايقة ومبسوطة')
        agent_state = self.memory.get_agent_state(my_id, default_mood)

        # Find bot's own UID to fetch her recent statements
        bot_uid = next((uid for uid, info in self.identities.items() if info.get('persona_id') == my_id), '')
        my_recent = self.memory.recent_bot_messages(self.room, bot_uid, limit=3)
        if agent_state.get('last_reply') and agent_state['last_reply'] not in my_recent:
            my_recent.append(agent_state['last_reply'])
        agent_state['my_recent_messages'] = my_recent[-3:]

        if not message:
            return agent_state, {
                'speaker_name': '',
                'speaker_role': 'مبادرة ذاتية منكِ في الغرفة',
                'addressee': 'أهل الغرفة بشكل عام',
                'intent': mode,
                'trigger_text': '',
                'speaker_memory': {},
                'directive': 'افتحي سالفة سعودية عفوية أو علقي بخفة دم بصوتكِ الشخصي كمؤنث.'
            }

        is_bot_speaker = message.user_id in self.identities
        if is_bot_speaker:
            bot_info = self.identities[message.user_id]
            speaker_name = bot_info.get('persona_id') or bot_info.get('name') or 'صديقتك'
            speaker_role = f"صديقتكِ في الغرفة ({speaker_name})"
            speaker_memory = {'relationship': 'صديقتكِ وزميلتكِ في روم المجلس'}
        else:
            speaker_memory = self.memory.get_social_profile(message.user_id)
            speaker_name = (message.sender_name or speaker_memory.get('display_name') or '').strip()
            speaker_role = f"لاعب حقيقي في الغرفة اسمه ({speaker_name})" if speaker_name else "لاعب حقيقي في الغرفة"

        text = message.text.strip()
        clean_txt = norm_ar(text)

        # Determine addressee
        text_lower = text.casefold()
        if my_id.casefold() in text_lower or profile['name'].casefold() in text_lower:
            addressee = f"موجهة لكِ أنتِ بالاسم ({my_id})"
        elif any(p['id'].casefold() in text_lower for p in self.config['profiles'] if p['id'] != my_id):
            other_id = next(p['id'] for p in self.config['profiles'] if p['id'] != my_id and p['id'].casefold() in text_lower)
            addressee = f"موجهة لصديقتكِ ({other_id}) وأنتِ تشاركين في الرد"
        elif not is_bot_speaker and message.user_id in self.threads and self.threads[message.user_id][0] == my_id:
            addressee = f"المتحدث ({speaker_name or 'اللاعب'}) يكمل حواره المباشر معكِ أنتِ ({my_id})"
        else:
            addressee = "حديث موجه للغرفة وأنتِ تردين عليه"

        # Determine intent, update mood & directive
        disp = speaker_name if speaker_name else 'اللاعب'
        if any(norm_ar(w) in clean_txt for w in RUDE_TERMS):
            intent = 'inappropriate_or_rude'
            mood = 'منزعجة وحازمة (ترفض قلة الأدب وترد بكرامة)'
            activity = f'ترد بحزم على تجاوز من {disp}'
            directive = (
                f"المتحدث ({disp}) كتب كلاماً غير لائق وعيب ({text}). "
                f"ردي عليه أنتِ بصفتكِ ({my_id}) بحزم وكرامة ووقفيه عند حده (مثال: عيب هالكلام يا {disp} احترم نفسك والموجودين). "
                f"تحذير: اسمكِ أنتِ هو {my_id}، فلا تقولي (يا {my_id}) نهائياً، بل خاطبي ({disp})!"
            )
        elif any(norm_ar(w) in clean_txt for w in IGNORED_TERMS):
            intent = 'feeling_ignored'
            mood = 'لطيفة ومرحبة وتعتذر بذوق'
            activity = f'ترحب باللاعب {disp} وتعتذر عن الانشغال'
            directive = (
                f"اللاعب ({disp}) يعاتبكم ويظن أنكم متجاهلينه. "
                f"اعتذري منه بلطافة وذوق (مثلاً كنا مندمجين باللغز أو السوالف) ورحبي فيه باسمه ({disp})."
            )
        elif any(norm_ar(w) in clean_txt for w in APOLOGY_TERMS):
            intent = 'apology'
            mood = 'هادية ومتقبلة للاعتذار'
            activity = f'تتقبل اعتذار {disp} وتلطف الجو'
            directive = f"المتحدث ({disp}) يعتذر أو يوضح أنه يمزح. تقبلي كلامه بذوق ولطفي الأجواء."
        elif mode == 'welcome' or any(w in clean_txt for w in ('سلام عليكم', 'السلام عليكم', 'مساء الخير', 'صباح الخير')):
            intent = 'welcome'
            mood = 'مرحبة وبشوشة'
            activity = f'ترحب بدخول {disp} للغرفة'
            directive = f"المتحدث ({disp}) يلقي التحية على الغرفة. ردي عليه السلام بحفاوة باسمه ({disp}) واسأليه عن حاله (كيفك؟)."
        else:
            intent = mode
            mood = agent_state.get('mood', default_mood)
            activity = f'تسولف مع {disp} في المجلس'
            directive = (
                f"ردي على رسالة ({disp}): \"{text}\" بشكل طبيعي ومباشر كفتاة سعودية حسابها ({my_id}). "
                f"تحدثي بصيغة المتكلمة المؤنثة (أنا) ولا تنادي ({disp}) باسمكِ ({my_id}) أبداً."
            )

        self.memory.set_agent_state(my_id, mood=mood, activity=activity, last_target_uid=message.user_id, last_target_name=speaker_name)
        agent_state['mood'] = mood
        agent_state['activity'] = activity

        social_context = {
            'speaker_name': speaker_name,
            'speaker_role': speaker_role,
            'addressee': addressee,
            'intent': intent,
            'trigger_text': text,
            'speaker_memory': speaker_memory,
            'directive': directive
        }
        return agent_state, social_context

    async def respond(self, message):
        if not self.ready():
            return None
        text = message.text.strip()
        clean_text = norm_ar(text)
        is_human = (message.user_id not in self.identities)
        human_name = (message.sender_name or self.memory.get_social_profile(message.user_id).get('display_name') or '').strip()

        # 1. Human participation in Active Riddle (ONLY if not rude and not complaining)
        is_rude = any(norm_ar(w) in clean_text for w in RUDE_TERMS)
        is_complaining = any(norm_ar(w) in clean_text for w in IGNORED_TERMS)

        if is_human and self.current_riddle and not self.current_riddle['solved'] and not is_rude and not is_complaining:
            cr = self.current_riddle
            raw_ans = cr['answer']
            norm_ans = cr['norm_ans']
            ans_no_al = norm_ans.removeprefix('ا')
            is_correct = (norm_ans in clean_text) or (len(ans_no_al) >= 3 and ans_no_al in clean_text)
            host = cr['host']
            disp_name = human_name or 'يا بطل'

            # A) Correct answer by human player
            if is_correct:
                cr['solved'] = True
                self.current_riddle = None
                self.last_riddle_end = time.monotonic()
                praise_bot = self.choose(exclude_ids=[host['id']])
                if praise_bot:
                    self.turn_queue.append(Reply(praise_bot['id'], f'ما شاء الله عليك يا {disp_name} جبتها وحنا من الصبح نحوس 😂👏', 'riddle_praise'))
                return Reply(host['id'], f'كفووووو يا {disp_name}! جبتها صح وربي 🔥👏 الجواب هو {raw_ans}', 'riddle_solve_human')

            # B) Human greeted or asked what's going on during a riddle
            if any(w in clean_text for w in ('سلام', 'صباح', 'مساء', 'هلا', 'وش تسوون', 'وش السالفه', 'وش فيه', 'علموني', 'ايش تسوون')):
                helper = self.choose(exclude_ids=[host['id']]) or host
                q = cr['riddle']['question']
                greet_prefix = f'وعليكم السلام يا هلا والله {human_name}! ' if 'سلام' in clean_text and human_name else (f'يا هلا والله {human_name}! ' if human_name else 'وعليكم السلام يا هلا والله! ')
                return Reply(helper['id'], f'{greet_prefix}نورت المجلس 🌸 تعال ساعدنا قاعدين نحل هاللغز: ({q})، وش تتوقع؟ 🤔', 'riddle_invite')

            # C) Short direct riddle guess (1-3 words, not a personal question)
            word_count = len(clean_text.split())
            if 1 <= word_count <= 3 and len(text) <= 25 and not any(term in text for term in ('اسمك', 'بنت', 'ولد', 'بوت', 'عمرك', 'وين', 'ليش', 'كيف')):
                return Reply(host['id'], f'مالك لواء يا {disp_name} 😂 قربت بس مو هي، فكر فيها شوي!', 'riddle_wrong_guess')

        # 2. General Queries & Identity
        profile = self.choose(message.text, message.user_id)
        if not profile:
            return None

        def local(value):
            self.memory.set_agent_state(profile['id'], last_reply=value, last_target_uid=message.user_id, last_target_name=human_name)
            return Reply(profile['id'], value, 'local', messages=(value,))

        if any(term in text for term in ('وش اسمك', 'وش اساميكم', 'وش اسماؤكم', 'وش اسمائكم', 'مين انتم', 'مين انتو', 'من انتم', 'من انتو', 'وش اسمك الحقيقي', 'وش اساميكم الحقيقية', 'اسمك ايش', 'اسمك ايه')):
            my_handle = profile['id']
            age = profile.get('age', 23)
            return local(f'حسابي {my_handle} وعمري {age} سنة 🌸')
        if any(term in text for term in ('ذكر ولا انثى', 'ذكر ولا أنثى', 'انثى ولا ذكر', 'أنثى ولا ذكر', 'بنت ولا ولد', 'ولد ولا بنت', 'انتي بنت', 'أنتي بنت', 'انت بنت', 'أنت بنت', 'انت ولد', 'أنت ولد', 'انتي ولد', 'أنتي ولد', 'وش جنسك', 'بنت ولا رجال', 'رجال ولا بنت', 'بنت؟', 'ذكر؟', 'انثى؟', 'أنثى؟', 'انتم بنات', 'انتو بنات')):
            return local('أكيد بنت طبعاً! 🌸')
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
        if any(term in text for term in ('تذكرني', 'لعبتي المفضلة', 'لعبتي المفضله')):
            preference = self.memory.preference(message.user_id)
            return local(f'أذكر إنك قلت لعبتك المفضلة {preference}.' if preference else 'ما خبرتك ذكرت لي شي معين من قبل.')
        if any(term in text for term in ('رصيدي', 'كم فوز', 'كم عمري', 'نتيجة', 'نتيجه', 'سعر', 'عملات')):
            return local('ما عندي وصول لمعلومة أكيدة عن هالشي، شيّك من المنصة.')

        # 3. Greeting ('السلام عليكم') -> Try model with 'welcome' mode, fallback to local greeting with user's name
        if text in ('السلام عليكم', 'سلام عليكم', 'السلام عليكم ورحمة الله', 'السلام عليكم ورحمة الله وبركاته'):
            reply = await self.generate_reply(profile, self.memory.preference(message.user_id), 'welcome', trigger_message=message)
            if reply:
                return reply
            if human_name:
                return local(f'وعليكم السلام يا {human_name}، يا هلا والله! كيفك؟ 🌸')
            return local('وعليكم السلام، يا هلا! كيفك؟')

        # 4. Model Response (Gemini) with full Persistent State & Social Context
        return await self.generate_reply(profile, self.memory.preference(message.user_id), 'reply', trigger_message=message)

    async def initiative(self, human_count=0):
        if not self.ready() or self.initiative_revision == self.revision:
            return None
        quiet = self.config.get('initiative_seconds', 25)
        if time.monotonic() - max(self.last_input, self.last_sent) < quiet:
            return None

        allow_empty_riddles = bool(self.config.get('allow_empty_room_riddles'))
        if not human_count and not allow_empty_riddles:
            return None

        self.initiative_revision = self.revision
        now = time.monotonic()

        # Launch Riddle only when allow_empty_room_riddles is enabled (live majlis)
        if allow_empty_riddles and self.riddles and not self.current_riddle and (now - self.last_riddle_end >= 50):
            reply = self.start_riddle()
            if reply:
                return reply

        profile = self.choose()
        if not profile or not self.provider:
            return None
        return await self.generate_reply(profile, None, 'initiative', trigger_message=None)

    async def generate_reply(self, profile, preference, mode, trigger_message: Message | None = None):
        if not self.provider or not self.memory.reserve_call(self.config['daily_model_calls']):
            return None
        before = self.revision
        agent_state, social_context = self._build_social_and_agent_state(profile, trigger_message, mode)
        enriched_profile = {
            **profile,
            'conversation_mode': mode,
            'agent_state': agent_state,
            'social_context': social_context
        }
        try:
            context = self.memory.context(self.room, self.identities)
            answer = await self.provider.generate(enriched_profile, context, preference)
        except Exception:
            return None

        # Discard stale reply if new messages arrived while awaiting the model
        if self.revision != before:
            return None

        text = ''
        messages_tuple = ()
        if isinstance(answer, dict):
            raw_msgs = answer.get('messages')
            if isinstance(raw_msgs, (list, tuple)) and raw_msgs:
                messages_tuple = tuple(str(m).strip() for m in raw_msgs if str(m).strip())
            text = answer.get('text', '') or (' '.join(messages_tuple) if messages_tuple else '')
        elif isinstance(answer, (list, tuple)):
            messages_tuple = tuple(str(m).strip() for m in answer if str(m).strip())
            text = messages_tuple[0] if messages_tuple else ''
        else:
            text = str(answer or '')

        text = text.strip()
        if not text:
            return None

        # Safety check: never let a bot address someone using the bot's own username
        speaker_name = social_context.get('speaker_name', '')
        my_id = profile['id']
        for own in {my_id, profile.get('name', '')}:
            if own:
                pat = re.compile(r'يا\s*' + re.escape(own) + r'\b', re.IGNORECASE)
                if pat.search(text):
                    if speaker_name and speaker_name.lower() != own.lower():
                        text = pat.sub(f'يا {speaker_name}', text)
                    else:
                        text = pat.sub('', text)
                    text = re.sub(r'\s{2,}', ' ', text).strip()

        if not valid_output(text):
            return None
        if not messages_tuple:
            messages_tuple = (text,)

        normalize = lambda v: re.sub(r'[\W_]+', '', v).casefold()
        if any(normalize(row.get('text', '')) == normalize(text) for row in context[-6:]):
            return None

        self.memory.set_agent_state(
            my_id,
            last_reply=text,
            last_target_uid=trigger_message.user_id if trigger_message else '',
            last_target_name=speaker_name
        )
        tokens = getattr(self.provider, 'last_usage', None)
        return Reply(my_id, text, 'initiative' if mode == 'initiative' else 'model', tokens, messages_tuple)


def valid_output(text):
    if not isinstance(text, str) or not 1 <= len(text) <= 280:
        return False
    if not re.search(r'[\u0600-\u06ff]', text):
        return False
    if re.search(r'https?://|www\.|[\w.+-]+@[\w.-]+|(?:\+?966|05)\d{8}|\d{7,}', text):
        return False
    return not any(s in text for s in (
        'أنا روبوت', 'انا روبوت', 'أنا ريبورت', 'انا ريبورت', 'أنا بوت', 'انا بوت',
        'أنا شخصية آلية', 'شخصية آلية', 'ذكاء اصطناعي', 'نموذج لغوي', 'بصفتي نموذج',
        'رقم جوالي', 'حسابي سناب', 'أنا إنسان', 'انا انسان', 'أنا شخص حقيقي', 'رصيدك'
    ))


def load_config(path):
    config = json.loads(Path(path).read_text(encoding='utf-8'))
    if not isinstance(config.get('room'), str) or not re.fullmatch(r'[a-z][a-z0-9_-]{1,31}', config['room']):
        raise ValueError('Invalid room')
    ZoneInfo(config['timezone'])
    profiles = config['profiles']
    if type(config.get('initiative_seconds', 45)) is not int or not 10 <= config.get('initiative_seconds', 45) <= 600:
        raise ValueError('Invalid initiative_seconds')
    if not profiles or len(profiles) > 100 or len({p['id'] for p in profiles}) != len(profiles):
        raise ValueError('Invalid profiles')
    for key, low, high in [('daily_model_calls', 0, 10000), ('cooldown_seconds', 2, 3600), ('reply_delay_seconds', 0, 15), ('idle_seconds', 30, 3600), ('memory_days', 1, 30)]:
        if not isinstance(config[key], int) or not low <= config[key] <= high:
            raise ValueError('Invalid ' + key)
    for p in profiles:
        if p.get('gender', 'unspecified') not in ('male', 'female', 'unspecified'):
            raise ValueError('Invalid profile gender')
        if not re.fullmatch(r'[a-z][a-z0-9_]{1,30}', p['id']) or not p['name'] or not re.fullmatch(r'PLAZR_BOT_[A-Z0-9_]+_SESSION', p['session_env']):
            raise ValueError('Invalid profile')
        a, b = p['hours']
        if not 0 <= a <= 23 or not 1 <= b <= 24:
            raise ValueError('Invalid schedule')
    return config
