from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import io
from PIL import Image
import json
import os
import re
import secrets
import time
import unicodedata
from datetime import datetime
from zoneinfo import ZoneInfo
from dataclasses import dataclass
from typing import Any

USERNAME_RE = re.compile(r"^[A-Za-z0-9_]{3,20}$")
DISPLAY_MAX = 24
PASSWORD_MIN = 15
PASSWORD_MAX = 128
AVATAR_MAX_BYTES = 300 * 1024
SESSION_TTL = max(3600, min(7 * 86400, int(os.getenv("SAMIDEV_SESSION_TTL_SECONDS", str(7 * 86400)))))
GAME_TICKET_TTL = max(15, min(120, int(os.getenv("SAMIDEV_GAME_TICKET_TTL_SECONDS", "45"))))
PBKDF2_ROUNDS = 600_000
PREFIX = os.getenv("SAMIDEV_PLATFORM_PREFIX", "sdp")
COMMUNITY_CHAT_MAX = 120
COMMUNITY_CHAT_CHARS = 280
COMMUNITY_PRESENCE_TTL = 90
COMMUNITY_CHAT_USER_RATE = max(1, min(60, int(os.getenv("SAMIDEV_COMMUNITY_CHAT_USER_RATE", "10"))))
COMMUNITY_CHAT_RATE_WINDOW = max(1, min(60, int(os.getenv("SAMIDEV_COMMUNITY_CHAT_RATE_WINDOW", "12"))))
COMMUNITY_CHAT_ROOM_RATE = max(COMMUNITY_CHAT_USER_RATE, min(600, int(os.getenv("SAMIDEV_COMMUNITY_CHAT_ROOM_RATE", "80"))))
MATCH_REWARD_COINS = max(1, min(10_000, int(os.getenv("SAMIDEV_MATCH_REWARD_COINS", "50"))))
MATCH_REWARD_DAILY_LIMIT = max(1, min(50, int(os.getenv("SAMIDEV_MATCH_REWARD_DAILY_LIMIT", "5"))))
MATCH_REWARD_TIMEZONE = os.getenv("SAMIDEV_MATCH_REWARD_TIMEZONE", "Asia/Riyadh").strip() or "Asia/Riyadh"
try:
    REWARD_TZ = ZoneInfo(MATCH_REWARD_TIMEZONE)
except Exception:
    MATCH_REWARD_TIMEZONE = "UTC"
    REWARD_TZ = ZoneInfo("UTC")
STORE_LEDGER_MAX = 100
# These two locally bundled cosmetics are free; no coins are charged or granted.
# Explicit entitlement avoids treating a missing price as ownership for future items.
STORE_CATALOG: dict[str, dict[str, Any]] = {
    "carrom_classic": {
        "name": "كلاسيك", "description": "خشب فاتح بإطار جوز ولمسات نحاسية. التصميم الافتراضي للكيرم.",
        "slot": "carrom_theme", "category": "carrom", "gameId": "carrom", "asset": "/images/themes/classic-preview.webp",
        "price": 0, "availableToAll": True, "default": True,
    },
    "carrom_cat": {
        "name": "القطو الملكي", "description": "رخام أبيض وذهب وأحجار زرقاء مع قطعة القطو. فعّله لمبارياتك القادمة.",
        "slot": "carrom_theme", "category": "carrom", "gameId": "carrom", "asset": "/images/themes/cat-preview.webp",
        "price": 0, "availableToAll": True, "default": False,
    },
}
STORE_CATALOG.update({
    "pool_cue_classic": {"name":"المضرب الكلاسيكي", "description":"خشب قيقب وجوز، بتصميم بسيط وأنيق.", "slot":"pool_cue", "category":"pool", "gameId":"pool", "asset":"/images/cues/classic-preview.webp", "price":0, "availableToAll":True, "default":True},
    "pool_cue_moon": {"name":"ضوء القمر", "description":"مضرب كحلي وفضي مزين بهلال. يظهر في دورك عند تفعيله.", "slot":"pool_cue", "category":"pool", "gameId":"pool", "asset":"/images/cues/moon-preview.webp", "price":0, "availableToAll":True, "default":False},
    "pool_midnight": {"name":"ليل المجلس", "description":"قماش أزرق وإطار جوز داكن ونحاس.", "slot":"pool_theme", "category":"pool", "gameId":"pool", "asset":"/images/themes/pool-midnight-preview.webp", "price":0, "availableToAll":True, "default":True},
    "pool_emerald": {"name":"زمرد", "description":"قماش زمردي وإطار جوز ونحاس.", "slot":"pool_theme", "category":"pool", "gameId":"pool", "asset":"/images/themes/pool-emerald-preview.webp", "price":0, "availableToAll":True, "default":False},
    "crazy8_original": {"name":"ورق SamiDev", "description":"تصميم كريزي 8 الحالي.", "slot":"crazy8_theme", "category":"crazy8", "gameId":"crazy8", "asset":"/games/crazy8/images/table-background.webp", "price":0, "availableToAll":True, "default":True},
    "soccer_original": {"name":"ملعب SamiDev", "description":"تصميم ملعب الكورة الحالي.", "slot":"tablesoccer_theme", "category":"tablesoccer", "gameId":"tablesoccer", "asset":"/games/tablesoccer/images/thumbnail-standard.png", "price":0, "availableToAll":True, "default":True},
    "badge_palm_swords": {"name":"سيفين ونخلة", "description":"شعار السيفين والنخلة الذهبي يظهر بجانب اسمك في البروفايل والمباريات.", "slot":"name_badge", "category":"profile", "gameId":"", "asset":"/platform/assets/profile/raster/palm-swords.webp", "price":0, "availableToAll":True, "default":True},
    "badge_crown": {"name":"التاج الملكي", "description":"ملصق التاج الذهبي الفاخر بجانب اسمك.", "slot":"name_badge", "category":"profile", "gameId":"", "asset":"/platform/assets/profile/raster/trophy.webp", "price":100, "availableToAll":False, "default":False},
    "badge_fire": {"name":"شعلة الحماس", "description":"ملصق شعلة اللهب المتوهجة بجانب اسمك.", "slot":"name_badge", "category":"profile", "gameId":"", "asset":"/platform/assets/profile/raster/reputation-flame.webp", "price":150, "availableToAll":False, "default":False},
    "profile_star": {"name":"نجمة ذهبية", "description":"ملصق نجمة ذهبية تزين بطاقة ملفك الشخصي. يمكنك جمع حتى 5 نجوم.", "slot":"profile_stars", "category":"profile", "gameId":"", "asset":"/platform/assets/profile/raster/star.webp", "price":50, "maxQuantity":5, "availableToAll":False, "default":False},
})
STORE_DEFAULT_EQUIPPED = {"carrom_theme":"carrom_classic", "pool_theme":"pool_midnight", "pool_cue":"pool_cue_classic", "crazy8_theme":"crazy8_original", "tablesoccer_theme":"soccer_original", "name_badge":"badge_palm_swords"}


def effective_store_equipment(equipped: dict[str, str], inventory: list[str]) -> dict[str, str]:
    result = dict(STORE_DEFAULT_EQUIPPED)
    for slot, item_id in equipped.items():
        item = STORE_CATALOG.get(item_id)
        if item and item_id in inventory and item.get("slot") == slot:
            result[slot] = item_id
    return result


COMMUNITIES = {
    "majlis": {"id":"majlis","name":"المجلس","description":"مساحة اجتماعية مفتوحة للقاء اللاعبين وبدء مباريات سريعة.","accent":"#d5a34c","mark":"م","order":1},
    "square": {"id":"square","name":"الساحة","description":"غرفة نشطة للمباريات السريعة والتجمعات اليومية.","accent":"#2f9ea0","mark":"س","order":2},
    "diwan": {"id":"diwan","name":"الديوان","description":"مساحة هادئة للمحادثة وتكوين مجموعات قبل اللعب.","accent":"#8d6bd1","mark":"د","order":3},
    "elite": {"id":"elite","name":"النخبة","description":"غرفة بطابع تنافسي للاعبين الباحثين عن مباريات أقوى.","accent":"#c45b57","mark":"ن","order":4},
}

def normalize_community_id(value: Any) -> str:
    cid = str(value or "").strip().lower()
    if cid not in COMMUNITIES:
        raise PlatformError("BAD_COMMUNITY", "الغرفة الاجتماعية غير موجودة", 404)
    return cid


class PlatformError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def now_ms() -> int:
    return int(time.time() * 1000)


def reward_day(at_ms: int | None = None) -> str:
    stamp = (int(at_ms) if at_ms is not None else now_ms()) / 1000
    return datetime.fromtimestamp(stamp, tz=REWARD_TZ).date().isoformat()


def sanitize_plain_text(value: Any, max_chars: int, *, empty_code: str = "EMPTY_TEXT", empty_message: str = "النص فارغ", too_long_code: str = "TEXT_TOO_LONG") -> str:
    text = unicodedata.normalize("NFC", str(value or ""))
    # Match the in-game chat policy: remove control, format and surrogate code points.
    # This blocks bidi override/zero-width spoofing (Cf) as well as control characters (Cc).
    text = "".join(ch for ch in text if ch in (" ", "\t") or unicodedata.category(ch) not in {"Cc", "Cf", "Cs"})
    text = " ".join(text.split()).strip()
    if not text:
        raise PlatformError(empty_code, empty_message)
    if len(text) > max_chars:
        raise PlatformError(too_long_code, f"الحد الأقصى {max_chars} حرفًا")
    return text


def sanitize_community_chat_text(value: Any) -> str:
    return sanitize_plain_text(value, COMMUNITY_CHAT_CHARS, empty_code="EMPTY_MESSAGE", empty_message="اكتب رسالة أولًا", too_long_code="CHAT_TOO_LONG")


def normalize_username(value: Any) -> str:
    value = str(value or "").strip()
    if not USERNAME_RE.fullmatch(value):
        raise PlatformError("BAD_USERNAME", "اسم المستخدم يجب أن يكون 3-20 حرفًا ويحتوي حروفًا إنجليزية أو أرقامًا أو _ فقط")
    return value


def normalize_display(value: Any, fallback: str) -> str:
    raw = value if str(value or "").strip() else fallback
    try:
        return sanitize_plain_text(raw, DISPLAY_MAX, empty_code="BAD_DISPLAY", empty_message="الاسم الظاهر غير صالح", too_long_code="BAD_DISPLAY")
    except PlatformError as exc:
        if exc.code == "BAD_DISPLAY" and str(raw) != str(fallback):
            return sanitize_plain_text(fallback, DISPLAY_MAX, empty_code="BAD_DISPLAY", empty_message="الاسم الظاهر غير صالح", too_long_code="BAD_DISPLAY")
        raise


def normalize_avatar_data(value: Any) -> str:
    value = str(value or "").strip()
    if not value:
        return ""
    match = re.fullmatch(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=\r\n]+)", value, re.IGNORECASE)
    if not match:
        raise PlatformError("BAD_AVATAR", "صيغة صورة الملف الشخصي غير مدعومة")
    mime = match.group(1).lower()
    payload = re.sub(r"\s+", "", match.group(2))
    try:
        raw = base64.b64decode(payload, validate=True)
    except Exception as exc:
        raise PlatformError("BAD_AVATAR", "صورة الملف الشخصي غير صالحة") from exc
    if not raw or len(raw) > AVATAR_MAX_BYTES:
        raise PlatformError("AVATAR_TOO_LARGE", "حجم صورة الملف الشخصي كبير جدًا")
    valid = (
        (mime == "png" and raw.startswith(b"\x89PNG\r\n\x1a\n"))
        or (mime == "jpeg" and raw.startswith(b"\xff\xd8\xff"))
        or (mime == "webp" and len(raw) >= 12 and raw[:4] == b"RIFF" and raw[8:12] == b"WEBP")
    )
    if not valid:
        raise PlatformError("BAD_AVATAR", "محتوى صورة الملف الشخصي لا يطابق الصيغة")
    try:
        with Image.open(io.BytesIO(raw)) as image:
            if image.format not in {"PNG", "JPEG", "WEBP"} or image.width * image.height > 1_000_000:
                raise ValueError("avatar dimensions")
            image.verify()
    except Exception as exc:
        raise PlatformError("BAD_AVATAR", "صورة الملف الشخصي غير صالحة") from exc
    return f"data:image/{mime};base64,{payload}"


def _hash_password(password: str, salt: bytes | None = None) -> str:
    if not PASSWORD_MIN <= len(password) <= PASSWORD_MAX:
        raise PlatformError("WEAK_PASSWORD", f"كلمة المرور يجب ألا تقل عن {PASSWORD_MIN} أحرف")
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${base64.urlsafe_b64encode(salt).decode().rstrip('=')}${base64.urlsafe_b64encode(digest).decode().rstrip('=')}"


def _b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def verify_password(password: str, encoded: str) -> bool:
    try:
        algo, rounds, salt_b64, digest_b64 = encoded.split("$", 3)
        if algo != "pbkdf2_sha256" or not 1 <= len(password) <= PASSWORD_MAX or not 100_000 <= int(rounds) <= 2_000_000:
            return False
        salt = _b64decode(salt_b64)
        expected = _b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(rounds))
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def public_user(raw: dict[str, Any], *, relation: str | None = None, online: bool | None = None, include_avatar: bool = False) -> dict[str, Any]:
    created_at = int(raw.get("createdAt") or 0)
    account_age_days = max(0, (now_ms() - created_at) // 86_400_000) if created_at > 0 else 0
    out = {
        "id": str(raw.get("id") or ""),
        "username": str(raw.get("username") or ""),
        "displayName": str(raw.get("displayName") or raw.get("username") or "Player"),
        "role": str(raw.get("role") or "user"),
        "createdAt": created_at,
        "accountAgeDays": int(account_age_days),
        "wins": max(0, int(raw.get("wins") or 0)),
        "reputation": max(0, int(raw.get("reputation") or 0)),
        "banned": str(raw.get("banned") or "0") == "1" if not isinstance(raw.get("banned"), bool) else bool(raw.get("banned")),
    }
    stars_raw = raw.get("starsCount")
    out["starsCount"] = 5 if stars_raw is None else max(0, min(5, int(stars_raw)))
    badge = str(raw.get("nameBadge") or "badge_palm_swords")
    out["nameBadge"] = badge
    badge_item = STORE_CATALOG.get(badge)
    out["nameBadgeAsset"] = badge_item.get("asset", "/platform/assets/profile/raster/palm-swords.webp") if badge_item else "/platform/assets/profile/raster/palm-swords.webp"
    out["nameBadgeName"] = badge_item.get("name", "سيفين ونخلة") if badge_item else "سيفين ونخلة"
    if include_avatar:
        out["avatarData"] = str(raw.get("avatarData") or "")
    if relation is not None:
        out["relation"] = relation
    if online is not None:
        out["online"] = online
    return out


@dataclass
class MemoryEntry:
    value: Any
    expires_at: float | None = None


class PlatformService:
    """Account/social layer inspired by Poly Arena's project-level social architecture.

    The production PostgreSQL service persists accounts/social data while shared
    Redis handles short-lived authentication and presence. Memory mode is for tests.
    """

    def __init__(self, redis_client: Any | None = None):
        self.r = redis_client
        self.lock = asyncio.Lock()
        self.mem_users: dict[str, dict[str, Any]] = {}
        self.mem_usernames: dict[str, str] = {}
        self.mem_sessions: dict[str, MemoryEntry] = {}
        self.mem_tickets: dict[str, MemoryEntry] = {}
        self.mem_friends: dict[str, set[str]] = {}
        self.mem_requests: dict[str, set[str]] = {}
        self.mem_presence: dict[str, float] = {}
        self.mem_rate: dict[str, tuple[int, float]] = {}
        self.password_slots = asyncio.Semaphore(4)
        self.mem_rep_daily: dict[tuple[str, int], set[str]] = {}
        self.mem_match_ratings: set[tuple[str, str, str]] = set()
        self.mem_reports: list[dict[str, Any]] = []
        self.mem_community_chat: dict[str, list[dict[str, Any]]] = {cid: [] for cid in COMMUNITIES}
        self.mem_active_community: dict[str, tuple[str, float]] = {}
        self.mem_inventory: dict[str, set[str]] = {}
        self.mem_equipped: dict[str, dict[str, str]] = {}
        self.mem_store_ledger: dict[str, list[dict[str, Any]]] = {}
        self.mem_daily_match_counts: dict[tuple[str, str], int] = {}
        self.mem_match_reward_claims: set[tuple[str, str]] = set()
        self.mem_game_stats: dict[str, dict[str, dict[str, int]]] = {}
        self.mem_game_results: set[tuple[str, str]] = set()

    def k_user(self, uid: str) -> str: return f"{PREFIX}:user:{uid}"
    def k_username(self, username_lower: str) -> str: return f"{PREFIX}:username:{username_lower}"
    def k_users(self) -> str: return f"{PREFIX}:users"
    def k_game_stats(self, uid: str, game: str) -> str: return f"{PREFIX}:game-stats:{uid}:{game}"
    def k_game_result(self, uid: str, match: str) -> str: return f"{PREFIX}:game-result:{uid}:{match}"

    async def record_game_result(self, uid: str, game: str, match: str, *, won: bool, drawn: bool = False) -> bool:
        from games import GAMES
        if game not in GAMES or not match or len(match) > 128:
            raise PlatformError('BAD_MATCH_RESULT', 'نتيجة المباراة غير صالحة')
        if won and drawn:
            raise PlatformError('BAD_MATCH_RESULT', 'نتيجة المباراة غير صالحة')
        if self.r is not None:
            # Development Redis mode. PostgreSQL overrides this with an SQL
            # result ledger and counters committed in one database transaction.
            script = '''
            if redis.call('EXISTS', KEYS[1]) == 0 then return 0 end
            if redis.call('SET', KEYS[3], '1', 'NX') == false then return 0 end
            redis.call('HINCRBY', KEYS[2], 'played', 1)
            if ARGV[1] == '1' then
              redis.call('HINCRBY', KEYS[2], 'wins', 1)
              redis.call('HINCRBY', KEYS[1], 'wins', 1)
            end
            if ARGV[2] == '1' then redis.call('HINCRBY', KEYS[2], 'draws', 1) end
            return 1
            '''
            return bool(await self.r.eval(script, 3, self.k_user(uid), self.k_game_stats(uid, game), self.k_game_result(uid, match), '1' if won else '0', '1' if drawn else '0'))
        async with self.lock:
            user = self.mem_users.get(uid)
            if not user or (uid, match) in self.mem_game_results: return False
            self.mem_game_results.add((uid, match))
            stats = self.mem_game_stats.setdefault(uid, {}).setdefault(game, {'wins': 0, 'played': 0, 'draws': 0})
            stats['played'] += 1
            if won:
                stats['wins'] += 1
                user['wins'] = str(int(user.get('wins') or 0) + 1)
            if drawn: stats['draws'] += 1
            return True

    async def game_statistics(self, uid: str) -> list[dict[str, Any]]:
        from games import GAMES
        from progression import statistics
        result = []
        for game in GAMES:
            raw = await self.r.hgetall(self.k_game_stats(uid, game)) if self.r is not None else self.mem_game_stats.get(uid, {}).get(game, {})
            result.append(statistics(game, raw))
        return result
    def k_session(self, token: str) -> str: return f"{PREFIX}:session:{token}"
    def k_ticket(self, token: str) -> str: return f"{PREFIX}:ticket:{token}"
    def k_friends(self, uid: str) -> str: return f"{PREFIX}:friends:{uid}"
    def k_requests(self, uid: str) -> str: return f"{PREFIX}:requests:{uid}"
    def k_presence(self, uid: str) -> str: return f"{PREFIX}:presence:{uid}"
    def k_rate(self, key: str) -> str: return f"{PREFIX}:rate:{key}"
    def k_rep_day(self, uid: str, day: int) -> str: return f"{PREFIX}:repday:{uid}:{day}"
    def k_rep_target(self, uid: str, target_id: str, day: int) -> str: return f"{PREFIX}:reptarget:{uid}:{target_id}:{day}"
    def k_match_rating(self, room_id: str, uid: str, target_id: str) -> str: return f"{PREFIX}:matchrating:{room_id}:{uid}:{target_id}"
    def k_reports(self) -> str: return f"{PREFIX}:reports"
    def k_community_chat(self, cid: str) -> str: return f"{PREFIX}:community:{cid}:chat"
    def k_community_members(self, cid: str) -> str: return f"{PREFIX}:community:{cid}:members"
    def k_active_community(self, uid: str) -> str: return f"{PREFIX}:community:active:{uid}"
    def k_inventory(self, uid: str) -> str: return f"{PREFIX}:store:inventory:{uid}"
    def k_equipped(self, uid: str) -> str: return f"{PREFIX}:store:equipped:{uid}"
    def k_store_ledger(self, uid: str) -> str: return f"{PREFIX}:store:ledger:{uid}"
    def k_daily_match_count(self, uid: str, day: str) -> str: return f"{PREFIX}:store:daily-match:{uid}:{day}"
    def k_match_reward_claim(self, uid: str, room_id: str) -> str: return f"{PREFIX}:store:match-claim:{uid}:{room_id}"

    async def community_catalog(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for item in sorted(COMMUNITIES.values(), key=lambda x: int(x.get("order") or 0)):
            cid = str(item["id"])
            members = await self.community_members(cid, 250)
            out.append({**item, "onlineCount": len(members)})
        return out

    async def touch_community(self, uid: str, community_id: str) -> str:
        cid = normalize_community_id(community_id)
        await self.touch_presence(uid)
        if self.r is not None:
            active_key = self.k_active_community(uid)
            old = await self.r.get(active_key)
            p = self.r.pipeline(transaction=True)
            if old and str(old) != cid and str(old) in COMMUNITIES:
                p.srem(self.k_community_members(str(old)), uid)
            p.set(active_key, cid, ex=COMMUNITY_PRESENCE_TTL)
            p.sadd(self.k_community_members(cid), uid)
            await p.execute()
            return cid
        async with self.lock:
            self.mem_active_community[uid] = (cid, time.monotonic() + COMMUNITY_PRESENCE_TTL)
        return cid

    async def leave_community(self, uid: str, community_id: str | None = None) -> str | None:
        requested = normalize_community_id(community_id) if community_id else None
        if self.r is not None:
            active_key = self.k_active_community(uid)
            active = await self.r.get(active_key)
            active_id = str(active or "")
            target = requested or (active_id if active_id in COMMUNITIES else None)
            p = self.r.pipeline(transaction=True)
            if target:
                p.srem(self.k_community_members(target), uid)
            if active_id and active_id in COMMUNITIES and active_id != target:
                p.srem(self.k_community_members(active_id), uid)
            p.delete(active_key)
            await p.execute()
            return target
        async with self.lock:
            active = self.mem_active_community.get(uid)
            active_id = active[0] if active else None
            target = requested or active_id
            self.mem_active_community.pop(uid, None)
            return target

    async def community_members(self, community_id: str, limit: int = 120) -> list[dict[str, Any]]:
        cid = normalize_community_id(community_id)
        limit = max(1, min(250, int(limit)))
        if self.r is not None:
            ids = [str(x) for x in await self.r.smembers(self.k_community_members(cid))]
            out: list[dict[str, Any]] = []
            stale: list[str] = []
            for uid in ids[:500]:
                active = await self.r.get(self.k_active_community(uid))
                if str(active or "") != cid or not await self.is_online(uid):
                    stale.append(uid)
                    continue
                user = await self.get_user(uid)
                if user:
                    out.append(public_user(user, online=True))
                    if len(out) >= limit:
                        break
            if stale:
                await self.r.srem(self.k_community_members(cid), *stale)
            out.sort(key=lambda x: (str(x.get("displayName") or "").lower(), str(x.get("id") or "")))
            return out
        now = time.monotonic()
        out: list[dict[str, Any]] = []
        async with self.lock:
            stale = [uid for uid, (_, exp) in self.mem_active_community.items() if exp <= now]
            for uid in stale:
                self.mem_active_community.pop(uid, None)
            ids = [uid for uid, (active, exp) in self.mem_active_community.items() if active == cid and exp > now]
            for uid in ids[:limit]:
                user = self.mem_users.get(uid)
                if user:
                    out.append(public_user(user, online=True))
        out.sort(key=lambda x: (str(x.get("displayName") or "").lower(), str(x.get("id") or "")))
        return out

    async def community_chat_history(self, community_id: str, limit: int = 80) -> list[dict[str, Any]]:
        cid = normalize_community_id(community_id)
        limit = max(1, min(COMMUNITY_CHAT_MAX, int(limit)))
        if self.r is not None:
            rows = await self.r.lrange(self.k_community_chat(cid), -limit, -1)
            out: list[dict[str, Any]] = []
            for raw in rows:
                try:
                    value = json.loads(raw)
                    if isinstance(value, dict): out.append(value)
                except Exception:
                    pass
            return out
        async with self.lock:
            return [dict(x) for x in self.mem_community_chat.setdefault(cid, [])[-limit:]]

    async def append_community_chat(self, uid: str, community_id: str, text: Any) -> dict[str, Any]:
        cid = normalize_community_id(community_id)
        clean = sanitize_community_chat_text(text)
        user = await self.get_user(uid)
        if not user:
            raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
        entry = {
            "id": secrets.token_urlsafe(8), "communityId": cid, "userId": uid,
            "displayName": sanitize_plain_text(user.get("displayName") or user.get("username") or "Player", DISPLAY_MAX, empty_code="BAD_DISPLAY", empty_message="الاسم الظاهر غير صالح", too_long_code="BAD_DISPLAY"),
            "username": str(user.get("username") or ""), "text": clean, "createdAt": now_ms(),
        }
        if self.r is not None:
            key = self.k_community_chat(cid)
            p = self.r.pipeline(transaction=True)
            p.rpush(key, json.dumps(entry, ensure_ascii=False, separators=(",", ":")))
            p.ltrim(key, -COMMUNITY_CHAT_MAX, -1)
            await p.execute()
        else:
            async with self.lock:
                rows = self.mem_community_chat.setdefault(cid, [])
                rows.append(entry)
                if len(rows) > COMMUNITY_CHAT_MAX:
                    del rows[:-COMMUNITY_CHAT_MAX]
        await self.touch_community(uid, cid)
        return entry

    async def start(self) -> None:
        admin_username = os.getenv("SAMIDEV_ADMIN_USERNAME", "").strip()
        admin_password = os.getenv("SAMIDEV_ADMIN_PASSWORD", "")
        if admin_username and admin_password and not admin_password.startswith("CHANGE_ME"):
            try:
                await self.create_user(admin_username, admin_password, admin_username, role="admin", allow_existing=True)
            except PlatformError:
                pass

    async def allow_rate(self, key: str, limit: int, window: int) -> bool:
        if self.r is not None:
            script = """
            local n = redis.call('INCR', KEYS[1])
            if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
            return n
            """
            return int(await self.r.eval(script, 1, self.k_rate(key), str(window))) <= limit
        async with self.lock:
            now = time.monotonic()
            n, expires = self.mem_rate.get(key, (0, now + window))
            if expires <= now:
                n, expires = 0, now + window
            n += 1
            self.mem_rate[key] = (n, expires)
            return n <= limit

    async def password_work(self, function, *args):
        try:
            await asyncio.wait_for(self.password_slots.acquire(), timeout=0.25)
        except asyncio.TimeoutError:
            raise PlatformError("AUTH_BUSY", "الخدمة مشغولة، حاول بعد قليل", 503)
        task = asyncio.create_task(asyncio.to_thread(function, *args))
        task.add_done_callback(lambda _: self.password_slots.release())
        return await asyncio.shield(task)

    async def create_user(self, username: str, password: str, display_name: str | None = None, *, role: str = "user", allow_existing: bool = False) -> dict[str, Any]:
        username = normalize_username(username)
        lower = username.lower()
        display = normalize_display(display_name, username)
        encoded = await self.password_work(_hash_password, password)
        uid = secrets.token_urlsafe(12)
        created = now_ms()
        user = {"id": uid, "username": username, "usernameLower": lower, "displayName": display, "passwordHash": encoded, "role": role if role in {"user", "admin", "moderator"} else "user", "createdAt": str(created), "wins": "0", "reputation": "0", "coins": "0", "banned": "0", "starsCount": "0", "nameBadge": "badge_palm_swords"}
        if self.r is not None:
            # Username claim is atomic across all gateway replicas.
            claimed = await self.r.set(self.k_username(lower), uid, nx=True)
            if not claimed:
                existing_id = await self.r.get(self.k_username(lower))
                if allow_existing and existing_id:
                    existing = await self.get_user(str(existing_id))
                    if existing:
                        return existing
                raise PlatformError("USERNAME_TAKEN", "اسم المستخدم مستخدم بالفعل", 409)
            try:
                p = self.r.pipeline(transaction=True)
                p.hset(self.k_user(uid), mapping=user)
                p.sadd(self.k_users(), uid)
                await p.execute()
            except Exception:
                await self.r.delete(self.k_username(lower))
                raise
            return user
        async with self.lock:
            if lower in self.mem_usernames:
                if allow_existing:
                    return self.mem_users[self.mem_usernames[lower]]
                raise PlatformError("USERNAME_TAKEN", "اسم المستخدم مستخدم بالفعل", 409)
            self.mem_users[uid] = user
            self.mem_usernames[lower] = uid
            self.mem_friends[uid] = set()
            self.mem_requests[uid] = set()
            self.mem_inventory[uid] = set()
            self.mem_equipped[uid] = {}
            self.mem_store_ledger[uid] = []
            return user

    async def get_user(self, uid: str) -> dict[str, Any] | None:
        if self.r is not None:
            value = await self.r.hgetall(self.k_user(uid))
            return value or None
        return self.mem_users.get(uid)

    async def find_user_by_username(self, username: str) -> dict[str, Any] | None:
        lower = str(username or "").strip().lower()
        if not lower:
            return None
        if self.r is not None:
            uid = await self.r.get(self.k_username(lower))
            return await self.get_user(str(uid)) if uid else None
        uid = self.mem_usernames.get(lower)
        return self.mem_users.get(uid) if uid else None

    async def authenticate(self, username: str, password: str) -> dict[str, Any]:
        user = await self.find_user_by_username(username)
        encoded = str(user.get("passwordHash") or "") if user else "pbkdf2_sha256$600000$MDAwMDAwMDAwMDAwMDAwMA$" + "A" * 43
        valid = await self.password_work(verify_password, password, encoded)
        if not user or not valid:
            raise PlatformError("BAD_LOGIN", "اسم المستخدم أو كلمة المرور غير صحيحة", 401)
        if str(user.get("banned") or "0") == "1":
            raise PlatformError("ACCOUNT_BANNED", "هذا الحساب محظور", 403)
        return user

    async def update_profile(self, uid: str, *, display_name: Any = None, avatar_data: Any = None, update_avatar: bool = False) -> dict[str, Any]:
        user = await self.get_user(uid)
        if not user:
            raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
        updates: dict[str, str] = {}
        if display_name is not None:
            updates["displayName"] = normalize_display(display_name, str(user.get("username") or "Player"))
        if update_avatar:
            updates["avatarData"] = normalize_avatar_data(avatar_data)
        if not updates:
            return user
        if self.r is not None:
            await self.r.hset(self.k_user(uid), mapping=updates)
            return await self.get_user(uid) or {**user, **updates}
        async with self.lock:
            current = self.mem_users.get(uid)
            if not current:
                raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
            current.update(updates)
            return current

    async def increment_wins(self, uid: str, amount: int = 1) -> int:
        """Increment a player's persisted win count and return the new value."""
        amount = max(0, int(amount))
        if amount == 0:
            user = await self.get_user(uid)
            return max(0, int((user or {}).get("wins") or 0))
        user = await self.get_user(uid)
        if not user:
            raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
        if self.r is not None:
            value = int(await self.r.hincrby(self.k_user(uid), "wins", amount))
            return max(0, value)
        async with self.lock:
            current = self.mem_users.get(uid)
            if not current:
                raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
            value = max(0, int(current.get("wins") or 0)) + amount
            current["wins"] = str(value)
            return value

    async def award_daily_match_coins(self, uid: str, room_id: str, *, at_ms: int | None = None) -> dict[str, Any]:
        """Award the server-authoritative daily match reward exactly once per room/player."""
        uid = str(uid or "").strip()
        room_id = str(room_id or "").strip().upper()
        if not uid or not room_id:
            raise PlatformError("BAD_REWARD", "بيانات مكافأة المباراة غير صالحة")
        user = await self.get_user(uid)
        if not user:
            raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
        stamp = int(at_ms) if at_ms is not None else now_ms()
        day = reward_day(stamp)
        if self.r is not None:
            event_id = secrets.token_urlsafe(10)
            script = r'''
            -- samidev:daily-match-reward
            if redis.call('EXISTS', KEYS[1]) == 0 then return {-2,0,0} end
            local current = tonumber(redis.call('HGET', KEYS[1], 'coins') or '0')
            local used = tonumber(redis.call('GET', KEYS[2]) or '0')
            if redis.call('EXISTS', KEYS[3]) == 1 then return {2,used,current} end
            if used >= tonumber(ARGV[1]) then
              redis.call('SET', KEYS[3], 'limit', 'EX', ARGV[8])
              return {0,used,current}
            end
            used = redis.call('INCR', KEYS[2])
            if used == 1 then redis.call('EXPIRE', KEYS[2], ARGV[7]) end
            current = redis.call('HINCRBY', KEYS[1], 'coins', ARGV[2])
            redis.call('SET', KEYS[3], ARGV[2], 'EX', ARGV[8])
            local entry = cjson.encode({id=ARGV[3],type='daily_match_reward',amount=tonumber(ARGV[2]),roomId=ARGV[4],createdAt=tonumber(ARGV[5]),day=ARGV[6],balance=current})
            redis.call('LPUSH', KEYS[4], entry)
            redis.call('LTRIM', KEYS[4], 0, tonumber(ARGV[9]) - 1)
            return {1,used,current}
            '''
            ret = await self.r.eval(
                script, 4,
                self.k_user(uid), self.k_daily_match_count(uid, day), self.k_match_reward_claim(uid, room_id), self.k_store_ledger(uid),
                str(MATCH_REWARD_DAILY_LIMIT), str(MATCH_REWARD_COINS), event_id, room_id, str(stamp), day,
                str(3 * 24 * 60 * 60), str(35 * 24 * 60 * 60), str(STORE_LEDGER_MAX),
            )
            code, used, balance = int(ret[0]), int(ret[1]), max(0, int(ret[2]))
            if code == -2:
                raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
            return {
                "awarded": code == 1, "duplicate": code == 2,
                "amount": MATCH_REWARD_COINS if code == 1 else 0, "coins": balance,
                "rewardedMatchesToday": max(0, used),
                "remainingMatches": max(0, MATCH_REWARD_DAILY_LIMIT - used), "day": day,
            }
        async with self.lock:
            current = self.mem_users.get(uid)
            if not current:
                raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
            claim = (uid, room_id)
            used = self.mem_daily_match_counts.get((uid, day), 0)
            balance = max(0, int(current.get("coins") or 0))
            if claim in self.mem_match_reward_claims:
                return {"awarded": False, "duplicate": True, "amount": 0, "coins": balance, "rewardedMatchesToday": used, "remainingMatches": max(0, MATCH_REWARD_DAILY_LIMIT-used), "day": day}
            self.mem_match_reward_claims.add(claim)
            if used >= MATCH_REWARD_DAILY_LIMIT:
                return {"awarded": False, "duplicate": False, "amount": 0, "coins": balance, "rewardedMatchesToday": used, "remainingMatches": 0, "day": day}
            used += 1
            balance += MATCH_REWARD_COINS
            self.mem_daily_match_counts[(uid, day)] = used
            current["coins"] = str(balance)
            entry = {"id": secrets.token_urlsafe(10), "type": "daily_match_reward", "amount": MATCH_REWARD_COINS, "roomId": room_id, "createdAt": stamp, "day": day, "balance": balance}
            rows = self.mem_store_ledger.setdefault(uid, [])
            rows.insert(0, entry)
            del rows[STORE_LEDGER_MAX:]
            return {"awarded": True, "duplicate": False, "amount": MATCH_REWARD_COINS, "coins": balance, "rewardedMatchesToday": used, "remainingMatches": max(0, MATCH_REWARD_DAILY_LIMIT-used), "day": day}

    async def store_snapshot(self, uid: str, *, at_ms: int | None = None) -> dict[str, Any]:
        user = await self.get_user(uid)
        if not user:
            raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
        day = reward_day(at_ms)
        if self.r is not None:
            daily_raw, inventory_raw, equipped_raw, ledger_raw, coins_raw = await asyncio.gather(
                self.r.get(self.k_daily_match_count(uid, day)), self.r.smembers(self.k_inventory(uid)),
                self.r.hgetall(self.k_equipped(uid)), self.r.lrange(self.k_store_ledger(uid), 0, 19),
                self.r.hget(self.k_user(uid), "coins"),
            )
            used = max(0, int(daily_raw or 0))
            inventory = sorted(str(x) for x in (inventory_raw or set()) if str(x) in STORE_CATALOG)
            equipped = {str(k): str(v) for k, v in (equipped_raw or {}).items() if str(v) in STORE_CATALOG}
            ledger: list[dict[str, Any]] = []
            for raw in ledger_raw or []:
                try:
                    item = json.loads(str(raw))
                    if isinstance(item, dict): ledger.append(item)
                except Exception:
                    continue
        else:
            async with self.lock:
                used = max(0, int(self.mem_daily_match_counts.get((uid, day), 0)))
                inventory = sorted(x for x in self.mem_inventory.get(uid, set()) if x in STORE_CATALOG)
                equipped = {k:v for k,v in self.mem_equipped.get(uid, {}).items() if v in STORE_CATALOG}
                ledger = [dict(x) for x in self.mem_store_ledger.get(uid, [])[:20]]
                coins_raw = user.get("coins") or 0
        stars_raw = user.get("starsCount")
        stars_count = 5 if stars_raw is None else max(0, min(5, int(stars_raw)))
        inventory = sorted(set(inventory) | {item_id for item_id, item in STORE_CATALOG.items() if item.get("availableToAll") is True})
        equipped = effective_store_equipment(equipped, inventory)
        catalog = []
        for item_id, item in STORE_CATALOG.items():
            slot = str(item.get("slot") or "")
            if slot == "profile_stars":
                catalog.append({
                    **item,
                    "id": item_id,
                    "owned": stars_count >= 5,
                    "equipped": stars_count > 0,
                    "starsCount": stars_count,
                    "maxQuantity": 5,
                })
            else:
                catalog.append({
                    **item,
                    "id": item_id,
                    "owned": item_id in inventory,
                    "equipped": equipped.get(slot) == item_id,
                })
        return {
            "coins": max(0, int(coins_raw or 0)),
            "starsCount": stars_count,
            "catalog": catalog,
            "inventory": inventory,
            "equipped": equipped,
            "ledger": ledger,
            "dailyReward": {
                "day": day, "timezone": MATCH_REWARD_TIMEZONE, "coinsPerMatch": MATCH_REWARD_COINS,
                "maxMatches": MATCH_REWARD_DAILY_LIMIT, "rewardedMatches": min(MATCH_REWARD_DAILY_LIMIT, used),
                "remainingMatches": max(0, MATCH_REWARD_DAILY_LIMIT - used), "maxCoins": MATCH_REWARD_COINS * MATCH_REWARD_DAILY_LIMIT
            },
        }

    async def buy_store_item(self, uid: str, item_id: str) -> dict[str, Any]:
        item_id = str(item_id or "").strip()
        item = STORE_CATALOG.get(item_id)
        if not item:
            raise PlatformError("STORE_ITEM_NOT_FOUND", "العنصر غير موجود في المتجر", 404)
        user = await self.get_user(uid)
        if not user:
            raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)

        price = max(0, int(item.get("price") or 0))
        current_coins = max(0, int(user.get("coins") or 0))

        if item.get("slot") == "profile_stars" or item_id == "profile_star":
            stars_raw = user.get("starsCount")
            stars_count = 5 if stars_raw is None else max(0, min(5, int(stars_raw)))
            if stars_count >= 5:
                raise PlatformError("STORE_STAR_MAX", "لديك بالفعل الحد الأقصى من النجوم (5 نجوم)", 400)
            if current_coins < price:
                raise PlatformError("STORE_INSUFFICIENT_COINS", f"رصيدك غير كافٍ. يتطلب {price} عملة (رصيدك الحالي {current_coins})", 400)
            new_coins = current_coins - price
            new_stars = stars_count + 1
            if self.r is not None:
                p = self.r.pipeline(transaction=True)
                p.hset(self.k_user(uid), "coins", str(new_coins))
                p.hset(self.k_user(uid), "starsCount", str(new_stars))
                entry = json.dumps({"id": secrets.token_urlsafe(10), "type": "store_purchase", "itemId": item_id, "amount": -price, "createdAt": now_ms(), "balance": new_coins})
                p.lpush(self.k_store_ledger(uid), entry)
                p.ltrim(self.k_store_ledger(uid), 0, STORE_LEDGER_MAX - 1)
                await p.execute()
            else:
                async with self.lock:
                    user["coins"] = str(new_coins)
                    user["starsCount"] = str(new_stars)
                    entry = {"id": secrets.token_urlsafe(10), "type": "store_purchase", "itemId": item_id, "amount": -price, "createdAt": now_ms(), "balance": new_coins}
                    rows = self.mem_store_ledger.setdefault(uid, [])
                    rows.insert(0, entry)
                    del rows[STORE_LEDGER_MAX:]
            return {"bought": True, "itemId": item_id, "coins": new_coins, "starsCount": new_stars}

        if item.get("availableToAll") is True:
            raise PlatformError("STORE_ALREADY_OWNED", "هذا العنصر مجاني ومتاح للجميع بالفعل", 400)

        if self.r is not None:
            if await self.r.sismember(self.k_inventory(uid), item_id):
                raise PlatformError("STORE_ALREADY_OWNED", "هذا العنصر مملوك لك بالفعل", 400)
        else:
            if item_id in self.mem_inventory.get(uid, set()):
                raise PlatformError("STORE_ALREADY_OWNED", "هذا العنصر مملوك لك بالفعل", 400)

        if current_coins < price:
            raise PlatformError("STORE_INSUFFICIENT_COINS", f"رصيدك غير كافٍ. يتطلب {price} عملة (رصيدك الحالي {current_coins})", 400)

        new_coins = current_coins - price
        if self.r is not None:
            p = self.r.pipeline(transaction=True)
            p.hset(self.k_user(uid), "coins", str(new_coins))
            p.sadd(self.k_inventory(uid), item_id)
            entry = json.dumps({"id": secrets.token_urlsafe(10), "type": "store_purchase", "itemId": item_id, "amount": -price, "createdAt": now_ms(), "balance": new_coins})
            p.lpush(self.k_store_ledger(uid), entry)
            p.ltrim(self.k_store_ledger(uid), 0, STORE_LEDGER_MAX - 1)
            await p.execute()
        else:
            async with self.lock:
                user["coins"] = str(new_coins)
                self.mem_inventory.setdefault(uid, set()).add(item_id)
                entry = {"id": secrets.token_urlsafe(10), "type": "store_purchase", "itemId": item_id, "amount": -price, "createdAt": now_ms(), "balance": new_coins}
                rows = self.mem_store_ledger.setdefault(uid, [])
                rows.insert(0, entry)
                del rows[STORE_LEDGER_MAX:]

        return {"bought": True, "itemId": item_id, "coins": new_coins}

    async def grant_store_item(self, uid: str, item_id: str, *, reason: str = "system") -> bool:
        """Server-only inventory grant. There is intentionally no player HTTP grant endpoint."""
        item_id = str(item_id or "").strip()
        if item_id not in STORE_CATALOG:
            raise PlatformError("STORE_ITEM_NOT_FOUND", "العنصر غير موجود", 404)
        if not await self.get_user(uid):
            raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
        if self.r is not None:
            return bool(await self.r.sadd(self.k_inventory(uid), item_id))
        async with self.lock:
            owned = self.mem_inventory.setdefault(uid, set())
            added = item_id not in owned
            owned.add(item_id)
            return added

    async def equip_store_item(self, uid: str, item_id: str) -> dict[str, str]:
        item_id = str(item_id or "").strip()
        item = STORE_CATALOG.get(item_id)
        if not item:
            raise PlatformError("STORE_ITEM_NOT_FOUND", "العنصر غير موجود", 404)
        slot = str(item.get("slot") or "").strip()
        if not slot or slot == "profile_stars":
            raise PlatformError("STORE_ITEM_INVALID", "العنصر غير قابل للتجهيز")
        user = await self.get_user(uid)
        if not user:
            raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
        available_to_all = item.get("availableToAll") is True
        if self.r is not None:
            if not available_to_all and not await self.r.sismember(self.k_inventory(uid), item_id):
                raise PlatformError("STORE_ITEM_NOT_OWNED", "هذا العنصر غير مملوك", 403)
            p = self.r.pipeline(transaction=True)
            p.hset(self.k_equipped(uid), slot, item_id)
            if slot == "name_badge":
                p.hset(self.k_user(uid), "nameBadge", item_id)
            await p.execute()
            return {str(k): str(v) for k, v in (await self.r.hgetall(self.k_equipped(uid))).items()}
        async with self.lock:
            if not available_to_all and item_id not in self.mem_inventory.get(uid, set()):
                raise PlatformError("STORE_ITEM_NOT_OWNED", "هذا العنصر غير مملوك", 403)
            equipped = self.mem_equipped.setdefault(uid, {})
            equipped[slot] = item_id
            if slot == "name_badge":
                user["nameBadge"] = item_id
            return dict(equipped)

    @staticmethod
    def token_key(token: str | None) -> str | None:
        if not token or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token):
            return None
        return hashlib.sha256(token.encode()).hexdigest()

    async def create_session(self, uid: str) -> str:
        user = await self.get_user(uid)
        if not user or str(user.get("banned") or "0") == "1":
            raise PlatformError("AUTH_REQUIRED", "يجب تسجيل الدخول", 401)
        token = secrets.token_urlsafe(32)
        key = self.token_key(token)
        value = json.dumps({"uid":uid, "version":str(user.get("authVersion") or "0")})
        if self.r is not None:
            await self.r.set(self.k_session(key), value, ex=SESSION_TTL)
        else:
            self.mem_sessions[key] = MemoryEntry(value, time.monotonic() + SESSION_TTL)
        await self.touch_presence(uid)
        return token

    async def resolve_session_key(self, key: str | None, *, touch=False) -> dict[str, Any] | None:
        if not key or not re.fullmatch(r"[a-f0-9]{64}", key):
            return None
        if self.r is not None:
            raw = await self.r.get(self.k_session(key))
        else:
            item = self.mem_sessions.get(key)
            raw = item.value if item and item.expires_at > time.monotonic() else None
            if item and not raw: self.mem_sessions.pop(key, None)
        if not raw: return None
        try:
            data = json.loads(raw)
            user = await self.get_user(str(data["uid"]))
            if not user or str(user.get("banned") or "0") == "1" or str(user.get("authVersion") or "0") != data["version"]:
                return None
        except (ValueError, TypeError, KeyError):
            return None
        if touch: await self.touch_presence(str(user["id"]))
        return user

    async def resolve_session(self, token: str | None) -> dict[str, Any] | None:
        return await self.resolve_session_key(self.token_key(token), touch=True)

    async def delete_session(self, token: str | None) -> None:
        key = self.token_key(token)
        if not key: return
        if self.r is not None: await self.r.delete(self.k_session(key))
        else: self.mem_sessions.pop(key, None)

    async def touch_presence(self, uid: str) -> None:
        if self.r is not None:
            await self.r.set(self.k_presence(uid), "1", ex=75)
        else:
            self.mem_presence[uid] = time.monotonic() + 75

    async def is_online(self, uid: str) -> bool:
        if self.r is not None:
            return bool(await self.r.exists(self.k_presence(uid)))
        return self.mem_presence.get(uid, 0) > time.monotonic()

    async def issue_game_ticket(self, user: dict[str, Any], community_id: str | None = None, *, session_token: str | None = None) -> dict[str, Any]:
        token = secrets.token_urlsafe(28)
        payload = {
            "uid": str(user["id"]),
            "username": str(user["username"]),
            "displayName": str(user.get("displayName") or user["username"]),
            "role": str(user.get("role") or "user"),
            "issuedAt": now_ms(),
            "sessionKey": self.token_key(session_token),
            "authVersion": str(user.get("authVersion") or "0"),
        }
        if community_id:
            payload["communityId"] = normalize_community_id(community_id)
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        if self.r is not None:
            await self.r.set(self.k_ticket(self.token_key(token)), raw, ex=GAME_TICKET_TTL)
        else:
            self.mem_tickets[self.token_key(token)] = MemoryEntry(raw, time.monotonic() + GAME_TICKET_TTL)
        return {"ticket": token, "expiresIn": GAME_TICKET_TTL}

    async def consume_game_ticket(self, token: str | None) -> dict[str, Any] | None:
        if not token:
            return None
        raw: str | None = None
        if self.r is not None:
            # GETDEL makes the ticket single-use across all gateway replicas.
            raw = await self.r.getdel(self.k_ticket(self.token_key(token)))
        else:
            item = self.mem_tickets.pop(self.token_key(token), None)
            if item and (item.expires_at is None or item.expires_at > time.monotonic()):
                raw = str(item.value)
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except Exception:
            return None
        user = await self.get_user(str(data.get("uid") or ""))
        if not user or str(user.get("banned") or "0") == "1":
            return None
        if str(user.get("authVersion") or "0") != str(data.get("authVersion") or "0"): return None
        if data.get("sessionKey"):
            if not await self.resolve_session_key(data["sessionKey"]): return None
        elif os.getenv("SAMIDEV_PRODUCTION", "0") == "1": return None
        await self.touch_presence(str(user["id"]))
        return data

    async def send_friend_request(self, sender: dict[str, Any], target_username: str) -> dict[str, Any]:
        target = await self.find_user_by_username(target_username)
        if not target:
            raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
        a, b = str(sender["id"]), str(target["id"])
        if a == b:
            raise PlatformError("SELF_FRIEND", "لا يمكنك إضافة نفسك")
        if await self.are_friends(a, b):
            raise PlatformError("ALREADY_FRIENDS", "هذا المستخدم موجود في قائمة أصدقائك", 409)
        if self.r is not None:
            # If the other side already requested us, accept automatically.
            if await self.r.sismember(self.k_requests(a), b):
                await self._make_friends(a, b)
                await self.r.srem(self.k_requests(a), b)
                return {"status": "accepted", "user": public_user(target)}
            await self.r.sadd(self.k_requests(b), a)
        else:
            if b in self.mem_requests.setdefault(a, set()):
                await self._make_friends(a, b)
                self.mem_requests[a].discard(b)
                return {"status": "accepted", "user": public_user(target)}
            self.mem_requests.setdefault(b, set()).add(a)
        return {"status": "pending", "user": public_user(target)}

    async def are_friends(self, a: str, b: str) -> bool:
        if self.r is not None:
            return bool(await self.r.sismember(self.k_friends(a), b))
        return b in self.mem_friends.setdefault(a, set())

    async def _make_friends(self, a: str, b: str) -> None:
        if self.r is not None:
            p = self.r.pipeline(transaction=True)
            p.sadd(self.k_friends(a), b)
            p.sadd(self.k_friends(b), a)
            p.srem(self.k_requests(a), b)
            p.srem(self.k_requests(b), a)
            await p.execute()
        else:
            self.mem_friends.setdefault(a, set()).add(b)
            self.mem_friends.setdefault(b, set()).add(a)
            self.mem_requests.setdefault(a, set()).discard(b)
            self.mem_requests.setdefault(b, set()).discard(a)

    async def respond_friend_request(self, user: dict[str, Any], sender_id: str, accept: bool) -> dict[str, Any]:
        uid = str(user["id"])
        sender = await self.get_user(sender_id)
        if not sender:
            raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
        if self.r is not None:
            exists = await self.r.sismember(self.k_requests(uid), sender_id)
            if not exists:
                raise PlatformError("REQUEST_NOT_FOUND", "طلب الصداقة غير موجود", 404)
            await self.r.srem(self.k_requests(uid), sender_id)
        else:
            if sender_id not in self.mem_requests.setdefault(uid, set()):
                raise PlatformError("REQUEST_NOT_FOUND", "طلب الصداقة غير موجود", 404)
            self.mem_requests[uid].discard(sender_id)
        if accept:
            await self._make_friends(uid, sender_id)
        return {"accepted": bool(accept), "user": public_user(sender)}

    async def remove_friend(self, uid: str, friend_id: str) -> None:
        if self.r is not None:
            p = self.r.pipeline(transaction=True)
            p.srem(self.k_friends(uid), friend_id)
            p.srem(self.k_friends(friend_id), uid)
            await p.execute()
        else:
            self.mem_friends.setdefault(uid, set()).discard(friend_id)
            self.mem_friends.setdefault(friend_id, set()).discard(uid)

    async def social_state(self, user: dict[str, Any]) -> dict[str, Any]:
        uid = str(user["id"])
        if self.r is not None:
            friend_ids = list(await self.r.smembers(self.k_friends(uid)))
            request_ids = list(await self.r.smembers(self.k_requests(uid)))
        else:
            friend_ids = list(self.mem_friends.setdefault(uid, set()))
            request_ids = list(self.mem_requests.setdefault(uid, set()))
        async def pack(ids: list[str], relation: str) -> list[dict[str, Any]]:
            out: list[dict[str, Any]] = []
            for user_id in ids[:100]:
                raw = await self.get_user(str(user_id))
                if raw:
                    out.append(public_user(raw, relation=relation, online=await self.is_online(str(user_id))))
            out.sort(key=lambda x: (not x.get("online", False), x["displayName"].lower()))
            return out
        return {"friends": await pack(friend_ids, "friend"), "requests": await pack(request_ids, "incoming")}

    async def relationship(self, current_uid: str, target_uid: str) -> str:
        if not current_uid or not target_uid:
            return "none"
        if await self.are_friends(current_uid, target_uid):
            return "friend"
        if self.r is not None:
            if await self.r.sismember(self.k_requests(current_uid), target_uid):
                return "incoming"
            if await self.r.sismember(self.k_requests(target_uid), current_uid):
                return "outgoing"
        else:
            if target_uid in self.mem_requests.setdefault(current_uid, set()):
                return "incoming"
            if current_uid in self.mem_requests.setdefault(target_uid, set()):
                return "outgoing"
        return "none"

    async def public_profile(self, target_id: str, viewer_id: str | None = None) -> dict[str, Any]:
        target = await self.get_user(target_id)
        if not target or str(target.get("banned") or "0") == "1":
            raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
        relation = await self.relationship(viewer_id, target_id) if viewer_id and viewer_id != target_id else ("self" if viewer_id == target_id else "none")
        out = public_user(target, relation=relation, online=await self.is_online(target_id))
        out["hasAvatar"] = bool(str(target.get("avatarData") or "").strip())
        # Public, read-only showcase sourced from the existing store inventory.
        # No private balances, purchases, or equipment mutation is exposed.
        if self.r is not None:
            owned = {str(x) for x in (await self.r.smembers(self.k_inventory(target_id)) or set())}
        else:
            owned = set(self.mem_inventory.get(target_id, set()))
        out["showcaseItems"] = [
            {"id": item_id, "name": item["name"], "asset": item.get("asset", ""), "gameId": item.get("gameId", ""), "quantity": 1, "category": item.get("category", "")}
            for item_id, item in STORE_CATALOG.items()
            if item_id in owned
        ]
        stars = max(0, min(5, int(target.get('starsCount') or 0)))
        if stars:
            item = STORE_CATALOG['profile_star']
            out['showcaseItems'].append(dict(id='profile_star', name=item['name'], asset=item['asset'], gameId='', quantity=stars, category='profile'))
        out['ownedItemCount'] = sum(x['quantity'] for x in out['showcaseItems'])
        out['gameStatistics'] = await self.game_statistics(target_id)
        out['statisticsHistory'] = 'tracked_matches_only'
        out['legacyWins'] = max(0, out['wins'] - sum(x['wins'] for x in out['gameStatistics']))

        if self.r is not None:
            equipped_badge = str(await self.r.hget(self.k_equipped(target_id), "name_badge") or "")
        else:
            equipped_badge = str(self.mem_equipped.get(target_id, {}).get("name_badge") or "")
        if equipped_badge:
            out["nameBadge"] = equipped_badge
            badge_item = STORE_CATALOG.get(equipped_badge)
            if badge_item:
                out["nameBadgeAsset"] = badge_item.get("asset", out.get("nameBadgeAsset"))
                out["nameBadgeName"] = badge_item.get("name", out.get("nameBadgeName"))

        if viewer_id:
            day = now_ms() // 86_400_000
            if self.r is not None:
                used = int(await self.r.get(self.k_rep_day(viewer_id, day)) or 0)
                out["reputationDailyRemaining"] = max(0, 5 - used)
                out["reputationGrantedToday"] = bool(await self.r.exists(self.k_rep_target(viewer_id, target_id, day)))
            else:
                granted = self.mem_rep_daily.get((viewer_id, day), set())
                out["reputationDailyRemaining"] = max(0, 5 - len(granted))
                out["reputationGrantedToday"] = target_id in granted
        return out

    async def grant_reputation(self, giver_id: str, target_id: str) -> dict[str, Any]:
        if giver_id == target_id:
            raise PlatformError("SELF_REPUTATION", "لا يمكنك منح السمعة لنفسك")
        target = await self.get_user(target_id)
        if not target or str(target.get("banned") or "0") == "1":
            raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
        day = now_ms() // 86_400_000
        ttl = max(60, int(((day + 1) * 86_400_000 - now_ms()) / 1000) + 120)
        if self.r is not None:
            script = """
            -- samidev:grant-reputation
            local used = tonumber(redis.call('GET', KEYS[1]) or '0')
            if used >= tonumber(ARGV[1]) then return {-1, used, tonumber(redis.call('HGET', KEYS[3], 'reputation') or '0')} end
            if redis.call('EXISTS', KEYS[2]) == 1 then return {-2, used, tonumber(redis.call('HGET', KEYS[3], 'reputation') or '0')} end
            redis.call('SET', KEYS[2], '1', 'EX', ARGV[2])
            local n = redis.call('INCR', KEYS[1])
            if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[2]) end
            local rep = redis.call('HINCRBY', KEYS[3], 'reputation', 1)
            return {1, n, rep}
            """
            ret = await self.r.eval(
                script, 3,
                self.k_rep_day(giver_id, day),
                self.k_rep_target(giver_id, target_id, day),
                self.k_user(target_id),
                "5", str(ttl),
            )
            code, used, reputation = int(ret[0]), int(ret[1]), int(ret[2])
            if code == -1:
                raise PlatformError("REPUTATION_DAILY_LIMIT", "استخدمت منح السمعة الخمس لهذا اليوم", 429)
            if code == -2:
                raise PlatformError("REPUTATION_ALREADY_GIVEN", "منحت هذا اللاعب سمعة اليوم بالفعل", 409)
            return {"reputation": max(0, reputation), "remaining": max(0, 5 - used)}
        async with self.lock:
            granted = self.mem_rep_daily.setdefault((giver_id, day), set())
            if len(granted) >= 5:
                raise PlatformError("REPUTATION_DAILY_LIMIT", "استخدمت منح السمعة الخمس لهذا اليوم", 429)
            if target_id in granted:
                raise PlatformError("REPUTATION_ALREADY_GIVEN", "منحت هذا اللاعب سمعة اليوم بالفعل", 409)
            granted.add(target_id)
            current = self.mem_users[target_id]
            reputation = max(0, int(current.get("reputation") or 0)) + 1
            current["reputation"] = str(reputation)
            return {"reputation": reputation, "remaining": max(0, 5 - len(granted))}

    async def record_match_rating(self, giver_id: str, target_id: str, room_id: str, liked: bool) -> dict[str, Any]:
        if giver_id == target_id:
            raise PlatformError("SELF_RATING", "لا يمكنك تقييم نفسك")
        target = await self.get_user(target_id)
        if not target:
            raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
        room_id = str(room_id or "").strip()
        if not room_id:
            raise PlatformError("BAD_ROOM", "المباراة غير صالحة")
        if self.r is not None:
            # Claim the rating and mutate reputation atomically. A dislike removes
            # one point, but reputation never drops below zero.
            script = """
            -- samidev:match-rating
            if redis.call('EXISTS', KEYS[1]) == 1 then return {-1, tonumber(redis.call('HGET', KEYS[2], 'reputation') or '0')} end
            redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
            local rep = tonumber(redis.call('HGET', KEYS[2], 'reputation') or '0')
            if ARGV[1] == '1' then
                rep = rep + 1
            else
                rep = math.max(0, rep - 1)
            end
            redis.call('HSET', KEYS[2], 'reputation', tostring(rep))
            return {1, rep}
            """
            ret = await self.r.eval(
                script, 2,
                self.k_match_rating(room_id, giver_id, target_id),
                self.k_user(target_id),
                "1" if liked else "0", str(30 * 24 * 60 * 60),
            )
            if int(ret[0]) == -1:
                raise PlatformError("MATCH_ALREADY_RATED", "تم تقييم هذا اللاعب في هذه المباراة", 409)
            return {"liked": bool(liked), "reputation": max(0, int(ret[1]))}
        async with self.lock:
            key = (room_id, giver_id, target_id)
            if key in self.mem_match_ratings:
                raise PlatformError("MATCH_ALREADY_RATED", "تم تقييم هذا اللاعب في هذه المباراة", 409)
            self.mem_match_ratings.add(key)
            current = self.mem_users[target_id]
            reputation = max(0, int(current.get("reputation") or 0))
            reputation = reputation + 1 if liked else max(0, reputation - 1)
            current["reputation"] = str(reputation)
            return {"liked": bool(liked), "reputation": reputation}

    async def submit_report(self, reporter_id: str, target_id: str, *, message: str = "", room_id: str = "") -> dict[str, Any]:
        if reporter_id == target_id:
            raise PlatformError("SELF_REPORT", "لا يمكنك الإبلاغ عن نفسك")
        target = await self.get_user(target_id)
        reporter = await self.get_user(reporter_id)
        if not target or not reporter:
            raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
        message = " ".join(str(message or "").split()).strip()[:500]
        report = {
            "id": secrets.token_urlsafe(10),
            "createdAt": now_ms(),
            "status": "open",
            "reporterId": reporter_id,
            "reporterName": str(reporter.get("displayName") or reporter.get("username") or "Player"),
            "targetId": target_id,
            "targetName": str(target.get("displayName") or target.get("username") or "Player"),
            "roomId": str(room_id or "")[:32],
            "message": message,
        }
        if self.r is not None:
            encoded = json.dumps(report, ensure_ascii=False, separators=(",", ":"))
            p = self.r.pipeline(transaction=True)
            p.lpush(self.k_reports(), encoded)
            p.ltrim(self.k_reports(), 0, 4999)
            await p.execute()
        else:
            async with self.lock:
                self.mem_reports.insert(0, report)
                del self.mem_reports[5000:]
        return report

    async def list_reports(self, limit: int = 200) -> list[dict[str, Any]]:
        limit = max(1, min(500, int(limit)))
        if self.r is not None:
            raw = await self.r.lrange(self.k_reports(), 0, limit - 1)
            out: list[dict[str, Any]] = []
            for item in raw:
                try:
                    value = json.loads(item)
                    if isinstance(value, dict):
                        out.append(value)
                except Exception:
                    continue
            return out
        return [dict(x) for x in self.mem_reports[:limit]]

    async def search_users(self, query: str, current_uid: str, limit: int = 15) -> list[dict[str, Any]]:
        q = str(query or "").strip().lower()
        if len(q) < 2:
            return []
        if self.r is not None:
            ids = list(await self.r.smembers(self.k_users()))
        else:
            ids = list(self.mem_users.keys())
        out: list[dict[str, Any]] = []
        for uid in ids:
            if str(uid) == current_uid:
                continue
            raw = await self.get_user(str(uid))
            if not raw:
                continue
            hay = f"{raw.get('username','')} {raw.get('displayName','')}".lower()
            if q in hay:
                relation = "friend" if await self.are_friends(current_uid, str(uid)) else "none"
                out.append(public_user(raw, relation=relation, online=await self.is_online(str(uid))))
                if len(out) >= limit:
                    break
        return out

    async def list_users(self, limit: int = 200) -> list[dict[str, Any]]:
        if self.r is not None:
            ids = list(await self.r.smembers(self.k_users()))
        else:
            ids = list(self.mem_users.keys())
        out: list[dict[str, Any]] = []
        for uid in ids[:limit]:
            raw = await self.get_user(str(uid))
            if raw:
                out.append(public_user(raw, online=await self.is_online(str(uid))))
        out.sort(key=lambda x: x.get("createdAt", 0), reverse=True)
        return out

    async def set_banned(self, target_id: str, banned: bool) -> dict[str, Any]:
        user = await self.get_user(target_id)
        if not user:
            raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
        if self.r is not None:
            pipeline = self.r.pipeline(transaction=True)
            pipeline.hset(self.k_user(target_id), "banned", "1" if banned else "0")
            if banned: pipeline.hincrby(self.k_user(target_id), "authVersion", 1)
            await pipeline.execute()
        else:
            user["banned"] = "1" if banned else "0"
            if banned: user["authVersion"] = str(int(user.get("authVersion") or 0) + 1)
        return public_user(await self.get_user(target_id) or user)

    async def set_role(self, target_id: str, role: str) -> dict[str, Any]:
        if role not in {"user", "moderator", "admin"}:
            raise PlatformError("BAD_ROLE", "الصلاحية غير مدعومة")
        user = await self.get_user(target_id)
        if not user:
            raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
        if self.r is not None:
            await self.r.hset(self.k_user(target_id), "role", role)
        else:
            user["role"] = role
        return public_user(await self.get_user(target_id) or user)

# HTTP API layer kept here so the game realtime code stays focused on matches.
from aiohttp import web

SESSION_COOKIE = "samidev_session"


class PlatformHttp:
    def __init__(self, platform: PlatformService, room_store: Any, *, trust_proxy: bool = False, trust_forwarded_https: bool = False):
        self.platform = platform
        self.room_store = room_store
        self.trust_proxy = trust_proxy
        self.trust_forwarded_https = trust_forwarded_https

    def _peer(self, request: web.Request) -> str:
        peer = request.remote or "?"
        if self.trust_proxy:
            value = request.headers.get("X-Real-IP") or request.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
            if value:
                peer = value
        return peer

    def _secure(self, request: web.Request) -> bool:
        if request.secure:
            return True
        if self.trust_proxy or self.trust_forwarded_https:
            return request.headers.get("X-Forwarded-Proto", "").lower() == "https"
        return False

    async def _body(self, request: web.Request) -> dict[str, Any]:
        try:
            value = await request.json()
        except Exception:
            raise PlatformError("BAD_JSON", "الطلب غير صالح")
        if not isinstance(value, dict):
            raise PlatformError("BAD_JSON", "الطلب غير صالح")
        return value

    async def _user(self, request: web.Request) -> dict[str, Any]:
        token = request.cookies.get(SESSION_COOKIE)
        user = await self.platform.resolve_session(token)
        if not user:
            raise PlatformError("AUTH_REQUIRED", "يجب تسجيل الدخول أولًا", 401)
        return user

    async def _optional_user(self, request: web.Request) -> dict[str, Any] | None:
        token = request.cookies.get(SESSION_COOKIE)
        if not token:
            return None
        return await self.platform.resolve_session(token)

    async def _admin(self, request: web.Request) -> dict[str, Any]:
        user = await self._user(request)
        if str(user.get("role") or "user") not in {"admin", "moderator"}:
            raise PlatformError("ADMIN_REQUIRED", "لا تملك صلاحية الإدارة", 403)
        return user

    def _session_response(self, user: dict[str, Any], token: str) -> web.Response:
        response = web.json_response({"ok": True, "user": public_user(user, include_avatar=True)})
        # secure is applied by the route because it depends on the request scheme.
        response._samidev_session_token = token  # type: ignore[attr-defined]
        return response

    async def register(self, request: web.Request) -> web.Response:
        peer = self._peer(request)
        if not await self.platform.allow_rate(f"register:{peer}", 8, 300):
            raise PlatformError("RATE_LIMIT", "محاولات كثيرة؛ حاول لاحقًا", 429)
        body = await self._body(request)
        user = await self.platform.create_user(body.get("username"), str(body.get("password") or ""), body.get("displayName"))
        await self.platform.delete_session(request.cookies.get(SESSION_COOKIE))
        token = await self.platform.create_session(str(user["id"]))
        response = web.json_response({"ok": True, "user": public_user(user, include_avatar=True)})
        response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_TTL, httponly=True, secure=self._secure(request), samesite="Lax", path="/")
        return response

    async def login(self, request: web.Request) -> web.Response:
        peer = self._peer(request)
        if not await self.platform.allow_rate(f"login:{peer}", 20, 300):
            raise PlatformError("RATE_LIMIT", "محاولات تسجيل دخول كثيرة؛ حاول لاحقًا", 429)
        body = await self._body(request)
        account = hashlib.sha256(str(body.get("username") or "").strip().lower().encode()).hexdigest()
        if not await self.platform.allow_rate(f"login-account:{account}", 30, 300):
            raise PlatformError("RATE_LIMIT", "محاولات كثيرة؛ حاول لاحقًا", 429)
        user = await self.platform.authenticate(str(body.get("username") or ""), str(body.get("password") or ""))
        await self.platform.delete_session(request.cookies.get(SESSION_COOKIE))
        token = await self.platform.create_session(str(user["id"]))
        response = web.json_response({"ok": True, "user": public_user(user, include_avatar=True)})
        response.set_cookie(SESSION_COOKIE, token, max_age=SESSION_TTL, httponly=True, secure=self._secure(request), samesite="Lax", path="/")
        return response

    async def logout(self, request: web.Request) -> web.Response:
        token = request.cookies.get(SESSION_COOKIE)
        await self.platform.delete_session(token)
        response = web.json_response({"ok": True})
        response.del_cookie(SESSION_COOKIE, path="/")
        return response

    async def me(self, request: web.Request) -> web.Response:
        user = await self._user(request)
        profile = await self.platform.public_profile(str(user['id']), str(user['id']))
        profile['avatarData'] = str(user.get('avatarData') or '')
        return web.json_response({"ok": True, "user": profile})

    async def store_state(self, request: web.Request) -> web.Response:
        user = await self._user(request)
        snapshot = await self.platform.store_snapshot(str(user["id"]))
        return web.json_response({"ok": True, **snapshot}, headers={"Cache-Control": "private, no-store"})

    async def store_equip(self, request: web.Request) -> web.Response:
        user = await self._user(request)
        if not await self.platform.allow_rate(f"store-equip:{user['id']}", 30, 60):
            raise PlatformError("RATE_LIMIT", "محاولات كثيرة؛ حاول بعد قليل", 429)
        body = await self._body(request)
        item_id = str(body.get("itemId") or "").strip()
        requested_game = str(body.get("gameId") or "").strip()
        item = STORE_CATALOG.get(item_id)
        if requested_game and item and str(item.get("gameId") or "") != requested_game:
            raise PlatformError("STORE_GAME_MISMATCH", "هذا العنصر غير مخصص للعبة الحالية", 400)
        equipped = await self.platform.equip_store_item(str(user["id"]), item_id)
        return web.json_response({"ok": True, "equipped": equipped}, headers={"Cache-Control": "private, no-store"})

    async def store_buy(self, request: web.Request) -> web.Response:
        user = await self._user(request)
        if not await self.platform.allow_rate(f"store-buy:{user['id']}", 30, 60):
            raise PlatformError("RATE_LIMIT", "محاولات كثيرة؛ حاول بعد قليل", 429)
        body = await self._body(request)
        item_id = str(body.get("itemId") or "").strip()
        result = await self.platform.buy_store_item(str(user["id"]), item_id)
        return web.json_response({"ok": True, **result}, headers={"Cache-Control": "private, no-store"})

    async def avatar_image(self, request: web.Request) -> web.Response:
        # Avatars are public game-facing media. A player may enter the game using a
        # one-time game ticket (or an anonymous development connection) without an
        # active platform HTTP session, so requiring the session cookie here made
        # opponents fail to load each other's pictures. Only opaque user ids are
        # accepted, the route returns image bytes only, and scraping is rate-limited.
        peer = self._peer(request)
        if not await self.platform.allow_rate(f"avatar:{peer}", 240, 60):
            raise PlatformError("RATE_LIMIT", "طلبات صور كثيرة؛ حاول لاحقًا", 429)
        target_id = str(request.match_info.get("user_id") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{12,32}", target_id):
            raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
        target = await self.platform.get_user(target_id)
        if not target:
            raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
        value = str(target.get("avatarData") or "").strip()
        if not value:
            return web.Response(status=204, headers={"Cache-Control": "no-store", "Cross-Origin-Resource-Policy": "same-origin"})
        match = re.fullmatch(r"data:image/(png|jpeg|webp);base64,([A-Za-z0-9+/=\r\n]+)", value, re.IGNORECASE)
        if not match:
            return web.Response(status=204, headers={"Cache-Control": "no-store", "Cross-Origin-Resource-Policy": "same-origin"})
        try:
            raw = base64.b64decode(re.sub(r"\s+", "", match.group(2)), validate=True)
        except Exception:
            return web.Response(status=204, headers={"Cache-Control": "no-store", "Cross-Origin-Resource-Policy": "same-origin"})
        mime = match.group(1).lower()
        return web.Response(
            body=raw,
            content_type=f"image/{mime}",
            headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", "Cross-Origin-Resource-Policy": "same-origin", "X-Robots-Tag": "noindex, nofollow"},
        )

    async def profile_update(self, request: web.Request) -> web.Response:
        user = await self._user(request)
        if not await self.platform.allow_rate(f"profile:{user['id']}", 20, 300):
            raise PlatformError("RATE_LIMIT", "محاولات تحديث كثيرة؛ حاول لاحقًا", 429)
        body = await self._body(request)
        updated = await self.platform.update_profile(
            str(user["id"]),
            display_name=body.get("displayName") if "displayName" in body else None,
            avatar_data=body.get("avatarData"),
            update_avatar="avatarData" in body,
        )
        return web.json_response({"ok": True, "user": public_user(updated, include_avatar=True)})

    async def heartbeat(self, request: web.Request) -> web.Response:
        user = await self._user(request)
        await self.platform.touch_presence(str(user["id"]))
        return web.json_response({"ok": True})

    async def communities(self, request: web.Request) -> web.Response:
        await self._user(request)
        rooms = await self.room_store.list_public_rooms(200)
        room_counts: dict[str, int] = {cid: 0 for cid in COMMUNITIES}
        for room in rooms:
            cid = str(room.get("communityId") or "majlis")
            if cid in room_counts:
                room_counts[cid] += 1
        items = await self.platform.community_catalog()
        for item in items:
            item["gameRoomCount"] = room_counts.get(str(item["id"]), 0)
        return web.json_response({"ok": True, "communities": items, "ts": now_ms()})

    async def community_state(self, request: web.Request) -> web.Response:
        user = await self._user(request)
        cid = normalize_community_id(request.match_info.get("community_id"))
        await self.platform.touch_community(str(user["id"]), cid)
        rooms = [r for r in await self.room_store.list_public_rooms(200) if str(r.get("communityId") or "majlis") == cid]
        return web.json_response({
            "ok": True, "community": dict(COMMUNITIES[cid]),
            "members": await self.platform.community_members(cid),
            "messages": await self.platform.community_chat_history(cid),
            "rooms": rooms, "ts": now_ms(),
        })

    async def community_enter(self, request: web.Request) -> web.Response:
        user = await self._user(request)
        cid = normalize_community_id(request.match_info.get("community_id"))
        await self.platform.touch_community(str(user["id"]), cid)
        return web.json_response({"ok": True, "communityId": cid})

    async def community_leave(self, request: web.Request) -> web.Response:
        user = await self._user(request)
        cid = normalize_community_id(request.match_info.get("community_id"))
        await self.platform.leave_community(str(user["id"]), cid)
        return web.json_response({"ok": True, "communityId": cid})

    async def community_chat(self, request: web.Request) -> web.Response:
        user = await self._user(request)
        cid = normalize_community_id(request.match_info.get("community_id"))
        if not await self.platform.allow_rate(f"community-chat:{user['id']}:{cid}", COMMUNITY_CHAT_USER_RATE, COMMUNITY_CHAT_RATE_WINDOW):
            raise PlatformError("RATE_LIMIT", "أرسلت رسائل كثيرة بسرعة؛ حاول بعد قليل", 429)
        if not await self.platform.allow_rate(f"community-chat-room:{cid}", COMMUNITY_CHAT_ROOM_RATE, COMMUNITY_CHAT_RATE_WINDOW):
            raise PlatformError("ROOM_RATE_LIMIT", "المحادثة نشطة جدًا الآن؛ حاول بعد لحظات", 429)
        body = await self._body(request)
        entry = await self.platform.append_community_chat(str(user["id"]), cid, body.get("text"))
        return web.json_response({"ok": True, "message": entry})

    async def lobby_rooms(self, request: web.Request) -> web.Response:
        await self._user(request)
        rooms = await self.room_store.list_public_rooms(120)
        return web.json_response({"ok": True, "rooms": rooms, "ts": now_ms()})

    async def game_ticket(self, request: web.Request) -> web.Response:
        user = await self._user(request)
        body = await self._body(request)
        community_id = body.get("communityId")
        if not await self.platform.allow_rate(f"game-ticket:{user['id']}", 30, 60):
            raise PlatformError("RATE_LIMIT", "محاولات كثيرة؛ حاول لاحقًا", 429)
        value = await self.platform.issue_game_ticket(user, str(community_id) if community_id else None, session_token=request.cookies.get(SESSION_COOKIE))
        return web.json_response({"ok": True, **value, "displayName": user.get("displayName") or user.get("username")})

    async def friends(self, request: web.Request) -> web.Response:
        user = await self._user(request)
        return web.json_response({"ok": True, **await self.platform.social_state(user)})

    async def friend_request(self, request: web.Request) -> web.Response:
        user = await self._user(request)
        body = await self._body(request)
        result = await self.platform.send_friend_request(user, str(body.get("username") or ""))
        return web.json_response({"ok": True, **result})

    async def friend_respond(self, request: web.Request) -> web.Response:
        user = await self._user(request)
        body = await self._body(request)
        sender_id = str(body.get("userId") or "")
        if not sender_id:
            raise PlatformError("BAD_USER", "المستخدم غير صالح")
        result = await self.platform.respond_friend_request(user, sender_id, bool(body.get("accept")))
        return web.json_response({"ok": True, **result})

    async def friend_remove(self, request: web.Request) -> web.Response:
        user = await self._user(request)
        friend_id = str(request.match_info.get("user_id") or "")
        await self.platform.remove_friend(str(user["id"]), friend_id)
        return web.json_response({"ok": True})

    async def public_profile(self, request: web.Request) -> web.Response:
        peer = self._peer(request)
        if not await self.platform.allow_rate(f"public-profile:{peer}", 180, 60):
            raise PlatformError("RATE_LIMIT", "طلبات ملفات كثيرة؛ حاول لاحقًا", 429)
        target_id = str(request.match_info.get("user_id") or "").strip()
        if not re.fullmatch(r"[A-Za-z0-9_-]{12,32}", target_id):
            raise PlatformError("USER_NOT_FOUND", "المستخدم غير موجود", 404)
        viewer = await self._optional_user(request)
        profile = await self.platform.public_profile(target_id, str(viewer["id"]) if viewer else None)
        return web.json_response({"ok": True, "user": profile})

    async def reputation_give(self, request: web.Request) -> web.Response:
        user = await self._user(request)
        if not await self.platform.allow_rate(f"rep:{user['id']}", 12, 60):
            raise PlatformError("RATE_LIMIT", "محاولات كثيرة؛ حاول لاحقًا", 429)
        target_id = str(request.match_info.get("user_id") or "").strip()
        body = await self._body(request)
        source = str(body.get("source") or "profile")
        if source == "game":
            room_id = str(body.get("roomId") or "").strip()
            liked = bool(body.get("liked"))
            try:
                room = await self.room_store.get_room_state(room_id)
            except Exception:
                raise PlatformError("ROOM_NOT_FOUND", "تعذر التحقق من المباراة", 404)
            roster = list(room.get("roster") or [])
            giver_seat = next((int(p.get("seat")) for p in roster if p and str(p.get("accountId") or "") == str(user["id"])), None)
            target_seat = next((int(p.get("seat")) for p in roster if p and str(p.get("accountId") or "") == target_id), None)
            capacity = int(room.get("capacity") or len(roster) or 0)
            if giver_seat is None or target_seat is None or giver_seat == target_seat or not bool(room.get("begun")):
                raise PlatformError("RATING_NOT_ALLOWED", "هذا التقييم غير مرتبط بمباراة صالحة", 403)
            soccer = (room.get("settings") or {}).get("gameId") == "tablesoccer"
            giver_team = giver_seat // 2 if soccer else giver_seat % 2
            target_team = target_seat // 2 if soccer else target_seat % 2
            if capacity >= 4 and ((room.get("settings") or {}).get("gameId") != "crazy8" or (room.get("settings") or {}).get("seats") == 4) and giver_team == target_team:
                raise PlatformError("RATING_TEAMMATE", "التقييم بعد المباراة مخصص للخصم", 403)
            result = await self.platform.record_match_rating(str(user["id"]), target_id, room_id, liked)
            return web.json_response({"ok": True, **result})
        result = await self.platform.grant_reputation(str(user["id"]), target_id)
        return web.json_response({"ok": True, **result})

    async def report_user(self, request: web.Request) -> web.Response:
        user = await self._user(request)
        if not await self.platform.allow_rate(f"report:{user['id']}", 8, 3600):
            raise PlatformError("RATE_LIMIT", "وصلت للحد المؤقت للبلاغات؛ حاول لاحقًا", 429)
        target_id = str(request.match_info.get("user_id") or "").strip()
        body = await self._body(request)
        report = await self.platform.submit_report(
            str(user["id"]),
            target_id,
            message=str(body.get("message") or ""),
            room_id=str(body.get("roomId") or ""),
        )
        return web.json_response({"ok": True, "reportId": report["id"]})

    async def user_search(self, request: web.Request) -> web.Response:
        user = await self._user(request)
        q = request.query.get("q", "")
        results = await self.platform.search_users(q, str(user["id"]))
        return web.json_response({"ok": True, "users": results})

    async def admin_users(self, request: web.Request) -> web.Response:
        await self._admin(request)
        return web.json_response({"ok": True, "users": await self.platform.list_users()})

    async def admin_stats(self, request: web.Request) -> web.Response:
        await self._admin(request)
        users = await self.platform.list_users(500)
        rooms = await self.room_store.list_public_rooms(200)
        return web.json_response({
            "ok": True,
            "stats": {
                "users": len(users),
                "onlineUsers": sum(1 for u in users if u.get("online")),
                "rooms": len(rooms),
                "waitingRooms": sum(1 for r in rooms if not r.get("started")),
                "runningRooms": sum(1 for r in rooms if r.get("begun")),
            },
        })

    async def admin_reports(self, request: web.Request) -> web.Response:
        await self._admin(request)
        return web.json_response({"ok": True, "reports": await self.platform.list_reports(250)})

    async def admin_ban(self, request: web.Request) -> web.Response:
        admin = await self._admin(request)
        target_id = str(request.match_info.get("user_id") or "")
        if target_id == str(admin["id"]):
            raise PlatformError("CANNOT_BAN_SELF", "لا يمكنك حظر حسابك الإداري")
        body = await self._body(request)
        if not isinstance(body.get("banned"), bool):
            raise PlatformError("BAD_BAN_VALUE", "قيمة الحظر غير صالحة")
        target = await self.platform.get_user(target_id)
        if str(admin.get("role")) != "admin" and target and target.get("role") in {"admin", "moderator"}:
            raise PlatformError("ADMIN_REQUIRED", "لا تملك صلاحية حظر هذا الحساب", 403)
        user = await self.platform.set_banned(target_id, body["banned"])
        return web.json_response({"ok": True, "user": user})

    async def admin_role(self, request: web.Request) -> web.Response:
        admin = await self._admin(request)
        if str(admin.get("role")) != "admin":
            raise PlatformError("ADMIN_REQUIRED", "هذه العملية للمدير فقط", 403)
        target_id = str(request.match_info.get("user_id") or "")
        if target_id == str(admin["id"]):
            raise PlatformError("CANNOT_CHANGE_SELF", "لا تغيّر صلاحية حسابك الحالي")
        body = await self._body(request)
        user = await self.platform.set_role(target_id, str(body.get("role") or "user"))
        return web.json_response({"ok": True, "user": user})
