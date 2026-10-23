"""Isolated orchestration, Social Relationship Graph, Persistent Agent State, Life Engine, and Natural Human Typing."""
from __future__ import annotations
import json, random, re, sqlite3, time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo
from life_engine import LifeEngine, PERSONA_LIFE_PROFILES


def safe_text(text):
    if re.search(r'https?://|www\.|[\w.+-]+@[\w.-]+|(?:\d[\s-]?){7,}', text) or any(word in text for word in ('كلمة المرور', 'رقم جوالي', 'رقم هويتي', 'عنوان بيتي')):
        return '[رسالة مستبعدة من الذاكرة]'
    return text[:600]


def normalize_saudi_dialect(s: str) -> str:
    """Expand common Saudi mobile shorthand and typos into clear standard dialect forms."""
    if not isinstance(s, str):
        return ''
    s = re.sub(r'\bشتقربلك\b', 'وش تقرب لك', s)
    s = re.sub(r'\bشتقرب\b', 'وش تقرب', s)
    s = re.sub(r'\bشتصير\b', 'وش تصير', s)
    s = re.sub(r'\bشخبار\b', 'وش اخبار', s)
    s = re.sub(r'\bشعلوم\b', 'وش علوم', s)
    s = re.sub(r'\bشسالف[ةه]\b', 'وش سالفه', s)
    s = re.sub(r'\bا?شفيها\b', 'وش فيها', s)
    s = re.sub(r'\bا?شفيك\b', 'وش فيك', s)
    s = re.sub(r'\bباروم\b', 'بالروم', s)
    s = re.sub(r'بالروم\s+ذا\s+معن[ىي]', 'بالروم ذا معنا', s)
    s = re.sub(r'\bاصتناعي\b', 'اصطناعي', s)
    s = re.sub(r'\bعمكر\b', 'عمرك', s)
    return s


def norm_ar(s):
    if not isinstance(s, str):
        return ''
    s = normalize_saudi_dialect(s)
    s = re.sub(r'[\u064b-\u065f\u0670]', '', s)
    s = re.sub(r'[إأآا]', 'ا', s)
    s = re.sub(r'[ة]', 'ه', s)
    s = re.sub(r'[ى]', 'ي', s)
    s = re.sub(r'[^\w\s]', '', s)
    return s.strip().casefold()


EMOJI_RE = re.compile(
    r'[\U00010000-\U0010ffff\u2600-\u27bf\u2300-\u23ff\u2b50\u2764\ufe0f\u200d]+'
)


def humanize_chat(text: str, turn_index: int = 1, strip_trailing_laugh: bool = True) -> str:
    """Make bot output look like real Saudi mobile typing without distorting words:
    - Strip commas (،), exclamation marks (!), semicolons (؛), trailing periods (.)
    - Remove awkward male/robotic vocatives ('يالطيب', 'بالغالي')
    - Strip meaningless 'ههههه' anywhere in the sentence when strip_trailing_laugh is True
    - Allow at most 1 emoji ONLY once every 5 messages (turn_index % 5 == 0); strip all emojis on the other 4 turns.
    """
    if not text:
        return ''
    s = text.strip()
    # Strip commas, exclamation marks, semicolons
    s = re.sub(r'[،,!！؛;]+', ' ', s)
    # Strip trailing periods or ellipses
    s = re.sub(r'\.{1,}\s*$', '', s)
    s = re.sub(r'\.{2,}', ' ', s)
    # Remove awkward male-style filler vocatives
    s = re.sub(r'\b(يا\s*الطيب|يالطيب|بالغالي|يا\s*الغالي|يالغالي)\b', '', s)

    allow_emoji = (turn_index % 5 == 0)
    emojis = EMOJI_RE.findall(s)
    s_clean = EMOJI_RE.sub('', s)
    if strip_trailing_laugh:
        # Remove meaningless 'هههه+' anywhere in the sentence (start, middle, or end) unless it's the only word
        stripped = re.sub(r'\bه{3,}\b', '', s_clean).strip()
        if stripped:
            s_clean = stripped
    s_clean = re.sub(r'[ \t]{2,}', ' ', s_clean).strip()

    if allow_emoji and emojis:
        first_char = emojis[0][0]
        return f"{s_clean} {first_char}".strip()
    return s_clean


RUDE_TERMS = (
    'سراويل', 'سراويلكم', 'فسخو', 'افسخ', 'فصخو', 'افصخ', 'كل زق', 'كلي زق', 'زق',
    'كلب', 'كلبه', 'حيوان', 'حيوانه', 'غبيه', 'غبي', 'تفو', 'تف عليك', 'تفو عليك',
    'قحبه', 'شرموط', 'منيوك', 'كس امك', 'كسمك', 'تس امك', 'تسمك', 'بقذفك', 'اقذفك',
    'لها ريحه', 'ريحتك', 'وسخ', 'وسخه', 'انقلع', 'انقلعي', 'كلي تبن', 'كل تبن',
    'تافهين', 'سافل', 'قذر', 'يهود', 'ياهود'
)

IGNORED_TERMS = (
    'متجاهلين', 'متجاهليني', 'مطنشين', 'مطنشيني', 'ليش محد يرد', 'محد يرد',
    'ساحبين علي', 'ساحبين علينا', 'ردوا علي', 'ماتردون', 'ما تردون'
)

APOLOGY_TERMS = (
    'اسف', 'آسف', 'اعتذر', 'أعتذر', 'امزح', 'أمزح', 'نمزح', 'حقكم علي', 'حقك علي', 'سامحيني', 'سموحة', 'سوري', 'معليش'
)

INTRO_TERMS = (
    'عرفوني عليكم', 'عرفيني عليك', 'عرفونا عليكم', 'ممكن نتعرف', 'نتعرف عليكم',
    'وش اساميكم', 'وش اسماؤكم', 'وش اسمائكم', 'مين انتم', 'مين انتو', 'من انتم', 'من انتو',
    'وش اسمك', 'اسمك ايش', 'اسمك ايه', 'من معي', 'مين موجود'
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
        self.db = sqlite3.connect(path, timeout=15.0)
        self.db.execute('PRAGMA journal_mode=WAL')
        self.db.execute('PRAGMA synchronous=NORMAL')
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
            social_name TEXT DEFAULT '',
            attitude TEXT,
            last_message TEXT,
            interactions INTEGER DEFAULT 0,
            ts REAL
        );
        CREATE TABLE IF NOT EXISTS relationships(
            observer_id TEXT,
            target_id TEXT,
            level TEXT DEFAULT 'stranger',
            knows_name INTEGER DEFAULT 0,
            interactions INTEGER DEFAULT 0,
            last_topic TEXT DEFAULT '',
            ts REAL,
            PRIMARY KEY(observer_id, target_id)
        );
        ''')
        msg_cols = {row[1] for row in self.db.execute("PRAGMA table_info(messages)").fetchall()}
        if 'sender_name' not in msg_cols:
            with self.db:
                self.db.execute("ALTER TABLE messages ADD COLUMN sender_name TEXT DEFAULT ''")
        sp_cols = {row[1] for row in self.db.execute("PRAGMA table_info(social_profiles)").fetchall()}
        if 'social_name' not in sp_cols:
            with self.db:
                self.db.execute("ALTER TABLE social_profiles ADD COLUMN social_name TEXT DEFAULT ''")
        self.purge()

    def seed_relationships(self, profiles: list[dict]):
        now = time.time()
        with self.db:
            for p in profiles:
                oid = p['id']
                for tid in p.get('close_friends', []):
                    self.db.execute(
                        'INSERT OR IGNORE INTO relationships(observer_id, target_id, level, knows_name, interactions, last_topic, ts) VALUES(?,?,?,?,?,?,?)',
                        (oid, tid, 'close_friend', 1, 8, 'سوالف وميانة يومية', now)
                    )
                for tid in p.get('acquaintances', []):
                    self.db.execute(
                        'INSERT OR IGNORE INTO relationships(observer_id, target_id, level, knows_name, interactions, last_topic, ts) VALUES(?,?,?,?,?,?,?)',
                        (oid, tid, 'acquaintance', 1, 3, 'ألغاز وسوالف في المجلس', now)
                    )

    def get_relationship(self, observer_id: str, target_id: str) -> dict:
        if not observer_id or not target_id or observer_id == target_id:
            return {'level': 'self', 'knows_name': 1, 'interactions': 99, 'last_topic': ''}
        row = self.db.execute(
            'SELECT level, knows_name, interactions, last_topic FROM relationships WHERE observer_id=? AND target_id=?',
            (observer_id, target_id)
        ).fetchone()
        if not row:
            return {'level': 'stranger', 'knows_name': 0, 'interactions': 0, 'last_topic': ''}
        return {
            'level': row[0] or 'stranger',
            'knows_name': int(row[1] or 0),
            'interactions': int(row[2] or 0),
            'last_topic': row[3] or ''
        }

    def evolve_relationship(self, observer_id: str, target_id: str, topic: str = '', learned_name: bool = False):
        if not observer_id or not target_id or observer_id == target_id:
            return
        cur = self.get_relationship(observer_id, target_id)
        count = cur['interactions'] + 1
        knows = 1 if (learned_name or cur['knows_name'] or count >= 2) else 0
        level = cur['level']
        if count >= 6:
            level = 'close_friend'
        elif count >= 2 and level == 'stranger':
            level = 'acquaintance'
        now = time.time()
        with self.db:
            self.db.execute(
                '''INSERT INTO relationships(observer_id, target_id, level, knows_name, interactions, last_topic, ts)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(observer_id, target_id) DO UPDATE SET
                   level=excluded.level,
                   knows_name=excluded.knows_name,
                   interactions=excluded.interactions,
                   last_topic=excluded.last_topic,
                   ts=excluded.ts''',
                (observer_id, target_id, level, knows, count, (topic or cur['last_topic'])[:120], now)
            )

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
        row = self.db.execute('SELECT display_name, social_name, attitude, interactions FROM social_profiles WHERE uid=?', (uid,)).fetchone()
        cur_name = (display_name or (row[0] if row else '') or '').strip()[:64]
        cur_social = (row[1] if row else '') or ''
        name_match = re.search(r'(?:اسمي|انا اسمي|أنا اسمي|نادوني)\s+([\u0600-\u06ff]{2,15})', text)
        if name_match:
            candidate = name_match.group(1).strip()
            if candidate not in ('بوت', 'بنت', 'ولد', 'هنا', 'معكم', 'تمام', 'بخير', 'طيب'):
                cur_social = candidate
        cur_att = attitude or (row[2] if row else 'محترم وطبيعي')
        count = (row[3] if row else 0) + 1
        with self.db:
            self.db.execute(
                '''INSERT INTO social_profiles(uid, display_name, social_name, attitude, last_message, interactions, ts)
                   VALUES(?,?,?,?,?,?,?)
                   ON CONFLICT(uid) DO UPDATE SET
                   display_name=excluded.display_name,
                   social_name=excluded.social_name,
                   attitude=excluded.attitude,
                   last_message=excluded.last_message,
                   interactions=excluded.interactions,
                   ts=excluded.ts''',
                (uid, cur_name, cur_social, cur_att, safe_text(text)[:200], count, now)
            )

    def get_social_profile(self, uid: str) -> dict:
        if not uid:
            return {}
        row = self.db.execute(
            'SELECT display_name, social_name, attitude, last_message, interactions FROM social_profiles WHERE uid=?',
            (uid,)
        ).fetchone()
        pref = self.preference(uid)
        if not row:
            return {'preference': pref} if pref else {}
        return {
            'display_name': row[0] or '',
            'social_name': row[1] or '',
            'attitude': row[2] or 'طبيعي',
            'last_message': row[3] or '',
            'interactions': row[4] or 0,
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
            if identity or (sender_name and sender_name in PERSONA_LIFE_PROFILES):
                pid = (identity or {}).get('persona_id') or (identity or {}).get('name') or sender_name
                pdata = PERSONA_LIFE_PROFILES.get(pid, {})
                sname = pdata.get('social_name') or (identity or {}).get('social_name') or pid
                entry['persona_id'] = pid
                entry['social_name'] = sname
                entry['kind'] = 'bot'
            elif sender_name:
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
        self.last_human_input = -1e9
        self.initiative_revision = None
        self.threads = {}
        self.last_user_id = None
        self.bot_turns = 0

        self.last_speaker_id = None
        self.last_human_reply_bot_id = None
        self.last_human_reply_ts = -1e9
        self.recent_speakers = []
        self.turn_queue = []

        self.profile_map = {p['id']: p for p in config['profiles']}
        self.memory.seed_relationships(config['profiles'])

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
        self.social_scene_index = 0
        self.rude_grudges: dict[tuple[str, str], float] = {}
        self.enable_life_engine = bool(config.get('enable_life_engine', True))
        self.virtual_day = int(config.get('virtual_day', 1))
        self.life = LifeEngine(self.memory.db, room=self.room) if self.enable_life_engine else None

    def social_name_of(self, bot_id: str) -> str:
        p = self.profile_map.get(bot_id)
        if not p:
            return bot_id
        return p.get('social_name') or p.get('name') or bot_id

    def nickname_of(self, bot_id: str) -> str:
        p = self.profile_map.get(bot_id)
        if not p:
            return bot_id
        return p.get('nickname') or self.social_name_of(bot_id)

    def natural_address(self, speaker_id: str, target_id: str, use_ya: bool = True) -> str:
        rel = self.memory.get_relationship(speaker_id, target_id)
        sname = self.social_name_of(target_id)
        nick = self.nickname_of(target_id)
        if rel['knows_name']:
            if rel['level'] == 'close_friend' and random.random() < 0.35:
                chosen = nick
            else:
                chosen = sname
            return f"يا {chosen}" if use_ya else chosen
        return "يا بنت" if use_ya else ""

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
                    if self.last_speaker_id and self.last_speaker_id != bot_pid:
                        self.memory.evolve_relationship(bot_pid, self.last_speaker_id, message.text[:60])
                    self.last_speaker_id = bot_pid
                    self.recent_speakers.append(bot_pid)
                    if len(self.recent_speakers) > 10:
                        self.recent_speakers.pop(0)
            else:
                self.last_human_input = time.monotonic()
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
        is_human = bool(user_id and user_id not in self.identities)

        if text:
            text_lower = text.casefold()
            text_norm = norm_ar(text)
            words = text_norm.split()
            active_thread_bot = None
            if is_human and user_id in self.threads:
                tid, tts = self.threads[user_id]
                if time.monotonic() - tts <= 120:
                    active_thread_bot = tid
            third_person_to_second_markers = (
                'تسبك', 'سبتك', 'قالتلك', 'قالت لك', 'تحشك', 'تمدحك', 'بينكم',
                'عنك', 'اختك', 'صديقتك', 'تغار منك', 'قالت عنك'
            )
            has_third_to_second = any(m in text_norm for m in third_person_to_second_markers)

            # Pass 1: Direct vocative ('يا ريم', 'يا لمى') or explicit handle or sentence-initial name ('ريم ...')
            for p in active:
                if p['id'] in exclude:
                    continue
                sname = norm_ar(p.get('social_name', ''))
                nick = norm_ar(p.get('nickname', ''))
                pname = norm_ar(p.get('name', ''))
                names = [n for n in (sname, nick, pname) if n]
                explicit_ya = any(f"يا {n}" in text_norm for n in names)
                initial_name = bool(words and any(words[0] == n for n in names))
                # If the user has an active thread with another bot and starts with "ريم امس تسبك بينكم شي",
                # "ريم" is a third-person subject while the user is addressing their current interlocutor!
                if initial_name and not explicit_ya and active_thread_bot and active_thread_bot != p['id'] and has_third_to_second:
                    initial_name = False
                is_vocative = explicit_ya or initial_name
                is_handle = p['id'].casefold() in text_lower or bool(p.get('username') and p['username'].casefold() in text_lower)
                if is_vocative or is_handle:
                    if is_human:
                        self.threads[user_id] = (p['id'], time.monotonic())
                    return p

        # Pass 2: Active Human Thread Continuity — keep the user with their current interlocutor (up to 30 minutes)
        # even if they pause for a few minutes between questions (e.g., asking Lama about variables then functions)
        if is_human and user_id in self.threads:
            threaded_id, ts = self.threads[user_id]
            if time.monotonic() - ts <= 1800 and threaded_id not in exclude:
                matched = next((p for p in active if p['id'] == threaded_id), None)
                if matched:
                    self.threads[user_id] = (matched['id'], time.monotonic())
                    return matched

        if text:
            text_norm = norm_ar(text)
            words = text_norm.split()
            # Pass 3: General mention when no active thread exists (unless third-person object)
            for p in active:
                if p['id'] in exclude:
                    continue
                sname = norm_ar(p.get('social_name', ''))
                nick = norm_ar(p.get('nickname', ''))
                pname = norm_ar(p.get('name', ''))
                names = [n for n in (sname, nick, pname) if n]
                if any(
                    n in words and not any(f"{prep} {n}" in text_norm for prep in ('مع', 'عن', 'ان', 'لأن', 'لان', 'لك', 'سالفه'))
                    for n in names
                ):
                    if is_human:
                        self.threads[user_id] = (p['id'], time.monotonic())
                    return p

            # Pass 3.b: Academic/Specialty Topic Match when no active thread exists
            if any(w in text_norm for w in ('فنكشن', 'فانكشن', 'متغيرات', 'برمجه', 'كود', 'بايثون', 'حاسب', 'خوارزميات')):
                cs_bot = next((p for p in active if p['id'] == 'k5lp' and p['id'] not in exclude), None)
                if cs_bot:
                    if is_human:
                        self.threads[user_id] = (cs_bot['id'], time.monotonic())
                    return cs_bot

        # Pass 4: If a new human joins/follows up on what the last HUMAN-conversing bot speaker just said (within 300s),
        # keep the conversation with that bot speaker (never hijack to a background scene/riddle bot!)
        target_recent_bot = self.last_human_reply_bot_id
        target_recent_ts = self.last_human_reply_ts
        if is_human and target_recent_bot and (time.monotonic() - target_recent_ts <= 300) and target_recent_bot not in exclude:
            matched = next((p for p in active if p['id'] == target_recent_bot), None)
            if matched:
                self.threads[user_id] = (matched['id'], time.monotonic())
                return matched

        if not is_human and self.last_speaker_id:
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
        return Reply(line['speaker'], humanize_chat(line['text'], self.turn + 1), 'recorded')

    def start_social_scene(self) -> Reply | None:
        active = self.active()
        if len(active) < 3:
            return None
        active_ids = {p['id'] for p in active}

        stranger_pair = None
        for p1 in active:
            for p2 in active:
                if p1['id'] != p2['id']:
                    rel = self.memory.get_relationship(p1['id'], p2['id'])
                    if not rel['knows_name']:
                        stranger_pair = (p1, p2)
                        break
            if stranger_pair:
                break

        self.social_scene_index += 1
        now = time.monotonic()

        if stranger_pair and (self.social_scene_index % 3 == 0):
            p1, p2 = stranger_pair
            n1 = self.social_name_of(p1['id'])
            n2 = self.social_name_of(p2['id'])
            self.memory.evolve_relationship(p1['id'], p2['id'], 'تعارف في المجلس', learned_name=True)
            self.memory.evolve_relationship(p2['id'], p1['id'], 'تعارف في المجلس', learned_name=True)
            self.current_riddle = {
                'type': 'social_scene',
                'steps': [
                    (p2['id'], f'يا هلا فيك أنا {n2} توني انتبه لوجودك معنا', 6.5),
                    (p1['id'], f'عاشت الأسامي يا {n2} أنا {n1} تشرفنا والله', 6.5),
                    (p2['id'], f'الشرف لي يا {n1} منورة المجلس والله', 6.0),
                ],
                'stage': 0,
                'next_stage_time': now + 6.5,
                'solved': False
            }
            return Reply(p1['id'], humanize_chat('بنات مين الجديدة اللي معنا بالشات ما قد سولفنا من قبل', self.turn + 1), 'social_intro')

        if self.life and (self.social_scene_index % 2 == 0):
            # 1. Check if any active friend has a follow-up question on a known event from a previous day
            for f_prof in active:
                for o_prof in active:
                    if f_prof['id'] != o_prof['id']:
                        fq = self.life.get_followup_question(f_prof['id'], o_prof['id'], self.virtual_day)
                        if fq:
                            ev = self.life.get_event(fq['event_id'])
                            dev_reply = (ev['developing_text'] or ev['resolved_text']) if ev else 'الحمد لله الأمور طيبة الحين'
                            self.current_riddle = {
                                'type': 'social_scene',
                                'steps': [
                                    (o_prof['id'], dev_reply, 6.5),
                                ],
                                'stage': 0,
                                'next_stage_time': now + 6.5,
                                'solved': False
                            }
                            return Reply(f_prof['id'], humanize_chat(fq['question'], self.turn + 1), 'life_followup')

            # 2. Otherwise share a fresh daily life event with two present friends/sisters
            speaker_prof = active[self.social_scene_index % len(active)]
            listeners = [p['id'] for p in active if p['id'] != speaker_prof['id']][:2]
            if listeners:
                ev = self.life.create_daily_event(speaker_prof['id'], virtual_day=self.virtual_day)
                opener = self.life.share_event(ev['event_id'], speaker_prof['id'], listeners, current_day=self.virtual_day)
                l1 = listeners[0]
                sname = self.social_name_of(speaker_prof['id'])
                fam = self.life.get_family_relation(l1, speaker_prof['id'])
                if fam and fam['fact_relation'] == 'sister':
                    react = f'الله يعينك يا أختي {sname} عاد أنتِ أدرى بالوضع'
                elif ev['valence'] == 'positive':
                    react = f'ما شاء الله يا {sname} خبر يفتح النفس والله دوم الروقان'
                else:
                    react = f'يلا بسيطة يا {sname} تعالي نلعب ونغير جو بالمجلس'
                self.current_riddle = {
                    'type': 'social_scene',
                    'steps': [(l1, react, 6.5)],
                    'stage': 0,
                    'next_stage_time': now + 6.5,
                    'solved': False
                }
                return Reply(speaker_prof['id'], humanize_chat(opener, self.turn + 1), 'life_event_share')

        scenes = [
            ('x7v', 'r9kx', 'z8qx',
             'سارة وينك مختفية اليوم ما لك حس؟',
             [
                 ('r9kx', 'موجودة يا بنت بس انشغلت شوي وش عندك', 6.0),
                 ('z8qx', 'أنتم الثنتين ما تهدون أبد؟', 6.0),
                 ('x7v', 'شهد محد كلمك اسكتي بس', 5.5),
             ]),
            ('b4yqz', 'f9xr', 't2rnx',
             'دانة للحين صاملة تلعبين بلياردو ولا استسلمتي؟',
             [
                 ('f9xr', 'أستسلم لمين يا نوف تعالي طاولة وتشوفين الفوز لمين', 6.5),
                 ('t2rnx', 'بدينا الهياط كل مرة تقولون كذا وتتعادلون', 6.0),
                 ('b4yqz', 'مرام لا تخربين الحماس خليني أفوز عليها أول', 5.5),
             ]),
            ('k5lp', 'd7wsx', 'z8qx',
             'غدو خلصتي مذاكرة ولا باقي حايسة؟',
             [
                 ('d7wsx', 'خلاص قفلت الكتب يا لمى راسي صدع قلت أجي أروق معكم', 6.5),
                 ('z8qx', 'أحسن قرار والله المذاكرة ما تخلص', 6.0),
                 ('k5lp', 'شهد جاهزة للتحريض على السحبة دايم', 5.5),
             ]),
            ('v3mk', 'm9sra', 'x7v',
             'الجوهرة كيف كان دوامك اليوم عسى مو زحمة؟',
             [
                 ('m9sra', 'والله زحمة الشوارع اليوم شي مو طبيعي يا ريم بس الحمد لله عدت', 6.5),
                 ('x7v', 'أهم شي وصلتي بالسلامة يلا الحين وقت الروقان واللعب', 6.0),
             ]),
        ]
        valid_scenes = [s for s in scenes if s[0] in active_ids and s[1] in active_ids and s[2] in active_ids]
        if not valid_scenes:
            return None
        b1, b2, b3, opener, steps = valid_scenes[self.social_scene_index % len(valid_scenes)]
        self.memory.evolve_relationship(b1, b2, opener[:50], learned_name=True)
        self.memory.evolve_relationship(b2, b1, opener[:50], learned_name=True)
        self.current_riddle = {
            'type': 'social_scene',
            'steps': steps,
            'stage': 0,
            'next_stage_time': now + 6.5,
            'solved': False
        }
        return Reply(b1, humanize_chat(opener, self.turn + 1), 'social_banter')

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
            'type': 'riddle',
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

        q = humanize_chat(riddle['question'], self.turn + 1)
        self.memory.set_agent_state(host['id'], mood='متحمسة ومصحصحة', activity=f'طرحت لغز في الغرفة: {q[:50]}')
        return Reply(host['id'], f"عندي لكم لغز سريع مين يحله\n{q}", 'riddle_start')

    def riddle_tick(self):
        if not self.current_riddle or self.current_riddle['solved']:
            return None
        # Do NOT tick background bot riddles while a human is actively chatting!
        if time.monotonic() - self.last_human_input < 45:
            return None
        cr = self.current_riddle
        now = time.monotonic()
        if now < cr['next_stage_time'] or not self.ready():
            return None

        t_idx = self.turn + 1

        if cr.get('type') == 'social_scene':
            steps = cr['steps']
            stage = cr['stage']
            if stage >= len(steps):
                cr['solved'] = True
                self.current_riddle = None
                self.last_riddle_end = now
                return None
            speaker_id, text, delay = steps[stage]
            cr['stage'] = stage + 1
            cr['next_stage_time'] = now + delay
            if cr['stage'] >= len(steps):
                cr['solved'] = True
                self.current_riddle = None
                self.last_riddle_end = now
            return Reply(speaker_id, humanize_chat(text, t_idx), 'social_banter')

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
                    f'اممم وش رايكم اتوقع {opt1}؟',
                    f'احس الجواب {opt1} صح ولا غلط',
                    f'اتوقع {opt1} يا بنات',
                    f'شكله {opt1} شرايكم؟'
                ]
                return Reply(cr['idle1_id'], humanize_chat(random.choice(templates), t_idx), 'riddle_guess')

            elif stage == 1:
                cr['stage'] = 2
                cr['next_stage_time'] = now + 7.5
                templates = [
                    f'لا لا اتوقع {opt2} والله أعلم',
                    f'يمكن {opt2} احترت والله',
                    f'احس {opt2} أقرب شي للصح'
                ]
                return Reply(cr['idle2_id'], humanize_chat(random.choice(templates), t_idx), 'riddle_guess')

            elif stage == 2:
                cr['stage'] = 3
                cr['next_stage_time'] = now + 8.0
                addr = self.natural_address(cr['tease_id'], cr['idle2_id'])
                self.memory.evolve_relationship(cr['tease_id'], cr['idle2_id'], 'مزح في اللغز')
                templates = [
                    f'وش جاب {opt2} للغز {addr} ركزي شوي بس',
                    f'لا مستحيل {addr} من جدك فكروا زين',
                    f'شكلنا جبنا العيد بالتخمينات مين ينقذنا'
                ]
                return Reply(cr['tease_id'], humanize_chat(random.choice(templates), t_idx), 'riddle_tease')

            elif stage == 3:
                cr['stage'] = 4
                cr['next_stage_time'] = now + 5.5
                addr_host = self.natural_address(cr['solver_id'], host['id'])
                templates = [
                    f'خلاص وضحت عندي أكيد {ans} صح؟',
                    f'عرفتها خلاص أكيد {ans} ما يبيلها كلام',
                    f'لقيتها الجواب هو {ans} صح {addr_host}؟'
                ]
                return Reply(cr['solver_id'], humanize_chat(random.choice(templates), t_idx), 'riddle_solve')

            elif stage == 4:
                cr['stage'] = 5
                cr['next_stage_time'] = now + 6.0
                addr_solver = self.natural_address(host['id'], cr['solver_id'])
                self.memory.evolve_relationship(host['id'], cr['solver_id'], f'حلت لغز {ans}')
                templates = [
                    f'كفو {addr_solver} صح عليك والله الجواب هو {ans}',
                    f'صح عليك {addr_solver} جبتيها والله الجواب {ans}',
                    f'كفو والله {addr_solver} الجواب الصح {ans} 👏'
                ]
                return Reply(host['id'], humanize_chat(random.choice(templates), t_idx), 'riddle_confirm')

            elif stage == 5:
                cr['solved'] = True
                self.current_riddle = None
                self.last_riddle_end = time.monotonic()
                addr_solver = self.natural_address(cr['idle1_id'], cr['solver_id'])
                templates = [
                    f'ما شاء الله عليك {addr_solver} لقطتيها قبلي',
                    f'كنت بكتبها والله وسبقتيني قهر',
                    f'كفو يا ذيبة تستاهلين الفوز'
                ]
                return Reply(cr['idle1_id'], humanize_chat(random.choice(templates), t_idx), 'riddle_react')

        elif mode == 1:
            if stage == 0:
                cr['stage'] = 1
                cr['next_stage_time'] = now + 8.5
                return Reply(cr['idle1_id'], humanize_chat(f'احس الجواب {opt1} صح ولا تخمين شاطح؟', t_idx), 'riddle_guess')

            elif stage == 1:
                cr['stage'] = 2
                cr['next_stage_time'] = now + 7.5
                addr = self.natural_address(cr['tease_id'], cr['idle1_id'])
                return Reply(cr['tease_id'], humanize_chat(f'من جدك {addr} مستحيل {opt1} عاد', t_idx), 'riddle_tease')

            elif stage == 2:
                cr['stage'] = 3
                cr['next_stage_time'] = now + 9.5
                return Reply(cr['idle2_id'], humanize_chat('يا جماعة وين أذكياء الشات شكلنا ضيعنا الطاسة ساعدونا بالحل', t_idx), 'riddle_call_human')

            elif stage == 3:
                cr['stage'] = 4
                cr['next_stage_time'] = now + 5.5
                return Reply(cr['solver_id'], humanize_chat(f'عرفتها خلاص أكيد {ans} صح؟', t_idx), 'riddle_solve')

            elif stage == 4:
                cr['solved'] = True
                self.current_riddle = None
                self.last_riddle_end = time.monotonic()
                addr_solver = self.natural_address(host['id'], cr['solver_id'])
                return Reply(host['id'], humanize_chat(f'كفو {addr_solver} صح عليك الجواب هو {ans} 👏', t_idx), 'riddle_confirm')

        else:
            if stage == 0:
                cr['stage'] = 1
                cr['next_stage_time'] = now + 8.5
                return Reply(cr['idle1_id'], humanize_chat(f'اتوقع {opt1} يا جماعة', t_idx), 'riddle_guess')

            elif stage == 1:
                cr['stage'] = 2
                cr['next_stage_time'] = now + 7.5
                return Reply(cr['idle2_id'], humanize_chat(f'شكله {opt2} وش رايكم بنات؟', t_idx), 'riddle_guess')

            elif stage == 2:
                cr['stage'] = 3
                cr['next_stage_time'] = now + 5.5
                return Reply(cr['solver_id'], humanize_chat(f'لقيتها خلاص الجواب هو {ans} اكيد', t_idx), 'riddle_solve')

            elif stage == 3:
                cr['stage'] = 4
                cr['next_stage_time'] = now + 6.0
                addr_solver = self.natural_address(host['id'], cr['solver_id'])
                return Reply(host['id'], humanize_chat(f'والله كفو {addr_solver} جبتيها صح الجواب هو {ans}', t_idx), 'riddle_confirm')

            elif stage == 4:
                cr['solved'] = True
                self.current_riddle = None
                self.last_riddle_end = time.monotonic()
                return Reply(cr['tease_id'], humanize_chat('يا حظك كنت على وشك أرسلها والله وسبقتيني', t_idx), 'riddle_tease')

        return None

    def _build_social_and_agent_state(self, profile: dict, message: Message | None, mode: str) -> tuple[dict, dict]:
        my_id = profile['id']
        my_social_name = self.social_name_of(my_id)
        default_mood = profile.get('default_mood', 'رايقة ومبسوطة')
        agent_state = self.memory.get_agent_state(my_id, default_mood)

        bot_uid = next((uid for uid, info in self.identities.items() if info.get('persona_id') == my_id), '')
        my_recent = self.memory.recent_bot_messages(self.room, bot_uid, limit=2)
        if agent_state.get('last_reply') and agent_state['last_reply'] not in my_recent:
            my_recent.append(agent_state['last_reply'])
        agent_state['my_recent_messages'] = my_recent[-2:]

        if not message:
            return agent_state, {
                'speaker_name': '',
                'relationship_label': 'مبادرة عامة لأهل الغرفة',
                'addressee': 'أهل الغرفة',
                'intent': mode,
                'trigger_text': '',
                'speaker_memory': {},
                'directive': f'أنتِ {my_social_name}. افتحي سالفة سعودية قصيرة وعفوية بدون فواصل أو علامات تعجب.'
            }

        is_bot_speaker = message.user_id in self.identities
        other_id = ''
        if is_bot_speaker:
            bot_info = self.identities[message.user_id]
            other_id = bot_info.get('persona_id', '')
            rel = self.memory.get_relationship(my_id, other_id)
            speaker_name = self.social_name_of(other_id) if rel['knows_name'] else 'إحدى البنات'
            fam_rel = self.life.get_family_relation(my_id, other_id) if self.life else None
            if fam_rel and fam_rel['fact_relation'] == 'sister':
                rel_label = f"أختكِ الشقيقة في الغرفة ({speaker_name})"
            elif fam_rel and fam_rel['fact_relation'] == 'cousin':
                rel_label = f"بنت خالتكِ وصديقتكِ في الغرفة ({speaker_name})"
            elif rel['level'] == 'close_friend':
                rel_label = f"صديقتكِ المقربة التي تمونين عليها ({speaker_name})"
            elif rel['knows_name']:
                rel_label = f"معرفة لطيفة في الغرفة ({speaker_name})"
            else:
                rel_label = "بنت في الغرفة لم تتعرفي على اسمها بعد"
            speaker_memory = rel
        else:
            speaker_memory = self.memory.get_social_profile(message.user_id)
            rel = self.memory.get_relationship(my_id, message.user_id)
            self.memory.evolve_relationship(my_id, message.user_id, message.text[:60], learned_name=bool(speaker_memory.get('social_name')))
            speaker_name = (speaker_memory.get('social_name') or message.sender_name or speaker_memory.get('display_name') or '').strip()
            if rel['level'] == 'close_friend':
                rel_label = f"لاعب تعرفينه زين وتمونين عليه ({speaker_name})"
            elif rel['level'] == 'acquaintance':
                rel_label = f"لاعب مألوف في الغرفة ({speaker_name})"
            else:
                rel_label = f"لاعب في الغرفة ({speaker_name or 'زائر'})"

        text = message.text.strip()
        clean_txt = norm_ar(text)

        text_lower = text.casefold()
        if my_id.casefold() in text_lower or norm_ar(my_social_name) in clean_txt.split():
            addressee = f"موجهة لكِ أنتِ بالاسم ({my_social_name})"
        elif not is_bot_speaker and message.user_id in self.threads and self.threads[message.user_id][0] == my_id:
            addressee = f"يكمل حواره المباشر معكِ ({my_social_name})"
        else:
            addressee = "حديث عام في الغرفة"

        disp = speaker_name if speaker_name else 'اللاعب'
        if any(norm_ar(w) in clean_txt for w in RUDE_TERMS):
            intent = 'inappropriate_or_rude'
            if self.life:
                self.life.update_emotion(my_id, -0.8, f'رسالة غير لائقة من {disp}')
            mood = 'منزعجة وحازمة (ترفض قلة الأدب وترد بكرامة)'
            activity = f'ترد بحزم على تجاوز من {disp}'
            directive = (
                f"المتحدث ({disp}) قال كلاماً غير لائق ({text}). "
                f"أنتِ {my_social_name} ردي عليه بحزم وكرامة ووقفيه عند حده باختصار بدون فواصل أو تعجب (مثل: عيب هالكلام يا {disp} احترم الموجودين). "
                f"لا تناديه باسمكِ ({my_social_name} أو {my_id}) أبداً."
            )
        elif any(norm_ar(w) in clean_txt for w in IGNORED_TERMS):
            intent = 'feeling_ignored'
            mood = 'لطيفة ومرحبة وتعتذر بذوق'
            activity = f'ترحب بـ {disp} وتعتذر عن الانشغال'
            directive = f"({disp}) يعاتبكم لأنكم انشغلتم عنه. قولي له إنكم رديتوا عليه أو اعتذري بعفوية بدون فواصل أو تعجب."
        elif any(norm_ar(w) in clean_txt for w in APOLOGY_TERMS):
            intent = 'apology'
            if self.life:
                self.life.update_emotion(my_id, 0.4, f'اعتذار لطيف من {disp}')
            mood = 'هادية ومتقبلة للاعتذار'
            activity = f'تتقبل اعتذار {disp}'
            directive = f"({disp}) يعتذر أو يمزح. تقبلي كلامه بذوق ولطفي الجو بدون فواصل أو تعجب."
        elif mode == 'welcome' or any(w in clean_txt for w in ('سلام عليكم', 'السلام عليكم', 'مساء الخير', 'صباح الخير')):
            intent = 'welcome'
            if self.life:
                self.life.update_emotion(my_id, 0.2, f'تحية من {disp}')
            mood = 'مرحبة وبشوشة'
            activity = f'ترحب بـ {disp}'
            directive = f"({disp}) يلقي التحية. ردي عليه السلام بعفوية واسأليه كيفك بدون فواصل أو علامات تعجب."
        elif any(norm_ar(w) in clean_txt for w in INTRO_TERMS):
            intent = 'introduction'
            mood = agent_state.get('mood', default_mood)
            activity = f'تتفاعل وتعرف باسمها لـ {disp}'
            directive = (
                f"أنتِ {my_social_name}. المتحدث ({disp}) يقول: \"{text}\". "
                f"تفاعلي مع كلامه وموقفه بذكاء وعفوية واذكري اسمكِ الحقيقي ({my_social_name}) بأسلوب طبيعي غير رسمي. "
                f"ممنوع ذكر عمركِ أو سرد تعريف جاهز إلا لو سأل عن العمر صراحة."
            )
        else:
            intent = mode
            mood = (self.life.get_emotion(my_id)['mood_label'] if self.life else agent_state.get('mood', default_mood))
            activity = f'تسولف مع {disp}'
            directive = f"أنتِ {my_social_name}. ردي على ({disp}) بطبيعية وعفوية بدون فواصل وبدون علامات تعجب وبدون إيموجي."

        if self.life:
            ep = self.life.check_epistemic_event_query(my_id, text)
            if ep:
                if not ep['knows']:
                    directive += f" تنبيه معرفي: {ep['text']} (ممنوع ادعاء معرفة هذه السالفة)."
                else:
                    directive += f" السالفة في ذاكرتكِ ({ep['status']}): {ep['text']}"

        self.memory.set_agent_state(my_id, mood=mood, activity=activity, last_target_uid=message.user_id, last_target_name=speaker_name)
        agent_state['mood'] = mood
        agent_state['activity'] = activity

        social_context = {
            'speaker_name': speaker_name,
            'speaker_role': rel_label,
            'relationship_label': rel_label,
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
        sp = self.memory.get_social_profile(message.user_id)
        human_name = (sp.get('social_name') or message.sender_name or sp.get('display_name') or '').strip()

        is_rude = any(norm_ar(w) in clean_text for w in RUDE_TERMS)
        is_complaining = any(norm_ar(w) in clean_text for w in IGNORED_TERMS)
        is_intro = any(norm_ar(w) in clean_text for w in INTRO_TERMS)

        # 1. Human participation in Active Riddle — ONLY if human actually solved it or explicitly guessed one of the wrong options!
        if is_human and self.current_riddle and not self.current_riddle['solved']:
            if self.current_riddle.get('type') == 'riddle' and not is_rude and not is_complaining and not is_intro:
                cr = self.current_riddle
                raw_ans = cr['answer']
                norm_ans = cr['norm_ans']
                ans_no_al = norm_ans.removeprefix('ا')
                is_correct = (norm_ans in clean_text) or (len(ans_no_al) >= 3 and ans_no_al in clean_text)
                host = cr['host']
                disp_name = human_name or 'بطل'

                # A) Correct answer by human player
                if is_correct:
                    cr['solved'] = True
                    self.current_riddle = None
                    self.last_riddle_end = time.monotonic()
                    praise_bot = self.choose(exclude_ids=[host['id']])
                    if praise_bot:
                        self.turn_queue.append(Reply(praise_bot['id'], humanize_chat(f'ما شاء الله عليك يا {disp_name} جبتها صح وحنا نحوس', self.turn + 2), 'riddle_praise'))
                    return Reply(host['id'], humanize_chat(f'كفو والله يا {disp_name} جبتها صح الجواب هو {raw_ans}', self.turn + 1), 'riddle_solve_human')

                # B) Explicit wrong guess (ONLY if matching one of wrong_options or starting with الجواب/اتوقع or pure number when answer is number)
                explicit_guess = (
                    any(norm_ar(opt) == clean_text or (len(norm_ar(opt)) >= 3 and norm_ar(opt) in clean_text) for opt in cr.get('wrong_options', []))
                    or any(clean_text.startswith(prefix) for prefix in ('الجواب ', 'اتوقع ', 'الحل '))
                    or (clean_text.isdigit() and norm_ans.isdigit())
                )
                if explicit_guess:
                    return Reply(host['id'], humanize_chat(f'لا مو هي يا {disp_name} قربت فكر فيها شوي', self.turn + 1), 'riddle_wrong_guess')

            # For ANY other human message (greeting, 'عرفوني عليكم', normal chat), STOP the background riddle immediately so bots focus 100% on the human!
            self.current_riddle = None
            self.last_riddle_end = time.monotonic()

        # 2. General Queries, Introductions & Identity
        profile = self.choose(message.text, message.user_id)
        if not profile:
            return None

        is_humorous_msg = any(w in text for w in ('هههه', 'تخيل', 'مقلب', 'نكتة', 'نكته', 'ضحك', '😂', '🤣'))

        def local(value, strip_laugh=None):
            do_strip = (not is_humorous_msg) if strip_laugh is None else strip_laugh
            cleaned = humanize_chat(value, self.turn + 1, strip_trailing_laugh=do_strip)
            self.memory.set_agent_state(profile['id'], last_reply=cleaned, last_target_uid=message.user_id, last_target_name=human_name)
            if is_human:
                self.threads[message.user_id] = (profile['id'], time.monotonic())
                self.last_human_reply_bot_id = profile['id']
                self.last_human_reply_ts = time.monotonic()
            return Reply(profile['id'], cleaned, 'local', messages=(cleaned,))

        # 2.a Emotional & Dignity Continuity: if this human recently insulted this bot and hasn't apologized,
        # refuse to answer personal/normal questions until they apologize!
        is_apology = any(norm_ar(w) in clean_text for w in APOLOGY_TERMS)
        if is_human and is_rude:
            self.rude_grudges[(profile['id'], message.user_id)] = time.monotonic()
        elif is_human and is_apology:
            had_grudge = self.rude_grudges.pop((profile['id'], message.user_id), None)
            if had_grudge is not None:
                if self.life:
                    self.life.update_emotion(profile['id'], 0.4, f'اعتذار من {human_name or "اللاعب"}')
                return local('حصل خير بس لا عاد تعيدها')
        elif is_human:
            grudge_ts = self.rude_grudges.get((profile['id'], message.user_id), 0.0)
            if grudge_ts > 0 and (time.monotonic() - grudge_ts) <= 300:
                grudge_replies = (
                    'تغلط علي وتبيني أرد عليك عدل أسلوبك واعتذر أول',
                    'ما راح أجاوبك وأنت تسب احترم نفسك أول',
                    'ما لي كلام معك بعد أسلوبك ذا لين تعتذر وتحترم نفسك',
                )
                return local(grudge_replies[self.turn % len(grudge_replies)])

        if is_intro:
            sname = self.social_name_of(profile['id'])
            self.memory.evolve_relationship(profile['id'], message.user_id, 'تعارف بالأسماء', learned_name=True)
            # If asking plural ("عرفوني عليكم" / "مين انتم"), have a second friend also chime in naturally
            if any(w in clean_text for w in ('عرفوني', 'عرفونا', 'انتم', 'انتو', 'اساميكم', 'اسماؤكم', 'اسمائكم', 'موجود')):
                second_bot = self.choose(exclude_ids=[profile['id']])
                if second_bot:
                    s2 = self.social_name_of(second_bot['id'])
                    self.memory.evolve_relationship(second_bot['id'], message.user_id, 'تعارف بالأسماء', learned_name=True)
                    welcome_tail = f'يا {human_name}' if human_name else 'معنا'
                    self.turn_queue.append(Reply(second_bot['id'], humanize_chat(f'وأنا {s2} حياك الله {welcome_tail} منور المجلس', self.turn + 2), 'intro_followup'))
            # Let Gemini respond contextually to the exact situation first!
            model_reply = await self.generate_reply(profile, self.memory.preference(message.user_id), 'reply', trigger_message=message)
            if model_reply:
                return model_reply
            return local(f'أنا {sname} ومعنا البنات سارة ونورة ودانة حياك الله بيننا' if any(w in clean_text for w in ('عرفوني', 'عرفونا', 'انتم', 'انتو')) else f'أنا {sname} يا هلا فيك')

        if any(term in text for term in ('ذكر ولا انثى', 'ذكر ولا أنثى', 'انثى ولا ذكر', 'أنثى ولا ذكر', 'بنت ولا ولد', 'ولد ولا بنت', 'انتي بنت', 'أنتي بنت', 'انت بنت', 'أنت بنت', 'انت ولد', 'أنت ولد', 'انتي ولد', 'أنتي ولد', 'وش جنسك', 'بنت ولا رجال', 'رجال ولا بنت', 'بنت؟', 'ذكر؟', 'انثى؟', 'أنثى؟', 'انتم بنات', 'انتو بنات')):
            sname = self.social_name_of(profile['id'])
            return local(f'أكيد بنت أنا {sname}')
        if any(term in text for term in ('انت بوت', 'أنت بوت', 'انتي بوت', 'أنتي بوت', 'انت انسان', 'أنت إنسان', 'انتي انسانة', 'أنتي إنسانة', 'انت ريبورت', 'أنت ريبورت', 'انت روبوت', 'أنت روبوت', 'ذكاء اصطناعي')):
            return local('وش دعوة أكيد بنت حقيقية أجل شبح؟')
        if any(term in text for term in ('سناب', 'واتساب', 'رقمك', 'صورتك')):
            return local('ما عندي حساب تواصل أعطيك إياه خل سوالفنا هنا')
        if any(term in text for term in ('كم الساعة', 'كم الساعه')):
            clock = datetime.now(ZoneInfo(self.config['timezone'])).strftime('%H:%M')
            return local(f'الساعة الحين {clock} بتوقيت السعودية')
        if text in ('انس كلامي', 'احذف ذاكرتي', 'احذف معلوماتي'):
            self.memory.forget(message.user_id)
            return local('تم حذفت اللي حفظته عنك في ذاكرة التجربة')
        if any(term in text for term in ('تذكرني', 'لعبتي المفضلة', 'لعبتي المفضله')):
            preference = self.memory.preference(message.user_id)
            return local(f'أذكر إنك قلت لعبتك المفضلة {preference}' if preference else 'ما خبرتك ذكرت لي شي معين من قبل')
        if any(term in clean_text for term in ('كم عمرك', 'عمرك كم', 'وش عمرك')):
            age = self.life.get_identity(profile['id'])['age'] if self.life else profile.get('age', 23)
            sname = self.social_name_of(profile['id'])
            return local(f'أنا {sname} وعمري {age} سنة')
        if any(term in clean_text for term in ('وش حسابك', 'وش يوزرك', 'اي حساب انتي', 'تعرفين حسابك')):
            sname = self.social_name_of(profile['id'])
            return local(f'أنا {sname} وحسابي هنا بالروم هو {profile["id"]}')
        if any(term in text for term in ('رصيدي', 'كم فوز', 'كم عمري', 'نتيجة', 'نتيجه', 'سعر', 'عملات')):
            return local('ما عندي وصول لمعلومة أكيدة عن هالشي شيك من المنصة')

        if self.life:
            off_room = self.life.check_off_room_presence_query(profile['id'], text)
            if off_room:
                return local(off_room)
            if any(w in clean_text for w in ('مين اختك', 'من اختك', 'مين اخوك', 'من اخوك', 'اسم امك', 'وش اسم امك', 'عايلتك', 'عائلتك', 'ريم اختك', 'نوره اختك', 'وش تقرب لك', 'وش تصير لك', 'تقرب لك')):
                return local(self.life.resolve_family_fact(profile['id'], text))
            recent_rows = self.memory.context(self.room, self.identities)[-4:]
            recent_ctx_str = ' '.join(r.get('text', '') for r in recent_rows[:-1]) if len(recent_rows) > 1 else ''
            ep = self.life.check_epistemic_event_query(profile['id'], text, recent_context_text=recent_ctx_str)
            if ep:
                if not ep['knows']:
                    return local(ep['text'])
                if (
                    ep['status'] in ('Resolved', 'Archived')
                    or ep['subject_id'] != profile['id']
                    or any(w in clean_text for w in ('وش اخبار محمد', 'اخبار محمد', 'سالفته', 'سالفتها', 'قالت لك شي', 'متكدره', 'متضايقه'))
                ):
                    return local(ep['text'])

        if text in ('السلام عليكم', 'سلام عليكم', 'السلام عليكم ورحمة الله', 'السلام عليكم ورحمة الله وبركاته'):
            reply = await self.generate_reply(profile, self.memory.preference(message.user_id), 'welcome', trigger_message=message)
            if reply:
                return reply
            if human_name:
                return local(f'وعليكم السلام يا {human_name} يا هلا والله كيفك؟')
            return local('وعليكم السلام يا هلا كيفك؟')

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

        # Do not launch background bot riddles/scenes if a human was talking in the last 600s (10 minutes)
        if allow_empty_riddles and (time.monotonic() - self.last_human_input < 600):
            return None

        self.initiative_revision = self.revision
        now = time.monotonic()

        if allow_empty_riddles:
            if not self.current_riddle and (now - self.last_riddle_end >= 30):
                if (self.riddle_index + self.social_scene_index) % 2 == 0:
                    scene_reply = self.start_social_scene()
                    if scene_reply:
                        return scene_reply
                riddle_reply = self.start_riddle()
                if riddle_reply:
                    return riddle_reply
            return None

        if not human_count:
            return None

        profile = self.choose()
        if not profile or not self.provider:
            return None
        return await self.generate_reply(profile, None, 'initiative', trigger_message=None)

    async def generate_reply(self, profile, preference, mode, trigger_message: Message | None = None):
        if not self.provider or not self.memory.reserve_call(self.config['daily_model_calls']):
            return None
        if self.life and not self.life.budget.can_make_call(self.room, priority='optional_initiative' if mode == 'initiative' else 'human_reply'):
            return None
        before = self.revision
        agent_state, social_context = self._build_social_and_agent_state(profile, trigger_message, mode)
        enriched_profile = {
            **profile,
            'conversation_mode': mode,
            'agent_state': agent_state,
            'social_context': social_context
        }
        context = self.memory.context(self.room, self.identities)
        if self.life:
            other_bot_id = ''
            if trigger_message and trigger_message.user_id in self.identities:
                other_bot_id = self.identities[trigger_message.user_id].get('persona_id', '')
            recent_ctx_str = ' '.join(r.get('text', '') for r in context[-4:-1]) if len(context) > 1 else ''
            enriched_profile['life_slice'] = self.life.build_economic_memory_slice(
                profile['id'],
                other_bot_id,
                trigger_message.text if trigger_message else '',
                recent_context_text=recent_ctx_str
            )
        try:
            answer = await self.provider.generate(enriched_profile, context, preference)
        except Exception:
            return None

        if self.revision != before:
            return None

        trig_txt = trigger_message.text if trigger_message else ''
        is_humorous_trigger = any(w in trig_txt for w in ('هههه', 'تخيل', 'مقلب', 'نكتة', 'نكته', 'ضحك', '😂', '🤣'))
        strip_laugh = not is_humorous_trigger

        text = ''
        messages_tuple = ()
        if isinstance(answer, dict):
            raw_msgs = answer.get('messages')
            if isinstance(raw_msgs, (list, tuple)) and raw_msgs:
                messages_tuple = tuple(humanize_chat(str(m).strip(), self.turn + 1, strip_trailing_laugh=strip_laugh) for m in raw_msgs if str(m).strip())
            text = answer.get('text', '') or (' '.join(messages_tuple) if messages_tuple else '')
        elif isinstance(answer, (list, tuple)):
            messages_tuple = tuple(humanize_chat(str(m).strip(), self.turn + 1, strip_trailing_laugh=strip_laugh) for m in answer if str(m).strip())
            text = messages_tuple[0] if messages_tuple else ''
        else:
            text = str(answer or '')

        text = humanize_chat(text, self.turn + 1, strip_trailing_laugh=strip_laugh)
        if not text:
            return None

        speaker_name = social_context.get('speaker_name', '')
        my_id = profile['id']
        my_sname = self.social_name_of(my_id)
        for own in {my_id, profile.get('name', ''), my_sname}:
            if own:
                pat = re.compile(r'يا\s*@?' + re.escape(own) + r'\b', re.IGNORECASE)
                if pat.search(text):
                    if speaker_name and speaker_name.lower() != own.lower():
                        text = pat.sub(f'يا {speaker_name}', text)
                    else:
                        text = pat.sub('', text)
                    text = re.sub(r'\s{2,}', ' ', text).strip()

        # Prevent identity confusion: never claim another bot's social name ("أنا شهد" when my_sname is "ريم")
        for pid, pdata in PERSONA_LIFE_PROFILES.items():
            other_sname = pdata['social_name']
            if my_sname and other_sname != my_sname:
                text = re.sub(r'\b(أنا|انا|اسمي|أسمي)\s+' + re.escape(other_sname) + r'\b', rf'\1 {my_sname}', text)

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
        if trigger_message and trigger_message.user_id not in self.identities:
            self.threads[trigger_message.user_id] = (my_id, time.monotonic())
            self.last_human_reply_bot_id = my_id
            self.last_human_reply_ts = time.monotonic()
        tokens = getattr(self.provider, 'last_usage', None)
        if self.life and isinstance(tokens, dict) and tokens.get('totalTokenCount'):
            self.life.budget.record_gemini_usage(
                self.room,
                getattr(self.provider, 'model', 'gemini'),
                tokens.get('promptTokenCount', 0),
                tokens.get('candidatesTokenCount', 0),
                tokens.get('totalTokenCount', 0)
            )
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
