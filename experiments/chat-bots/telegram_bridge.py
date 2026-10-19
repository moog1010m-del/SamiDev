"""Telegram Live Bridge: Listens to public Telegram groups, sanitizes messages,
and feeds authentic background dialogue into SamiDev platform community rooms.
"""
import asyncio, json, os, re, sys, time, random
from pathlib import Path
import aiohttp
from telethon import TelegramClient, events
from telethon.tl.functions.channels import JoinChannelRequest

SECRETS_DIR = Path(r"C:\Users\Dev\.samidev\secrets")
CONFIG_PATH = SECRETS_DIR / "telegram.json"
SESSION_PATH = str(SECRETS_DIR / "telegram_listener")
STORAGE_DIR = Path(r"C:\Users\Dev\.samidev\storage")
FEED_CACHE = STORAGE_DIR / "telegram_live_feed.json"
SCRIPTS_PATH = Path(r"C:\Users\Dev\Desktop\مجلد جديد (10)\SamiDev_V36\experiments\chat-bots\scripts.json")

# Strict safety and cleanliness filter patterns
RE_URL = re.compile(r"https?://|www\.|t\.me/|[a-zA-Z0-9-]+\.(?:com|net|org|sa|xyz|me|io|info|app)", re.I)
RE_PHONE = re.compile(r"(?:\+?966|05)\d{8}|\d{7,}")
RE_HANDLE = re.compile(r"@[a-zA-Z0-9_]{3,}|(?:سناب|انستا|تيك|تويتر|يوتيوب|واتس)\s*[:：]?\s*[a-zA-Z0-9_.]+", re.I)
RE_ADS = re.compile(r"اشتراك|متجر|عرض خاص|خصم|ريال|كود خصم|شحن|للبيع|حسابات|تواصل خاص|خاص تعال|متابعين|رشق|فلورز", re.I)
RE_BOT_ADMIT = re.compile(r"روبوت|ذكاء اصطناعي|نموذج|تيلجرام|بوت|قناة|قروب", re.I)
RE_GAMES = re.compile(r"كيرم|بلياردو|بلوت|كريزي|قيم|نلعب|العب معي|ادخل قيم|تعال قيم", re.I)
RE_REPEAT = re.compile(r"(.)\1{4,}")

def sanitize_message(text: str) -> str | None:
    if not text or not isinstance(text, str):
        return None
    text = text.strip()
    if not (6 <= len(text) <= 140):
        return None
    # Must have Arabic text
    if not re.search(r"[\u0600-\u06ff]", text):
        return None
    # Must not contain URLs, phone numbers, handles, ads, games, or bot mentions
    if (RE_URL.search(text) or RE_PHONE.search(text) or RE_HANDLE.search(text)
            or RE_ADS.search(text) or RE_BOT_ADMIT.search(text) or RE_GAMES.search(text)):
        return None
    if text.startswith("/") or text.startswith("."):
        return None
    # Squash excessive repeated characters (e.g. ههههههههههههههههه -> ههههه)
    text = RE_REPEAT.sub(r"\1\1\1", text)
    return text.strip()

class TelegramLiveBridge:
    def __init__(self, api_id, api_hash, target_group="iSSSK", base_url="http://127.0.0.1:56648", room="majlis"):
        self.api_id = int(api_id)
        self.api_hash = api_hash
        self.target_group = target_group
        self.base_url = base_url.rstrip("/")
        self.room = room
        self.client = None
        self.bot_sessions = []
        self.history_cache = []
        self.pending_queue = asyncio.Queue()
        self.bot_index = 0

    def load_bot_sessions(self):
        sessions_file = SECRETS_DIR / "bot_sessions.json"
        if sessions_file.exists():
            try:
                data = json.loads(sessions_file.read_text(encoding="utf-8"))
                self.bot_sessions = [v for k, v in data.items() if v]
            except Exception:
                pass

    def save_cache(self, item):
        try:
            STORAGE_DIR.mkdir(parents=True, exist_ok=True)
            self.history_cache.append(item)
            if len(self.history_cache) > 200:
                self.history_cache.pop(0)
            FEED_CACHE.write_text(json.dumps(self.history_cache, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:
            pass

    async def post_to_room(self, text, sender_name):
        if not self.bot_sessions:
            self.load_bot_sessions()
        if not self.bot_sessions:
            return False

        token = self.bot_sessions[self.bot_index % len(self.bot_sessions)]
        self.bot_index += 1

        url = f"{self.base_url}/api/communities/{self.room}/chat"
        async with aiohttp.ClientSession(cookies={"samidev_session": token}, headers={"Origin": self.base_url}) as s:
            try:
                async with s.post(url, json={"text": text}, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        print(json.dumps({"event": "ambient_sent", "room": self.room, "text": text}, ensure_ascii=False), flush=True)
                        return True
            except Exception:
                pass
        return False

    async def ambient_speaker_loop(self):
        """Naturally paces and speaks messages from the live queue."""
        while True:
            try:
                # Natural gap between ambient background messages (12 to 24 seconds)
                delay = random.uniform(12.0, 24.0)
                await asyncio.sleep(delay)
                
                if not self.pending_queue.empty():
                    item = await self.pending_queue.get()
                    await self.post_to_room(item["text"], item["sender"])
            except asyncio.CancelledError:
                break
            except Exception as e:
                await asyncio.sleep(5)

    async def start(self):
        self.load_bot_sessions()
        self.client = TelegramClient(SESSION_PATH, self.api_id, self.api_hash)
        await self.client.connect()

        if not await self.client.is_user_authorized():
            print("ERROR: الجلسة غير مفعلة. شغّل telegram_auth.py أولاً.", flush=True)
            return

        target_entity = await self.client.get_entity(self.target_group)
        try:
            await self.client(JoinChannelRequest(target_entity))
        except Exception:
            pass

        title = getattr(target_entity, 'title', self.target_group) or self.target_group
        print(json.dumps({"event": "bridge_connected", "target": self.target_group, "title": title}, ensure_ascii=False), flush=True)

        # Seed with initial recent clean messages from the group
        try:
            recent_messages = await self.client.get_messages(target_entity, limit=40)
            seeded = 0
            for msg in reversed(recent_messages):
                raw_text = msg.text or ""
                clean = sanitize_message(raw_text)
                if clean:
                    sender = await msg.get_sender()
                    sname = getattr(sender, "first_name", "مشارك") or "مشارك"
                    payload = {"text": clean, "sender": sname, "ts": int(time.time() * 1000)}
                    self.save_cache(payload)
                    await self.pending_queue.put(payload)
                    seeded += 1
            print(json.dumps({"event": "seed_messages_loaded", "count": seeded}, ensure_ascii=False), flush=True)
        except Exception as e:
            print(json.dumps({"event": "seed_error", "error": str(e)}, ensure_ascii=False), flush=True)

        # Start the background ambient speaker
        speaker_task = asyncio.create_task(self.ambient_speaker_loop())

        # Listen in real time for incoming live messages
        @self.client.on(events.NewMessage(chats=target_entity))
        async def on_new_message(event):
            raw_text = event.message.message or ""
            clean = sanitize_message(raw_text)
            if not clean:
                return

            sender = await event.get_sender()
            sender_name = getattr(sender, "first_name", "مشارك") or "مشارك"

            payload = {
                "text": clean,
                "sender": sender_name,
                "ts": int(time.time() * 1000)
            }
            self.save_cache(payload)
            await self.pending_queue.put(payload)
            print(json.dumps({"event": "live_message_received", "sender": sender_name, "text": clean[:60]}, ensure_ascii=False), flush=True)

        try:
            await self.client.run_until_disconnected()
        finally:
            speaker_task.cancel()

async def main():
    if not CONFIG_PATH.exists():
        print(f"ERROR: ملف الإعدادات غير موجود في {CONFIG_PATH}", flush=True)
        return 1

    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    api_id = config.get("api_id")
    api_hash = config.get("api_hash")
    target = config.get("target_group", "iSSSK")
    room = config.get("room", "majlis")

    if not api_id or not api_hash:
        print("ERROR: api_id و api_hash مطلوبان في telegram.json", flush=True)
        return 1

    bridge = TelegramLiveBridge(api_id, api_hash, target_group=target, room=room)
    await bridge.start()
    return 0

if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(main()))
    except KeyboardInterrupt:
        pass
