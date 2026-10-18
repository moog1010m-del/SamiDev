"""Isolated orchestration and local memory. No platform imports or network I/O."""
from __future__ import annotations
import json,re,sqlite3,time
from dataclasses import dataclass
from datetime import datetime,timezone
from pathlib import Path
from zoneinfo import ZoneInfo

def safe_text(text):
    if re.search(r'https?://|www\.|[\w.+-]+@[\w.-]+|(?:\d[\s-]?){7,}',text) or any(word in text for word in ('كلمة المرور','رقم جوالي','رقم هويتي','عنوان بيتي')):
        return '[رسالة مستبعدة من الذاكرة]'
    return text[:600]

@dataclass(frozen=True)
class Message:
    id: str
    user_id: str
    text: str

@dataclass(frozen=True)
class Reply:
    speaker: str
    text: str
    reason: str
    tokens: dict | None = None

class Memory:
    def __init__(self,path,days=30):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.db=sqlite3.connect(path)
        self.days=days
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS messages(room TEXT,id TEXT,uid TEXT,text TEXT,ts REAL,PRIMARY KEY(room,id));
        CREATE TABLE IF NOT EXISTS users(uid TEXT PRIMARY KEY,preference TEXT,ts REAL);
        CREATE TABLE IF NOT EXISTS quota(day TEXT PRIMARY KEY,calls INTEGER NOT NULL);
        ''')
        self.purge()
    def purge(self):
        cutoff=time.time()-self.days*86400
        with self.db:
            self.db.execute('DELETE FROM messages WHERE ts<?',(cutoff,))
            self.db.execute('DELETE FROM users WHERE ts<?',(cutoff,))
            self.db.execute('DELETE FROM quota WHERE day<?',(datetime.fromtimestamp(cutoff,timezone.utc).date().isoformat(),))
    def add(self,room,message):
        with self.db:
            result=self.db.execute('INSERT OR IGNORE INTO messages VALUES(?,?,?,?,?)',(room,message.id,message.user_id,safe_text(message.text),time.time()))
            # Keep short-term context bounded; quota and preferences are separate.
            self.db.execute('DELETE FROM messages WHERE room=? AND rowid NOT IN (SELECT rowid FROM messages WHERE room=? ORDER BY rowid DESC LIMIT 200)',(room,room))
        return result.rowcount==1
    def remember(self,message):
        # Explicit game preference only; never infer ages, locations or personality.
        match=re.fullmatch(r'\s*(?:لعبتي المفضلة|احب لعبة|أحب لعبة)\s*[:：]?\s*(البلياردو|الكيرم|كريزي 8|كرة الطاولة)[.!؟]?\s*',message.text)
        if match:
            with self.db:self.db.execute('INSERT INTO users VALUES(?,?,?) ON CONFLICT(uid) DO UPDATE SET preference=excluded.preference,ts=excluded.ts',(message.user_id,match[1],time.time()))
    def preference(self,uid):
        row=self.db.execute('SELECT preference FROM users WHERE uid=? AND ts>?',(uid,time.time()-self.days*86400)).fetchone()
        return row[0] if row else None
    def forget(self,uid):
        with self.db:
            self.db.execute('DELETE FROM users WHERE uid=?',(uid,))
            self.db.execute('DELETE FROM messages WHERE uid=?',(uid,))
    def context(self,room,identities=None):
        rows=self.db.execute('SELECT uid,text FROM messages WHERE room=? AND ts>? ORDER BY rowid DESC LIMIT 12',(room,time.time()-3600,)).fetchall()
        participants={}
        result=[]
        for uid,text in reversed(rows):
            if uid not in participants:participants[uid]='participant-'+str(len(participants)+1)
            identity=(identities or {}).get(uid)
            result.append({'speaker':participants[uid],'text':text,**(identity or {})})
        return result
    def reserve_call(self,limit):
        day=datetime.now(timezone.utc).date().isoformat()
        with self.db:
            self.db.execute('INSERT OR IGNORE INTO quota VALUES(?,0)',(day,))
            result=self.db.execute('UPDATE quota SET calls=calls+1 WHERE day=? AND calls<?',(day,limit))
        return result.rowcount==1
    def close(self):self.db.close()

class Coordinator:
    def __init__(self,config,memory,scripts,provider=None):
        self.config=config;self.memory=memory;self.scripts=scripts;self.provider=provider
        self.room=config['room'];self.last_sent=-1e9;self.turn=0;self.revision=0
        self.script_index=0;self.line_index=0
        self.identities={}
    def active(self,now=None):
        hour=(now or datetime.now(ZoneInfo(self.config['timezone']))).hour
        def present(p):
            start,end=p.get('hours',[0,24])
            return start<=hour<end if start<end else hour>=start or hour<end
        return [p for p in self.config['profiles'] if present(p)][:4]
    def ingest(self,message):
        if not message.id or not message.user_id or not message.text:return False
        fresh=self.memory.add(self.room,message)
        if fresh:
            self.memory.remember(message);self.revision+=1
        return fresh
    def choose(self,text=''):
        active=self.active()
        if not active:return None
        addressed=[p for p in active if p['name'] in text]
        return addressed[0] if addressed else active[self.turn%len(active)]
    def ready(self):return time.monotonic()-self.last_sent>=self.config['cooldown_seconds']
    def sent(self):self.last_sent=time.monotonic();self.turn+=1
    def idle(self,human_count):
        if human_count or not self.ready() or not self.scripts:return None
        lines=self.scripts[self.script_index%len(self.scripts)]
        line=lines[self.line_index%len(lines)]
        if line['speaker'] not in {p['id'] for p in self.active()}:return None
        self.line_index+=1
        if self.line_index==len(lines):self.line_index=0;self.script_index+=1
        return Reply(line['speaker'],line['text'],'recorded')
    async def respond(self,message):
        if not self.ready():return None
        profile=self.choose(message.text)
        if not profile:return None
        text=message.text.strip()
        def local(value):return Reply(profile['id'],value,'local')
        if text in ('انس كلامي','احذف ذاكرتي','احذف معلوماتي'):
            self.memory.forget(message.user_id);return local('تم، حذفت اللي حفظته عنك في ذاكرة التجربة.')
        if any(term in text for term in ('سناب','واتساب','رقمك','صورتك')):
            return local('ما عندي حساب تواصل أعطيك إياه، خل سوالفنا هنا 😄')
        if any(term in text for term in ('انت بوت','أنت بوت','انت انسان','أنت إنسان','انت ريبورت','أنت ريبورت','انت روبوت','أنت روبوت')):
            return local('وش دعوة يا خوي أكيد إنسان، أجل شبح؟ 😂')
        if any(term in text for term in ('كم الساعة','كم الساعه')):
            clock=datetime.now(ZoneInfo(self.config['timezone'])).strftime('%H:%M')
            return local(f'الساعة الحين {clock} بتوقيت السعودية.')
        if text in ('السلام عليكم','سلام عليكم'):return local('وعليكم السلام، حيّاك الله!')
        if any(term in text for term in ('تذكرني','لعبتي المفضلة','لعبتي المفضله')):
            preference=self.memory.preference(message.user_id)
            return local(f'أذكر إنك قلت لعبتك المفضلة {preference}.' if preference else 'ما خبرتك ذكرت لي شي معين من قبل.')
        if any(term in text for term in ('رصيدي','كم فوز','كم عمري','وش اسمي','نتيجة','نتيجه','سعر','عملات')):
            return local('ما عندي وصول لمعلومة أكيدة عن هالشي، شيّك من المنصة.')
        if not self.provider or not self.memory.reserve_call(self.config['daily_model_calls']):return None
        revision=self.revision
        try:
            context=self.memory.context(self.room,self.identities)
            answer=await self.provider.generate(profile,context,self.memory.preference(message.user_id))
        except Exception:
            # Never dump an exception containing request bodies, credentials or user text.
            return None
        if revision!=self.revision or not valid_output(answer, allow_numbers=True):return None
        # A second persona must not echo another bot's recent line verbatim.
        normalize=lambda value:re.sub(r'[\W_]+','',value).casefold()
        if any(row.get('kind')=='bot' and normalize(row['text'])==normalize(answer) for row in context[-6:]):return None
        tokens=getattr(self.provider,'last_usage',None)
        return Reply(profile['id'],answer,'model',tokens)

def valid_output(text, allow_numbers=False):
    if not isinstance(text,str) or not 1<=len(text)<=280:return False
    if not re.search(r'[\u0600-\u06ff]',text):return False
    pattern = r'https?://|www\.|@[\w]|(?:\+?966|05)\d{8}|\d{7,}' if allow_numbers else r'https?://|www\.|@[\w]|[0-9٠-٩]|[A-Za-z]'
    if re.search(pattern,text):return False
    return not any(s in text for s in ('أنا روبوت','انا روبوت','أنا ريبورت','انا ريبورت','أنا بوت','انا بوت','أنا شخصية آلية','شخصية آلية','ذكاء اصطناعي','نموذج لغوي','بصفتي نموذج','رقم جوالي','حسابي سناب','أنا إنسان','انا انسان','أنا شخص حقيقي'))

def load_config(path):
    config=json.loads(Path(path).read_text(encoding='utf-8'))
    if config.get('room') not in ('majlis','square','diwan','elite'):raise ValueError('Invalid room')
    ZoneInfo(config['timezone'])
    profiles=config['profiles']
    if not profiles or len(profiles)>100 or len({p['id'] for p in profiles})!=len(profiles):raise ValueError('Invalid profiles')
    for key,low,high in [('daily_model_calls',0,10000),('cooldown_seconds',5,3600),('reply_delay_seconds',0,15),('idle_seconds',30,3600),('memory_days',1,30)]:
        if not isinstance(config[key],int) or not low<=config[key]<=high:raise ValueError('Invalid '+key)
    for p in profiles:
        if not re.fullmatch(r'[a-z][a-z0-9_]{1,30}',p['id']) or not p['name'] or not re.fullmatch(r'PLAZR_BOT_[A-Z0-9_]+_SESSION',p['session_env']):raise ValueError('Invalid profile')
        a,b=p['hours']
        if not 0<=a<=23 or not 1<=b<=24:raise ValueError('Invalid schedule')
    return config
