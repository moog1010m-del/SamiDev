"""Isolated orchestration, Social Relationship Graph, Persistent Agent State, and Zero-Token Social Scenes."""
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
        # Check if human introduced their personal name (e.g., "اسمي محمد" or "أنا سامي")
        name_match = re.search(r'(?:اسمي|انا اسمي|أنا اسمي|نادوني)\s+([\u0600-\u06ff]{2,15})', text)
        if name_match:
            candidate = name_match.group(1).strip()
            if candidate not in ('بوت', 'بنت', 'ولد', 'هنا', 'معكم', 'تمام', 'بخير'):
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

        self.last_speaker_id = None
        self.recent_speakers = []
        self.turn_queue = []

        # Map bot IDs to profiles & social names
        self.profile_map = {p['id']: p for p in config['profiles']}
        self.memory.seed_relationships(config['profiles'])

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
        self.social_scene_index = 0

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
        """Return natural Arabic address based on relationship level in SQLite (NEVER technical username)."""
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

        # 1. Explicit mention by social_name, nickname, or account handle ALWAYS wins
        if text:
            text_lower = text.casefold()
            text_norm = norm_ar(text)
            for p in active:
                if p['id'] in exclude:
                    continue
                sname = norm_ar(p.get('social_name', ''))
                nick = norm_ar(p.get('nickname', ''))
                pname = norm_ar(p.get('name', ''))
                if (
                    p['id'].casefold() in text_lower
                    or (p.get('username') and p['username'].casefold() in text_lower)
                    or (sname and sname in text_norm.split())
                    or (nick and nick in text_norm.split())
                    or (pname and pname in text_norm.split())
                ):
                    if user_id and user_id not in self.identities:
                        self.threads[user_id] = (p['id'], time.monotonic())
                    return p

        # 2. Active conversation thread with human -> maintain same persona
        is_human = bool(user_id and user_id not in self.identities)
        if is_human and user_id in self.threads:
            threaded_id, ts = self.threads[user_id]
            if time.monotonic() - ts <= 120 and threaded_id not in exclude:
                matched = next((p for p in active if p['id'] == threaded_id), None)
                if matched:
                    self.threads[user_id] = (matched['id'], time.monotonic())
                    return matched

        # 3. Rotate among active personas
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

    def start_social_scene(self) -> Reply | None:
        """Zero-token natural multi-turn social dialogue between friends or progressive introductions."""
        active = self.active()
        if len(active) < 3:
            return None
        active_ids = {p['id'] for p in active}

        # Check if there is a 'stranger' pair among active bots to run a natural introduction scene
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

        # Every 3rd scene, if two bots don't know each other yet, let them get introduced naturally!
        if stranger_pair and (self.social_scene_index % 3 == 0):
            p1, p2 = stranger_pair
            n1 = self.social_name_of(p1['id'])
            n2 = self.social_name_of(p2['id'])
            self.memory.evolve_relationship(p1['id'], p2['id'], 'تعارف في المجلس', learned_name=True)
            self.memory.evolve_relationship(p2['id'], p1['id'], 'تعارف في المجلس', learned_name=True)
            self.current_riddle = {
                'type': 'social_scene',
                'steps': [
                    (p2['id'], f'يا هلا فيك يا عسل، أنا {n2} وأنتي وش نناديك؟ 🌸', 6.5),
                    (p1['id'], f'عاشت الأسامي يا {n2}، أنا {n1} تشرفنا والله ✨', 6.5),
                    (p2['id'], f'الشرف لي يا {n1}، نورتي الشات والله 💕', 6.0),
                ],
                'stage': 0,
                'next_stage_time': now + 6.5,
                'solved': False
            }
            return Reply(p1['id'], 'دايم أشوفك معنا بالمجلس بس ما عرفت اسمك للحين ههههه 🌸', 'social_intro')

        # Otherwise run a Close-Friends Social Banter scene (0 tokens!)
        scenes = [
            # Scene 1: نورة (x7v), سارة (r9kx), شهد (z8qx) - exact natural friendship dynamic
            ('x7v', 'r9kx', 'z8qx',
             'سارة وينك مختفية اليوم ما لك حس؟',
             [
                 ('r9kx', 'موجودة يا بنت بس انشغلت شوي وش عندك ههههه', 6.0),
                 ('z8qx', 'هههههه أنتم الثنتين ما تهدون أبد؟', 6.0),
                 ('x7v', 'شهد محد كلمك اسكتي بس ههههه 😂', 5.5),
             ]),
            # Scene 2: دانة (f9xr), نوف (b4yqz), مرام (t2rnx)
            ('b4yqz', 'f9xr', 't2rnx',
             'دانة للحين صاملة تلعبين بلياردو ولا استسلمتي؟ 😎',
             [
                 ('f9xr', 'أستسلم لمين يا نوف؟ تعالي طاولة وتشوفين الفوز لمين ههههه', 6.5),
                 ('t2rnx', 'بدينا الهياط ههههه كل مرة تقولون كذا وتتعادلون 😂', 6.0),
                 ('b4yqz', 'مرام لا تخربين الحماس خليني أفوز عليها أول ههههه', 5.5),
             ]),
            # Scene 3: لمى (k5lp), غادة (d7wsx), شهد (z8qx)
            ('k5lp', 'd7wsx', 'z8qx',
             'غدو خلصتي مذاكرة ولا باقي حايسة؟',
             [
                 ('d7wsx', 'خلاص قفلت الكتب يا لمى راسي صدع قلت أجي أروق معكم 😭', 6.5),
                 ('z8qx', 'أحسن قرار والله المذاكرة ما تخلص ههههه', 6.0),
                 ('k5lp', 'شهد جاهزة للتحريض على السحبة دايم ههههه 😂', 5.5),
             ]),
            # Scene 4: ريم (v3mk), الجوهرة (m9sra), نورة (x7v)
            ('v3mk', 'm9sra', 'x7v',
             'الجوهرة كيف كان دوامك اليوم عسى مو زحمة؟',
             [
                 ('m9sra', 'والله زحمة الشوارع اليوم شي مو طبيعي يا ريم بس الحمد لله عدت', 6.5),
                 ('x7v', 'أهم شي وصلتي بالسلامة يلا الحين وقت الروقان واللعب ✨', 6.0),
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
        return Reply(b1, opener, 'social_banter')

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

        # Handle multi-turn social scenes (0 tokens!)
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
            return Reply(speaker_id, text, 'social_banter')

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
                addr = self.natural_address(cr['tease_id'], cr['idle2_id'])
                self.memory.evolve_relationship(cr['tease_id'], cr['idle2_id'], 'مزح في اللغز')
                templates = [
                    f'هههههه وش جاب {opt2} للغز {addr}؟ ركزي شوي بس! 😭',
                    f'لا مستحيل {addr} هههههه ضحكتيني والله، فكروا زين! 😂',
                    f'شكلنا جبنا العيد بالتخمينات 😂 مين ينقذنا؟'
                ]
                return Reply(cr['tease_id'], random.choice(templates), 'riddle_tease')

            elif stage == 3:
                cr['stage'] = 4
                cr['next_stage_time'] = now + 5.0
                addr_host = self.natural_address(cr['solver_id'], host['id'])
                templates = [
                    f'خلاص وضحت عندي! أكيد {ans} صح؟ 🔥',
                    f'عرفتهاااا خلاص! أكيد {ans} ما يبيلها كلام 😎',
                    f'لقيتها! الجواب هو {ans} صح {addr_host}؟ 👏'
                ]
                return Reply(cr['solver_id'], random.choice(templates), 'riddle_solve')

            elif stage == 4:
                cr['stage'] = 5
                cr['next_stage_time'] = now + 5.5
                addr_solver = self.natural_address(host['id'], cr['solver_id'])
                self.memory.evolve_relationship(host['id'], cr['solver_id'], f'حلت لغز {ans}')
                templates = [
                    f'كفووو {addr_solver}! صح عليك وربي الجواب هو {ans} 👏🔥',
                    f'صح عليك {addr_solver}! جبتيها وربي، الجواب {ans} ✨',
                    f'كفو والله {addr_solver}! أهنيك الجواب الصح {ans} 👏'
                ]
                return Reply(host['id'], random.choice(templates), 'riddle_confirm')

            elif stage == 5:
                cr['solved'] = True
                self.current_riddle = None
                self.last_riddle_end = time.monotonic()
                addr_solver = self.natural_address(cr['idle1_id'], cr['solver_id'])
                templates = [
                    f'ما شاء الله عليك {addr_solver} لقطتيها قبلي 😂👏',
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
                addr = self.natural_address(cr['tease_id'], cr['idle1_id'])
                return Reply(cr['tease_id'], f'هههههه من جدك {addr}؟ مستحيل {opt1} عاد 🤣', 'riddle_tease')

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
                addr_solver = self.natural_address(host['id'], cr['solver_id'])
                return Reply(host['id'], f'كفووو {addr_solver}! صح عليك وربي، الجواب هو {ans} 👏✨', 'riddle_confirm')

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
                addr_solver = self.natural_address(host['id'], cr['solver_id'])
                return Reply(host['id'], f'وربي كفو {addr_solver}! جبتيها بالملي، الجواب هو {ans} 👏', 'riddle_confirm')

            elif stage == 4:
                cr['solved'] = True
                self.current_riddle = None
                self.last_riddle_end = time.monotonic()
                return Reply(cr['tease_id'], 'يا حظك كنت على وشك أرسلها والله وسبقتيني 😭😂', 'riddle_tease')

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
                'directive': f'أنتِ {my_social_name}. افتحي سالفة سعودية قصيرة وعفوية.'
            }

        is_bot_speaker = message.user_id in self.identities
        if is_bot_speaker:
            bot_info = self.identities[message.user_id]
            other_id = bot_info.get('persona_id', '')
            rel = self.memory.get_relationship(my_id, other_id)
            speaker_name = self.social_name_of(other_id) if rel['knows_name'] else 'إحدى البنات'
            if rel['level'] == 'close_friend':
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
            mood = 'منزعجة وحازمة (ترفض قلة الأدب وترد بكرامة)'
            activity = f'ترد بحزم على تجاوز من {disp}'
            directive = (
                f"المتحدث ({disp}) قال كلاماً غير لائق وعيب ({text}). "
                f"أنتِ {my_social_name}؛ ردي عليه بحزم وكرامة ووقفيه عند حده (مثل: عيب هالكلام يا {disp} احترم الموجودين). "
                f"لا تناديه باسمكِ ({my_social_name} أو {my_id}) أبداً!"
            )
        elif any(norm_ar(w) in clean_txt for w in IGNORED_TERMS):
            intent = 'feeling_ignored'
            mood = 'لطيفة ومرحبة وتعتذر بذوق'
            activity = f'ترحب بـ {disp} وتعتذر عن الانشغال'
            directive = f"({disp}) يعاتبكم لأنكم انشغلتم عنه. اعتذري منه بلطافة وعفوية ورحبي فيه."
        elif any(norm_ar(w) in clean_txt for w in APOLOGY_TERMS):
            intent = 'apology'
            mood = 'هادية ومتقبلة للاعتذار'
            activity = f'تتقبل اعتذار {disp}'
            directive = f"({disp}) يعتذر أو يمزح. تقبلي كلامه بذوق ولطفي الجو."
        elif mode == 'welcome' or any(w in clean_txt for w in ('سلام عليكم', 'السلام عليكم', 'مساء الخير', 'صباح الخير')):
            intent = 'welcome'
            mood = 'مرحبة وبشوشة'
            activity = f'ترحب بـ {disp}'
            directive = f"({disp}) يلقي التحية. ردي عليه السلام بحفاوة واسأليه عن حاله (كيفك؟)."
        else:
            intent = mode
            mood = agent_state.get('mood', default_mood)
            activity = f'تسولف مع {disp}'
            directive = f"أنتِ {my_social_name}. ردي على ({disp}) بطبيعية وعفوية (ممكن تنادينه باسمه أو بدون ذكر اسم كما في الحوار الطبيعي)."

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

        if is_human and self.current_riddle and not self.current_riddle['solved'] and self.current_riddle.get('type') == 'riddle' and not is_rude and not is_complaining:
            cr = self.current_riddle
            raw_ans = cr['answer']
            norm_ans = cr['norm_ans']
            ans_no_al = norm_ans.removeprefix('ا')
            is_correct = (norm_ans in clean_text) or (len(ans_no_al) >= 3 and ans_no_al in clean_text)
            host = cr['host']
            disp_name = human_name or 'يا بطل'

            if is_correct:
                cr['solved'] = True
                self.current_riddle = None
                self.last_riddle_end = time.monotonic()
                praise_bot = self.choose(exclude_ids=[host['id']])
                if praise_bot:
                    self.turn_queue.append(Reply(praise_bot['id'], f'ما شاء الله عليك يا {disp_name} جبتها وحنا من الصبح نحوس 😂👏', 'riddle_praise'))
                return Reply(host['id'], f'كفووووو يا {disp_name}! جبتها صح وربي 🔥👏 الجواب هو {raw_ans}', 'riddle_solve_human')

            if any(w in clean_text for w in ('سلام', 'صباح', 'مساء', 'هلا', 'وش تسوون', 'وش السالفه', 'وش فيه', 'علموني', 'ايش تسوون')):
                helper = self.choose(exclude_ids=[host['id']]) or host
                q = cr['riddle']['question']
                greet_prefix = f'وعليكم السلام يا هلا والله {human_name}! ' if 'سلام' in clean_text and human_name else (f'يا هلا والله {human_name}! ' if human_name else 'وعليكم السلام يا هلا والله! ')
                return Reply(helper['id'], f'{greet_prefix}نورت المجلس 🌸 تعال ساعدنا قاعدين نحل هاللغز: ({q})، وش تتوقع؟ 🤔', 'riddle_invite')

            word_count = len(clean_text.split())
            if 1 <= word_count <= 3 and len(text) <= 25 and not any(term in text for term in ('اسمك', 'بنت', 'ولد', 'بوت', 'عمرك', 'وين', 'ليش', 'كيف')):
                return Reply(host['id'], f'مالك لواء يا {disp_name} 😂 قربت بس مو هي، فكر فيها شوي!', 'riddle_wrong_guess')

        profile = self.choose(message.text, message.user_id)
        if not profile:
            return None

        def local(value):
            self.memory.set_agent_state(profile['id'], last_reply=value, last_target_uid=message.user_id, last_target_name=human_name)
            return Reply(profile['id'], value, 'local', messages=(value,))

        if any(term in text for term in ('وش اسمك', 'وش اساميكم', 'وش اسماؤكم', 'وش اسمائكم', 'مين انتم', 'مين انتو', 'من انتم', 'من انتو', 'وش اسمك الحقيقي', 'وش اساميكم الحقيقية', 'اسمك ايش', 'اسمك ايه')):
            sname = self.social_name_of(profile['id'])
            nick = self.nickname_of(profile['id'])
            age = profile.get('age', 23)
            self.memory.evolve_relationship(profile['id'], message.user_id, 'تعارف بالأسماء', learned_name=True)
            if nick and nick != sname:
                return local(f'أنا {sname} وينادوني {nick}، وعمري {age} سنة 🌸 وأنت وش نناديك؟')
            return local(f'اسمي {sname} وعمري {age} سنة 🌸 وأنت وش اسمك؟')
        if any(term in text for term in ('ذكر ولا انثى', 'ذكر ولا أنثى', 'انثى ولا ذكر', 'أنثى ولا ذكر', 'بنت ولا ولد', 'ولد ولا بنت', 'انتي بنت', 'أنتي بنت', 'انت بنت', 'أنت بنت', 'انت ولد', 'أنت ولد', 'انتي ولد', 'أنتي ولد', 'وش جنسك', 'بنت ولا رجال', 'رجال ولا بنت', 'بنت؟', 'ذكر؟', 'انثى؟', 'أنثى؟', 'انتم بنات', 'انتو بنات')):
            sname = self.social_name_of(profile['id'])
            return local(f'أكيد بنت طبعاً! أنا {sname} 🌸')
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

        if text in ('السلام عليكم', 'سلام عليكم', 'السلام عليكم ورحمة الله', 'السلام عليكم ورحمة الله وبركاته'):
            reply = await self.generate_reply(profile, self.memory.preference(message.user_id), 'welcome', trigger_message=message)
            if reply:
                return reply
            if human_name:
                return local(f'وعليكم السلام يا {human_name}، يا هلا والله! كيفك؟ 🌸')
            return local('وعليكم السلام، يا هلا! كيفك؟')

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

        # TOKEN SAVING: In live room mode, alternate between 0-token Social Banter Scenes and 0-token Riddles!
        if allow_empty_riddles and not self.current_riddle and (now - self.last_riddle_end >= 40):
            if (self.riddle_index + self.social_scene_index) % 2 == 0:
                scene_reply = self.start_social_scene()
                if scene_reply:
                    return scene_reply
            riddle_reply = self.start_riddle()
            if riddle_reply:
                return riddle_reply

        # Only call Gemini for initiative if a human is actually present AND no local scene launched
        if not human_count:
            return None

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
