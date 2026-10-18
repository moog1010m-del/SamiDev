from __future__ import annotations

import asyncio
import json
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any
from games import GAMES, game_id, game_capacity

ROOM_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ROOM_TTL_SECONDS = 6 * 60 * 60
ROOM_WAIT_SECONDS = max(1, min(3600, int(os.getenv("SAMIDEV_ROOM_WAIT_SECONDS", "300"))))
TOKEN_TTL_SECONDS = ROOM_TTL_SECONDS
INVITE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,64}$")
MAX_HISTORY = 1200
CHAT_HISTORY_MAX = 30
CHAT_MAX_CHARS = 160
ROOM_RE = re.compile(r"^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{6}$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,64}$")


WAITING_LUA = """
local function waiting_expired(key)
  if redis.call('HGET', key, 'waitingExpired') == '1' then return true end
  local deadline = tonumber(redis.call('HGET', key, 'waitingExpiresAt') or '0')
  if deadline <= 0 then return false end
  if redis.call('HGET', key, 'started') == '1' or redis.call('HGET', key, 'begun') == '1' then return false end
  local t = redis.call('TIME')
  return tonumber(t[1])*1000 + math.floor(tonumber(t[2])/1000) >= deadline
end
"""


def normalize_room_id(v: Any) -> str:
    rid = str(v or "").strip().upper()
    if not ROOM_RE.fullmatch(rid):
        raise StoreError("BAD_ROOM_ID", "كود الغرفة غير صالح")
    return rid


def normalize_token(v: Any) -> str | None:
    if v is None or v == "":
        return None
    token = str(v).strip()
    if not TOKEN_RE.fullmatch(token):
        raise StoreError("BAD_TOKEN", "رمز إعادة الاتصال غير صالح")
    return token


def now_ms() -> int:
    return int(time.time() * 1000)


def sanitize_name(v: Any) -> str:
    s = str(v or "Player").strip() or "Player"
    return s[:24]


def clamp_int(v: Any, lo: int, hi: int, default: int) -> int:
    try:
        n = int(v)
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def sanitize_settings(raw: Any) -> dict[str, Any]:
    raw = raw if isinstance(raw, dict) else {}
    selected = game_id(raw)
    if selected not in GAMES:
        raise StoreError("UNKNOWN_GAME", "اللعبة غير مدعومة")
    if selected == "pool":
        mode = clamp_int(raw.get("gameType"), 0, 10, 0)
        if mode in (8, 9): raise StoreError("RETIRED_POOL_MODE", "تم إيقاف أنواع الهرم؛ اختر نوع بلياردو آخر")
        if mode == 10: mode = 0
        return {"gameId":"pool", "gameType":mode, "players":(0,1,2,0,1,2,3,0)[mode], "live":1, "break":clamp_int(raw.get("break"),0,1,0), "trickShots":0}
    if selected == "crazy8":
        return {"gameId": selected, "seats": clamp_int(raw.get("seats"), 0, 4, 2),
                "live": clamp_int(raw.get("live"), 0, 1, 1),
                "special": clamp_int(raw.get("special"), 0, 5, 0)}
    if selected == "tablesoccer":
        return {"gameId": selected, "players": clamp_int(raw.get("players"), 0, 1, 0),
                "live": clamp_int(raw.get("live"), 0, 1, 0),
                "goalsToWin": clamp_int(raw.get("goalsToWin"), 0, 2, 1),
                "passes": clamp_int(raw.get("passes"), 0, 2, 0)}
    requested_break = clamp_int(raw.get("break"), 0, 2, 0)
    settings: dict[str, int] = {
        "live": clamp_int(raw.get("live"), 0, 1, 1),
        "players": clamp_int(raw.get("players"), 0, 1, 0),
        "gamemode": clamp_int(raw.get("gamemode"), 0, 4, 0),
        "break": requested_break,
    }
    settings["gameId"] = selected
    if requested_break == 2:
        settings["break"] = secrets.randbelow(2)
        settings["_samidev_break_requested"] = 2
    return settings


def new_room_id() -> str:
    return "".join(secrets.choice(ROOM_ALPHABET) for _ in range(6))


def new_token() -> str:
    return secrets.token_urlsafe(24)


def new_invite_token() -> str:
    # Opaque one-time token suitable for web invite links.
    return secrets.token_urlsafe(18)


def normalize_invite_token(v: Any) -> str:
    token = str(v or "").strip()
    if not INVITE_TOKEN_RE.fullmatch(token):
        raise StoreError("BAD_INVITE", "رابط الدعوة غير صالح")
    return token


class StoreError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class MemPlayer:
    token: str
    name: str
    seat: int
    node_id: str
    conn_id: str
    connected: bool = True
    ready: bool = False
    disconnected_at: int | None = None
    connection_epoch: int = 1
    account_id: str | None = None


@dataclass
class MemRoom:
    room_id: str
    settings: dict[str, int]
    capacity: int
    community_id: str = "majlis"
    created_at: int = field(default_factory=now_ms)
    waiting_expires_at: int = 0
    waiting_expired: bool = False
    closed_reason: str = ""
    owner_seat: int = 0
    players: dict[int, MemPlayer] = field(default_factory=dict)
    started: bool = False
    begun: bool = False
    sequence: list[int] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    committed_moves: dict[str, dict[str, Any]] = field(default_factory=dict)
    chat: list[dict[str, Any]] = field(default_factory=list)
    move_count: int = 0
    snapshot: dict[str, Any] | None = None
    snapshot_move_count: int = -1
    snapshot_revision: int = -1
    snapshot_epoch: int = 0
    authority_shard: str | None = None
    authority_epoch: int = 0
    authority_revision: int = -1
    profile_result_claimed: bool = False
    begun_at: int = 0
    finished: bool = False
    spectator_nodes: dict[str, str] = field(default_factory=dict)
    expires_at: float = field(default_factory=lambda: time.monotonic() + ROOM_TTL_SECONDS)

    def __post_init__(self) -> None:
        if not self.waiting_expires_at: self.waiting_expires_at=self.created_at+ROOM_WAIT_SECONDS*1000
        self.sequence = [0] * self.capacity


class MemoryStore:
    """Single-node store used for local development and load testing.

    Production should use RedisStore so nodes can be added/removed horizontally.
    """

    distributed = False

    def __init__(self) -> None:
        self.rooms: dict[str, MemRoom] = {}
        self.tokens: dict[str, tuple[str, int]] = {}
        self.invites: dict[str, tuple[str, float]] = {}
        self.lock = asyncio.Lock()
        self.rate_windows: dict[str, tuple[int, float]] = {}

    def _roster(self, room: MemRoom, *, include_account_ids: bool = True) -> list[dict[str, Any]]:
        roster: list[dict[str, Any]] = []
        for seat in range(room.capacity):
            player = room.players.get(seat)
            item: dict[str, Any] = {
                "seat": seat,
                "name": player.name if player else None,
                "connected": bool(player and player.connected),
                "ready": bool(player and player.ready),
            }
            if include_account_ids:
                item["accountId"] = player.account_id if player else None
            roster.append(item)
        return roster

    def _waiting_expired(self, room: MemRoom) -> bool:
        return room.waiting_expired or (not room.started and not room.begun and now_ms() >= room.waiting_expires_at)

    def _room_payload(self, room: MemRoom) -> dict[str, Any]:
        return {
            "roomId": room.room_id,
            "createdAt": room.created_at, "begunAt":room.begun_at,
            "waitingExpiresAt": room.waiting_expires_at,
            "waitingExpired": self._waiting_expired(room),
            "ownerSeat": room.owner_seat,
            "communityId": room.community_id,
            "capacity": room.capacity,
            "settings": room.settings,
            "started": room.started,
            "begun": room.begun,
            "finished": room.finished,
            "roster": self._roster(room),
            "sequence": list(room.sequence),
            "moveCount": room.move_count,
        }

    async def create_room(self, name: str, settings: dict[str, int], node_id: str, conn_id: str, account_id: str | None = None, community_id: str = "majlis") -> dict[str, Any]:
        async with self.lock:
            for _ in range(20):
                rid = new_room_id()
                if rid not in self.rooms:
                    break
            else:
                raise StoreError("ROOM_ID_EXHAUSTED", "تعذر إنشاء كود غرفة")
            capacity = game_capacity(settings)
            token = new_token()
            room = MemRoom(rid, settings, capacity, community_id=str(community_id or "majlis")[:32])
            room.players[0] = MemPlayer(token, sanitize_name(name), 0, node_id, conn_id, account_id=account_id)
            self.rooms[rid] = room
            self.tokens[token] = (rid, 0)
            data = self._room_payload(room)
            data.update({"seat": 0, "token": token, "connectionEpoch": 1})
            return data

    async def join_room(self, room_id: str, name: str, token: str | None, node_id: str, conn_id: str, account_id: str | None = None) -> dict[str, Any]:
        room_id = normalize_room_id(room_id)
        token = normalize_token(token)
        async with self.lock:
            room = self.rooms.get(room_id)
            if not room:
                raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
            if self._waiting_expired(room):
                raise StoreError("ROOM_WAIT_EXPIRED", "انتهت مهلة انتظار اللاعبين")
            player: MemPlayer | None = None
            if token and token in self.tokens:
                mapped_room, seat = self.tokens[token]
                if mapped_room == room_id:
                    player = room.players.get(seat)
            if player is None:
                if account_id and any(p.account_id == account_id for p in room.players.values()):
                    raise StoreError("ACCOUNT_ALREADY_SEATED", "الحساب موجود في الغرفة؛ استخدم رمز إعادة الاتصال")
                if room.started:
                    raise StoreError("MATCH_STARTED", "المباراة بدأت بالفعل")
                seat = next((s for s in range(room.capacity) if s not in room.players), None)
                if seat is None:
                    raise StoreError("ROOM_FULL", "الغرفة ممتلئة")
                token = new_token()
                player = MemPlayer(token, sanitize_name(name), seat, node_id, conn_id, account_id=account_id)
                room.players[seat] = player
                self.tokens[token] = (room_id, seat)
            else:
                if (player.account_id or "") != (account_id or ""):
                    raise StoreError("RECONNECT_ACCOUNT_MISMATCH", "رمز إعادة الاتصال لا يخص هذا الحساب")
                replaced_node_id = player.node_id
                replaced_conn_id = player.conn_id
                player.connection_epoch += 1
                player.name = sanitize_name(name or player.name)
                player.node_id = node_id
                player.conn_id = conn_id
                player.connected = True
                player.ready = False
                player.disconnected_at = None
            was_started = room.started
            if len(room.players) == room.capacity:
                room.started = True
            room.expires_at = time.monotonic() + ROOM_TTL_SECONDS
            data = self._room_payload(room)
            data.update({
                "seat": player.seat, "token": player.token,
                "connectionEpoch": player.connection_epoch,
                "justStarted": bool(room.started and not was_started),
                "replacedNodeId": locals().get("replaced_node_id"),
                "replacedConnId": locals().get("replaced_conn_id"),
            })
            return data

    async def list_public_rooms(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(200, int(limit)))
        async with self.lock:
            rooms = sorted(self.rooms.values(), key=lambda r: r.created_at, reverse=True)[:limit]
            out: list[dict[str, Any]] = []
            for room in rooms:
                if room.finished or self._waiting_expired(room):
                    continue
                roster = self._roster(room, include_account_ids=False)
                occupied = sum(1 for p in room.players.values())
                out.append({
                    "roomId": room.room_id, "communityId": room.community_id, "capacity": room.capacity, "occupied": occupied,
                    "settings": dict(room.settings), "started": bool(room.started), "begun": bool(room.begun),
                    "createdAt": room.created_at, "begunAt":room.begun_at, "hostName": roster[room.owner_seat]["name"] if roster and room.owner_seat<len(roster) else None,
                    "roster": roster,
                })
            return out

    async def create_invite(self, room_id: str, seat: int, conn_id: str, connection_epoch: int, ttl_seconds: int) -> dict[str, Any]:
        room_id = normalize_room_id(room_id)
        async with self.lock:
            room = self.rooms.get(room_id)
            if not room:
                raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
            if self._waiting_expired(room):
                raise StoreError("ROOM_WAIT_EXPIRED", "انتهت مهلة انتظار اللاعبين")
            player = room.players.get(int(seat))
            if not player or not player.connected or player.conn_id != conn_id or int(player.connection_epoch) != int(connection_epoch):
                raise StoreError("STALE_CONNECTION", "تم استبدال هذا الاتصال باتصال أحدث")
            if room.started or len(room.players) >= room.capacity:
                raise StoreError("MATCH_STARTED", "لا يمكن إنشاء دعوة بعد اكتمال المباراة")
            token = new_invite_token()
            self.invites[token] = (room_id, time.monotonic() + max(30, int(ttl_seconds)))
            return {"inviteToken": token, "expiresIn": max(30, int(ttl_seconds))}

    async def join_invite(self, invite_token: str, name: str, node_id: str, conn_id: str, account_id: str | None = None) -> dict[str, Any]:
        invite_token = normalize_invite_token(invite_token)
        async with self.lock:
            entry = self.invites.get(invite_token)
            if not entry:
                raise StoreError("INVITE_INVALID", "الدعوة غير صالحة أو تم استخدامها")
            room_id, expires_at = entry
            if expires_at <= time.monotonic():
                self.invites.pop(invite_token, None)
                raise StoreError("INVITE_EXPIRED", "انتهت صلاحية الدعوة")
            room = self.rooms.get(room_id)
            if not room:
                self.invites.pop(invite_token, None)
                raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
            if self._waiting_expired(room): raise StoreError("ROOM_WAIT_EXPIRED", "انتهت مهلة انتظار اللاعبين")
            if account_id and any(p.account_id == account_id for p in room.players.values()):
                raise StoreError("ACCOUNT_ALREADY_SEATED", "الحساب موجود في الغرفة؛ استخدم رمز إعادة الاتصال")
            if room.started:
                raise StoreError("MATCH_STARTED", "المباراة بدأت بالفعل")
            seat = next((s for s in range(room.capacity) if s not in room.players), None)
            if seat is None:
                raise StoreError("ROOM_FULL", "الغرفة ممتلئة")
            token = new_token()
            player = MemPlayer(token, sanitize_name(name), seat, node_id, conn_id, account_id=account_id)
            room.players[seat] = player
            self.tokens[token] = (room_id, seat)
            self.invites.pop(invite_token, None)  # one-time, only after a successful join
            was_started = room.started
            if len(room.players) == room.capacity:
                room.started = True
            room.expires_at = time.monotonic() + ROOM_TTL_SECONDS
            data = self._room_payload(room)
            data.update({
                "seat": seat, "token": token, "connectionEpoch": 1,
                "justStarted": bool(room.started and not was_started),
            })
            return data

    async def get_room_state(self, room_id: str) -> dict[str, Any]:
        room = self.rooms.get(room_id)
        if not room:
            raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
        return self._room_payload(room)

    async def get_start(self, room_id: str, seat: int) -> dict[str, Any]:
        room = self.rooms.get(room_id)
        if not room:
            raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
        if self._waiting_expired(room): raise StoreError("ROOM_WAIT_EXPIRED", "انتهت مهلة انتظار اللاعبين")
        if not room.started:
            raise StoreError("MATCH_NOT_STARTED", "المباراة لم تبدأ")
        return {
            "roomId": room_id,
            "communityId": room.community_id,
            "seat": seat,
            "capacity": room.capacity,
            "settings": room.settings,
            "started": room.started,
            "begun": room.begun,
            "finished": room.finished,
            "roster": self._roster(room),
            "history": [e for e in room.history if int(e.get("moveIndex", -1)) >= room.snapshot_move_count] if room.snapshot is not None else list(room.history),
            "snapshot": room.snapshot,
            "snapshotMoveCount": room.snapshot_move_count,
            "moveCount": room.move_count,
            "sequence": list(room.sequence),
        }

    async def assert_connection(self, room_id: str, seat: int, conn_id: str, connection_epoch: int) -> None:
        async with self.lock:
            room = self.rooms.get(room_id)
            p = room.players.get(seat) if room else None
            if not p or not p.connected or p.conn_id != conn_id or p.connection_epoch != connection_epoch:
                raise StoreError("STALE_CONNECTION", "تم استبدال هذا الاتصال باتصال أحدث")

    async def get_connection_epochs(self, room_id: str) -> list[int]:
        room = self.rooms.get(room_id)
        if not room:
            raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
        return [room.players.get(i).connection_epoch if room.players.get(i) else 0 for i in range(room.capacity)]

    async def runtime_ready(self, room_id: str, seat: int, conn_id: str, connection_epoch: int) -> bool:
        async with self.lock:
            room = self.rooms.get(room_id)
            p = room.players.get(seat) if room else None
            if not p or not p.connected or p.conn_id != conn_id or p.connection_epoch != connection_epoch:
                raise StoreError("STALE_CONNECTION", "تم استبدال هذا الاتصال باتصال أحدث")
            p.ready = True
            if room.started and not room.begun and all(x.ready and x.connected for x in room.players.values()) and len(room.players) == room.capacity:
                room.begun = True
                room.begun_at = now_ms()
                return True
            return False

    async def append_move(self, room_id: str, seat: int, packet: dict[str, Any], conn_id: str | None = None, connection_epoch: int | None = None, *, authority_epoch: int | None = None, authority_shard: str | None = None) -> dict[str, Any]:
        async with self.lock:
            room = self.rooms.get(room_id)
            if not room or not room.started or not room.begun:
                raise StoreError("MATCH_NOT_READY", "المباراة لم تصبح جاهزة بعد")
            if conn_id is not None and connection_epoch is not None:
                p = room.players.get(seat)
                if not p or not p.connected or p.conn_id != conn_id or p.connection_epoch != connection_epoch:
                    raise StoreError("STALE_CONNECTION", "تم استبدال هذا الاتصال باتصال أحدث")
            if "__info" in packet:
                return {"seat": seat, "packet": packet, "moveIndex": room.move_count, "infoAck": True, "infoOnly": True}
            n = packet.get("n")
            move_id = packet.get("i")
            if not isinstance(n, int) or not isinstance(move_id, str):
                raise StoreError("BAD_MOVE", "حركة ناقصة")
            expected = room.sequence[seat]
            trusted = authority_epoch is not None
            commit_key = f'{authority_epoch}:{seat}:{n}'
            if trusted:
                if room.authority_epoch != authority_epoch or room.authority_shard != authority_shard:
                    raise StoreError('STALE_AUTHORITY', 'تم استبدال خادم المباراة')
                if commit_key in room.committed_moves:
                    return room.committed_moves[commit_key]
            if not trusted and n != expected:
                raise StoreError("DESYNC", json.dumps({"expected": expected, "actual": n, "moveCount": room.move_count}))
            # Only the internal gateway supplies this authority lease after GameHost
            # accepts a move. Timers/resync may already have advanced store sequence.
            room.sequence[seat] = max(expected, n + 1)
            entry = {"seat": seat, "packet": packet, "moveIndex": room.move_count}
            if trusted:
                room.committed_moves[commit_key] = entry
                if len(room.committed_moves) > MAX_HISTORY:
                    room.committed_moves.pop(next(iter(room.committed_moves)))
            room.move_count += 1
            room.history.append(entry)
            if len(room.history) > MAX_HISTORY:
                room.history = room.history[-MAX_HISTORY:]
            room.expires_at = time.monotonic() + ROOM_TTL_SECONDS
            return entry

    async def append_chat(self, room_id: str, seat: int, conn_id: str, connection_epoch: int, text: str, *, chat_bubble: str = "", sticker: dict | None = None) -> dict[str, Any]:
        async with self.lock:
            room = self.rooms.get(room_id)
            player = room.players.get(seat) if room else None
            if not player or not player.connected or player.conn_id != conn_id or player.connection_epoch != connection_epoch:
                raise StoreError("STALE_CONNECTION", "تم استبدال هذا الاتصال باتصال أحدث")
            message = {"id": secrets.token_urlsafe(9), "seat": int(seat), "text": str(text), "ts": now_ms(), "chatBubble": chat_bubble, **(sticker or {})}
            room.chat.append(message)
            if len(room.chat) > CHAT_HISTORY_MAX:
                room.chat = room.chat[-CHAT_HISTORY_MAX:]
            room.expires_at = time.monotonic() + ROOM_TTL_SECONDS
            return message

    async def chat_history(self, room_id: str) -> list[dict[str, Any]]:
        room = self.rooms.get(room_id)
        if not room:
            raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
        return list(room.chat[-CHAT_HISTORY_MAX:])

    async def set_snapshot(self, room_id: str, seat: int, state: dict[str, Any], move_count: int, revision: int = 0, *, authority_epoch: int | None = None, authority_shard: str | None = None) -> None:
        async with self.lock:
            room = self.rooms.get(room_id)
            if not room or not room.started:
                return
            epoch = room.authority_epoch if authority_epoch is None else authority_epoch
            if epoch != room.authority_epoch or (authority_shard is not None and authority_shard != room.authority_shard):
                return
            if move_count < room.snapshot_move_count or move_count > room.move_count:
                return
            if epoch == room.snapshot_epoch and move_count == room.snapshot_move_count and revision < room.snapshot_revision:
                return
            room.snapshot = state
            room.snapshot_move_count = move_count
            room.snapshot_revision = revision
            room.snapshot_epoch = epoch

    async def resync(self, room_id: str) -> dict[str, Any]:
        room = self.rooms.get(room_id)
        if not room:
            raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
        return {
            "snapshot": room.snapshot,
            "snapshotMoveCount": room.snapshot_move_count,
            "snapshotRevision": room.snapshot_revision,
            "history": [e for e in room.history if int(e.get("moveIndex", -1)) >= room.snapshot_move_count] if room.snapshot is not None else list(room.history),
            "moveCount": room.move_count,
            "sequence": list(room.sequence),
        }

    async def sync_sequence(self, room_id: str, sequence: list[int]) -> None:
        """Advance persisted per-seat sequence to the authoritative GameHost values.

        Server-generated auto moves (for example a missed-turn m:3) advance BaseLogic
        sequence without passing through append_move(). Never move a stored sequence
        backwards; delayed authority events are therefore harmless.
        """
        async with self.lock:
            room = self.rooms.get(room_id)
            if not room:
                return
            for seat, value in enumerate(sequence[: room.capacity]):
                if isinstance(value, int) and value > room.sequence[seat]:
                    room.sequence[seat] = value
            room.expires_at = time.monotonic() + ROOM_TTL_SECONDS

    async def claim_authority(self, room_id: str, preferred_shard: str, renew: bool = False) -> dict[str, Any]:
        async with self.lock:
            room = self.rooms.get(room_id)
            if not room:
                raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
            if self._waiting_expired(room):
                raise StoreError("ROOM_WAIT_EXPIRED", "انتهت مهلة انتظار اللاعبين")
            if room.authority_shard is None:
                room.authority_shard = preferred_shard
                room.authority_epoch = 1
                room.authority_revision = -1
            elif renew:
                room.authority_shard = preferred_shard
                room.authority_epoch += 1
                room.authority_revision = -1
            return {"shard": room.authority_shard, "epoch": room.authority_epoch, "revision": room.authority_revision}

    async def get_authority(self, room_id: str) -> dict[str, Any] | None:
        room = self.rooms.get(room_id)
        if not room or not room.authority_shard:
            return None
        return {"shard": room.authority_shard, "epoch": room.authority_epoch, "revision": room.authority_revision}

    async def accept_authority_event(self, room_id: str, shard: str, epoch: int, revision: int) -> bool:
        async with self.lock:
            room = self.rooms.get(room_id)
            if not room or room.authority_shard != shard or room.authority_epoch != epoch or revision <= room.authority_revision:
                return False
            room.authority_revision = revision
            return True

    async def account_ids_for_room(self, room_id: str) -> dict[int, str]:
        room = self.rooms.get(room_id)
        if not room:
            raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
        return {seat: str(player.account_id) for seat, player in room.players.items() if player.account_id}

    async def claim_profile_result(self, room_id: str) -> bool:
        async with self.lock:
            room = self.rooms.get(room_id)
            if not room or room.profile_result_claimed:
                return False
            room.profile_result_claimed = True
            return True

    async def allow_rate(self, key: str, limit: int, window_seconds: int) -> bool:
        if limit <= 0:
            return True
        async with self.lock:
            now = time.monotonic()
            count, expires = self.rate_windows.get(key, (0, now + window_seconds))
            if expires <= now:
                count, expires = 0, now + window_seconds
            count += 1
            self.rate_windows[key] = (count, expires)
            return count <= limit

    async def leave_room(self, room_id: str, seat: int, conn_id: str, connection_epoch: int, *, before_begin_only: bool = False) -> dict[str, Any]:
        async with self.lock:
            room = self.rooms.get(room_id)
            p = room.players.get(seat) if room else None
            if not p or not p.connected or p.conn_id != conn_id or p.connection_epoch != connection_epoch:
                raise StoreError("STALE_CONNECTION", "تم استبدال هذا الاتصال باتصال أحدث")
            if before_begin_only and room.begun: return {'roomDeleted':False,'seatFreed':False}
            # Explicit exit invalidates reconnect ownership. Before the authoritative
            # match begins, also free the seat so a replacement player may join.
            self.tokens.pop(p.token, None)
            if not room.begun:
                room.players.pop(seat, None)
                room.started = False
                if seat == room.owner_seat and room.players: room.owner_seat = min(room.players)
                room.sequence[seat] = 0
                if not room.players:
                    self.rooms.pop(room_id, None)
                    return {"roomDeleted": True, "seatFreed": True}
                room.expires_at = time.monotonic() + ROOM_TTL_SECONDS
                return {"roomDeleted": False, "seatFreed": True}
            p.connected = False
            p.ready = False
            p.disconnected_at = now_ms()
            return {"roomDeleted": False, "seatFreed": False}

    async def disconnect(self, room_id: str, seat: int, conn_id: str) -> None:
        async with self.lock:
            room = self.rooms.get(room_id)
            if not room:
                return
            p = room.players.get(seat)
            if p and p.conn_id == conn_id:
                p.connected = False
                p.ready = False
                p.disconnected_at = now_ms()

    async def mark_finished(self, room_id: str) -> None:
        async with self.lock:
            room = self.rooms.get(room_id)
            if not room:
                return
            room.finished = True
            room.expires_at = time.monotonic() + ROOM_TTL_SECONDS

    async def add_spectator(self, room_id: str, node_id: str, conn_id: str) -> None:
        room_id = normalize_room_id(room_id)
        async with self.lock:
            room = self.rooms.get(room_id)
            if not room:
                raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
            if self._waiting_expired(room):
                raise StoreError("ROOM_WAIT_EXPIRED", "انتهت مهلة انتظار اللاعبين")
            if room.finished:
                raise StoreError("MATCH_FINISHED", "المباراة انتهت")
            if not room.started:
                raise StoreError("MATCH_NOT_STARTED", "المباراة لم تبدأ")
            room.spectator_nodes[conn_id] = node_id
            room.expires_at = time.monotonic() + ROOM_TTL_SECONDS

    async def remove_spectator(self, room_id: str, conn_id: str) -> None:
        async with self.lock:
            room = self.rooms.get(room_id)
            if room:
                room.spectator_nodes.pop(conn_id, None)

    async def room_nodes(self, room_id: str) -> set[str]:
        room = self.rooms.get(room_id)
        if not room:
            return set()
        nodes = {p.node_id for p in room.players.values() if p.connected}
        nodes.update(room.spectator_nodes.values())
        return nodes

    async def manage_waiting_table(self, rid, seat, conn_id, epoch, action, target_seat=-1):
        if action not in {'close','kick'}: raise StoreError('BAD_TABLE_ACTION','إجراء غير مدعوم')
        async with self.lock:
            room = self.rooms.get(rid)
            player = room.players.get(seat) if room else None
            if not player or player.conn_id!=conn_id or player.connection_epoch!=epoch or not player.connected:
                raise StoreError('STALE_CONNECTION','الاتصال غير صالح')
            if room.begun or room.finished or self._waiting_expired(room):
                raise StoreError('TABLE_MANAGEMENT_CLOSED','إدارة الطاولة متاحة قبل اللعب فقط')
            if room.owner_seat!=seat: raise StoreError('TABLE_OWNER_REQUIRED','هذه العملية لمنشئ الطاولة فقط')
            if action=='close':
                room.waiting_expired=True;room.finished=True;room.closed_reason='TABLE_CLOSED'
                return {'roomId':rid,'createdAt':room.created_at,'reason':'TABLE_CLOSED'}
            if target_seat==seat: raise StoreError('CANNOT_KICK_OWNER','لا يمكن إخراج منشئ الطاولة')
            target=room.players.pop(target_seat,None)
            if not target:raise StoreError('NOT_IN_ROOM','المقعد فارغ')
            self.tokens.pop(target.token,None)
            room.started=False;room.sequence[target_seat]=0
            return {'roomId':rid,'createdAt':room.created_at,'reason':'TABLE_KICKED',
                'targetConnId':target.conn_id,'targetNodeId':target.node_id}

    async def waiting_closures(self, room_ids) -> list[dict[str, Any]]:
        async with self.lock:
            return [{"roomId":rid,"createdAt":self.rooms[rid].created_at,"reason":self.rooms[rid].closed_reason or "ROOM_WAIT_EXPIRED"} for rid in room_ids
                if rid in self.rooms and self._waiting_expired(self.rooms[rid])]

    async def expire_waiting_rooms(self, limit: int = 200) -> list[dict[str, Any]]:
        out = []
        async with self.lock:
            for room in self.rooms.values():
                if not room.waiting_expired and self._waiting_expired(room):
                    room.waiting_expired = True
                    room.finished = True
                    out.append({"roomId": room.room_id, "createdAt": room.created_at})
                    if len(out) >= limit: break
        return out

    async def sweep(self) -> None:
        async with self.lock:
            expired = [rid for rid, room in self.rooms.items() if room.expires_at <= time.monotonic()]
            for rid in expired:
                room = self.rooms.pop(rid)
                for p in room.players.values():
                    self.tokens.pop(p.token, None)
            now = time.monotonic()
            for token, (_, expires_at) in list(self.invites.items()):
                if expires_at <= now:
                    self.invites.pop(token, None)


class RedisStore:
    """Distributed production store.

    Room state lives in Redis, while WebSocket connections stay on gateway nodes.
    Each room has at most four players, so fan-out targets the small set of gateway
    node IDs that currently host those players instead of broadcasting globally.
    """

    distributed = True

    def __init__(self, url: str, prefix: str = "sd") -> None:
        try:
            import redis.asyncio as redis
        except ImportError as e:
            raise RuntimeError("Production Redis mode requires: pip install -r requirements.txt") from e
        self.redis_mod = redis
        self.r = redis.from_url(url, decode_responses=True, health_check_interval=20)
        self.prefix = prefix
        self.last_touch: dict[str, float] = {}

    def kroom(self, rid: str) -> str: return f"{self.prefix}:room:{rid}"
    def kplayers(self, rid: str) -> str: return f"{self.prefix}:room:{rid}:players"
    def kseq(self, rid: str) -> str: return f"{self.prefix}:room:{rid}:seq"
    def khistory(self, rid: str) -> str: return f"{self.prefix}:room:{rid}:history"
    def kready(self, rid: str) -> str: return f"{self.prefix}:room:{rid}:ready"
    def knodes(self, rid: str) -> str: return f"{self.prefix}:room:{rid}:nodes"
    def kspectators(self, rid: str) -> str: return f"{self.prefix}:room:{rid}:spectators"
    def ktoken(self, token: str) -> str: return f"{self.prefix}:token:{token}"
    def kinvite(self, token: str) -> str: return f"{self.prefix}:invite:{token}"
    def kchat(self, rid: str) -> str: return f"{self.prefix}:room:{rid}:chat"
    def kcommits(self, rid: str) -> str: return f"{self.prefix}:room:{rid}:commits"
    def kcommit_order(self, rid: str) -> str: return f"{self.prefix}:room:{rid}:commit-order"
    def node_channel(self, node_id: str) -> str: return f"{self.prefix}:node:{node_id}"
    def krate(self, key: str) -> str: return f"{self.prefix}:rate:{key}"
    def kwaiting(self) -> str: return f"{self.prefix}:rooms:waiting"
    def kroom_index(self) -> str: return f"{self.prefix}:rooms:index"

    async def ping(self) -> bool:
        return bool(await self.r.ping())

    async def _touch(self, rid: str) -> None:
        now = time.monotonic()
        if now - self.last_touch.get(rid, 0) < 30: return
        keys = [self.kroom(rid), self.kplayers(rid), self.kseq(rid), self.khistory(rid), self.kready(rid), self.knodes(rid), self.kspectators(rid), self.kchat(rid), self.kcommits(rid), self.kcommit_order(rid)]
        p = self.r.pipeline(transaction=False)
        for key in keys:
            p.expire(key, ROOM_TTL_SECONDS)
        await p.execute()
        if len(self.last_touch) >= 8192:
            self.last_touch.pop(next(iter(self.last_touch)))
        self.last_touch[rid] = now

    async def create_room(self, name: str, settings: dict[str, int], node_id: str, conn_id: str, account_id: str | None = None, community_id: str = "majlis") -> dict[str, Any]:
        capacity = game_capacity(settings)
        for _ in range(30):
            rid = new_room_id()
            token = new_token()
            player = {"token": token, "name": sanitize_name(name), "seat": 0, "nodeId": node_id, "connId": conn_id, "accountId": account_id, "connected": True, "ready": False, "disconnectedAt": None, "connectionEpoch": 1}
            script = """
            if redis.call('EXISTS', KEYS[1]) == 1 then return 0 end
            redis.call('DEL', KEYS[2], KEYS[3], KEYS[5], KEYS[6], KEYS[7], KEYS[8], KEYS[9], KEYS[10], KEYS[11])
            local t = redis.call('TIME')
            local clock = tonumber(t[1])*1000 + math.floor(tonumber(t[2])/1000)
            local deadline = clock + tonumber(ARGV[9])
            redis.call('ZADD', KEYS[12], deadline, ARGV[10])
            redis.call('HSET', KEYS[1], 'waitingExpiresAt', string.format('%.0f',deadline), 'waitingExpired', '0', 'ownerSeat', '0', 'capacity', ARGV[1], 'settings', ARGV[2], 'communityId', ARGV[8], 'started', '0', 'begun', '0', 'moveCount', '0', 'snapshotMoveCount', '-1', 'snapshotRevision', '-1', 'authorityShard', '', 'authorityEpoch', '0', 'authorityRevision', '-1', 'profileResultClaimed', '0', 'finished', '0', 'createdAt', string.format('%.0f',clock))
            redis.call('HSET', KEYS[2], '0', ARGV[4])
            for i=0,tonumber(ARGV[1])-1 do redis.call('HSET', KEYS[3], tostring(i), '0') end
            redis.call('SET', KEYS[4], ARGV[5], 'EX', ARGV[6])
            redis.call('SADD', KEYS[5], ARGV[7])
            redis.call('EXPIRE', KEYS[1], ARGV[6]); redis.call('EXPIRE', KEYS[2], ARGV[6]); redis.call('EXPIRE', KEYS[3], ARGV[6]); redis.call('EXPIRE', KEYS[5], ARGV[6])
            return 1
            """
            ok = await self.r.eval(script, 12, self.kroom(rid), self.kplayers(rid), self.kseq(rid), self.ktoken(token), self.knodes(rid), self.khistory(rid), self.kready(rid), self.kchat(rid), self.kspectators(rid), self.kcommits(rid), self.kcommit_order(rid), self.kwaiting(), str(capacity), json.dumps(settings, separators=(",", ":")), str(now_ms()), json.dumps(player, separators=(",", ":")), f"{rid}:0", str(TOKEN_TTL_SECONDS), node_id, str(community_id or "majlis")[:32], str(ROOM_WAIT_SECONDS * 1000), rid)
            if int(ok) == 1:
                self.last_touch.pop(rid, None)
                await self.r.zadd(self.kroom_index(), {rid: now_ms()})
                data = await self.get_room_state(rid)
                data.update({"seat": 0, "token": token, "connectionEpoch": 1})
                return data
        raise StoreError("ROOM_ID_EXHAUSTED", "تعذر إنشاء كود غرفة")

    async def join_room(self, room_id: str, name: str, token: str | None, node_id: str, conn_id: str, account_id: str | None = None) -> dict[str, Any]:
        rid = normalize_room_id(room_id)
        token = normalize_token(token)
        if not await self.r.exists(self.kroom(rid)):
            raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
        if token:
            mapped = await self.r.get(self.ktoken(token))
            if mapped:
                mrid, sseat = mapped.rsplit(":", 1)
                if mrid == rid:
                    seat = int(sseat)
                    script = WAITING_LUA + """
                    if waiting_expired(KEYS[4]) then return {-18, '', '', 0} end
                    local raw = redis.call('HGET', KEYS[1], ARGV[1])
                    if not raw then return {0, '', '', 0} end
                    local p = cjson.decode(raw)
                    local owner = p['accountId']
                    if owner == nil or owner == cjson.null then owner = '' end
                    if owner ~= ARGV[5] then return {-16, '', '', 0} end
                    if p['token'] ~= ARGV[6] then return {0, '', '', 0} end
                    local oldNode = p['nodeId'] or ''
                    local oldConn = p['connId'] or ''
                    local epoch = tonumber(p['connectionEpoch'] or 1) + 1
                    p['connectionEpoch'] = epoch
                    p['name'] = ARGV[2]
                    p['nodeId'] = ARGV[3]
                    p['connId'] = ARGV[4]
                    p['connected'] = true
                    p['ready'] = false
                    p['disconnectedAt'] = cjson.null
                    redis.call('HSET', KEYS[1], ARGV[1], cjson.encode(p))
                    redis.call('SADD', KEYS[2], ARGV[3])
                    redis.call('SREM', KEYS[3], ARGV[1])
                    return {1, oldNode, oldConn, epoch}
                    """
                    ret = await self.r.eval(
                        script, 4, self.kplayers(rid), self.knodes(rid), self.kready(rid), self.kroom(rid),
                        str(seat), sanitize_name(name), node_id, conn_id, str(account_id or ""), token,
                    )
                    if int(ret[0]) == -18: raise StoreError("ROOM_WAIT_EXPIRED", "انتهت مهلة انتظار اللاعبين")
                    if int(ret[0]) == -16:
                        raise StoreError("RECONNECT_ACCOUNT_MISMATCH", "رمز إعادة الاتصال لا يخص هذا الحساب")
                    if int(ret[0]) == 1:
                        await self._touch(rid)
                        data = await self.get_room_state(rid)
                        data.update({
                            "seat": seat, "token": token, "connectionEpoch": int(ret[3]),
                            "justStarted": False, "replacedNodeId": str(ret[1] or ""),
                            "replacedConnId": str(ret[2] or ""),
                        })
                        return data

        token = new_token()
        capacity = int(await self.r.hget(self.kroom(rid), "capacity") or 0)
        player_tpl = {"token": token, "name": sanitize_name(name), "seat": -1, "nodeId": node_id, "connId": conn_id, "accountId": account_id, "connected": True, "ready": False, "disconnectedAt": None, "connectionEpoch": 1}
        script = WAITING_LUA + """
        if redis.call('EXISTS', KEYS[1]) == 0 then return {-10} end
        if waiting_expired(KEYS[1]) then return {-18} end
        local p = cjson.decode(ARGV[1])
        if p['accountId'] ~= nil and p['accountId'] ~= cjson.null and p['accountId'] ~= '' then
          for _,raw in ipairs(redis.call('HVALS', KEYS[2])) do
            if cjson.decode(raw)['accountId'] == p['accountId'] then return {-17} end
          end
        end
        if redis.call('HGET', KEYS[1], 'started') == '1' then return {-11} end
        local cap = tonumber(redis.call('HGET', KEYS[1], 'capacity'))
        local seat = -1
        for i=0,cap-1 do
          local existing = redis.call('HGET', KEYS[2], tostring(i))
          if existing then
          elseif seat < 0 then
            seat = i
          end
        end
        if seat < 0 then return {-12} end
        p['seat'] = seat
        redis.call('HSET', KEYS[2], tostring(seat), cjson.encode(p))
        redis.call('SET', KEYS[3], ARGV[2] .. ':' .. tostring(seat), 'EX', ARGV[3])
        redis.call('SADD', KEYS[4], ARGV[4])
        local count = redis.call('HLEN', KEYS[2])
        if count >= cap then redis.call('HSET', KEYS[1], 'started', '1') end
        redis.call('EXPIRE', KEYS[1], ARGV[3]); redis.call('EXPIRE', KEYS[2], ARGV[3]); redis.call('EXPIRE', KEYS[4], ARGV[3])
        return {seat, count >= cap and 1 or 0}
        """
        ret = await self.r.eval(script, 4, self.kroom(rid), self.kplayers(rid), self.ktoken(token), self.knodes(rid), json.dumps(player_tpl, separators=(",", ":")), rid, str(TOKEN_TTL_SECONDS), node_id)
        code = int(ret[0])
        if code == -18: raise StoreError("ROOM_WAIT_EXPIRED", "انتهت مهلة انتظار اللاعبين")
        if code == -10: raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
        if code == -11: raise StoreError("MATCH_STARTED", "المباراة بدأت بالفعل")
        if code == -12: raise StoreError("ROOM_FULL", "الغرفة ممتلئة")
        if code == -17: raise StoreError("ACCOUNT_ALREADY_SEATED", "الحساب موجود في الغرفة؛ استخدم رمز إعادة الاتصال")
        seat = code
        just_started = bool(int(ret[1]))
        await self._touch(rid)
        data = await self.get_room_state(rid)
        data.update({"seat": seat, "token": token, "connectionEpoch": 1, "justStarted": just_started})
        return data

    async def list_public_rooms(self, limit: int = 100) -> list[dict[str, Any]]:
        limit = max(1, min(200, int(limit)))
        rids = list(await self.r.zrevrange(self.kroom_index(), 0, limit * 2 - 1))
        if not rids:
            return []
        p = self.r.pipeline(transaction=False)
        for rid in rids:
            p.hgetall(self.kroom(rid))
            p.hgetall(self.kplayers(rid))
        p.time()
        raw = await p.execute()
        clock = raw.pop()
        clock_ms = clock[0]*1000+clock[1]//1000
        out: list[dict[str, Any]] = []
        stale: list[str] = []
        for i, rid in enumerate(rids):
            room = raw[i * 2] or {}
            players = raw[i * 2 + 1] or {}
            if not room:
                stale.append(rid)
                continue
            deadline = int(room.get("waitingExpiresAt") or 0)
            if room.get("finished") == "1" or (not room.get("started") == "1" and deadline > 0 and clock_ms >= deadline):
                stale.append(rid)
                continue
            try:
                settings = json.loads(room.get("settings") or "{}")
            except Exception:
                settings = {}
            capacity = int(room.get("capacity") or 0)
            roster: list[dict[str, Any]] = []
            for seat in range(capacity):
                value = players.get(str(seat))
                player = None
                if value:
                    try: player = json.loads(value)
                    except Exception: player = None
                roster.append({
                    "seat": seat,
                    "name": player.get("name") if isinstance(player, dict) else None,
                    "connected": bool(player and player.get("connected")),
                    "ready": bool(player and player.get("ready")),
                })
            out.append({
                "roomId": rid, "communityId": str(room.get("communityId") or "majlis"), "capacity": capacity, "occupied": len(players), "settings": settings,
                "started": room.get("started") == "1", "begun": room.get("begun") == "1",
                "createdAt": int(room.get("createdAt") or 0),
                "ownerSeat":int(room.get("ownerSeat") or 0), "hostName": roster[int(room.get("ownerSeat") or 0)]["name"] if roster and int(room.get("ownerSeat") or 0)<len(roster) else None, "roster": roster,
            })
            if len(out) >= limit:
                break
        if stale:
            await self.r.zrem(self.kroom_index(), *stale)
        return out

    async def create_invite(self, rid: str, seat: int, conn_id: str, connection_epoch: int, ttl_seconds: int) -> dict[str, Any]:
        rid = normalize_room_id(rid)
        ttl = max(30, int(ttl_seconds))
        token = new_invite_token()
        script = WAITING_LUA + """
        if waiting_expired(KEYS[1]) then return -18 end
        if redis.call('EXISTS', KEYS[1]) == 0 then return -10 end
        local raw = redis.call('HGET', KEYS[2], ARGV[1]); if not raw then return -11 end
        local p = cjson.decode(raw)
        if p['connected'] ~= true or p['connId'] ~= ARGV[2] or tonumber(p['connectionEpoch'] or 1) ~= tonumber(ARGV[3]) then return -12 end
        if redis.call('HGET', KEYS[1], 'started') == '1' then return -13 end
        local cap = tonumber(redis.call('HGET', KEYS[1], 'capacity') or '0')
        if redis.call('HLEN', KEYS[2]) >= cap then return -14 end
        redis.call('SET', KEYS[3], ARGV[4], 'EX', ARGV[5])
        return 1
        """
        code = int(await self.r.eval(script, 3, self.kroom(rid), self.kplayers(rid), self.kinvite(token), str(seat), conn_id, str(connection_epoch), rid, str(ttl)))
        if code == -18: raise StoreError("ROOM_WAIT_EXPIRED", "انتهت مهلة انتظار اللاعبين")
        if code == -10: raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
        if code == -12: raise StoreError("STALE_CONNECTION", "تم استبدال هذا الاتصال باتصال أحدث")
        if code in (-13, -14): raise StoreError("MATCH_STARTED", "لا يمكن إنشاء دعوة بعد اكتمال المباراة")
        if code < 0: raise StoreError("NOT_IN_ROOM", "اللاعب غير موجود في غرفة")
        return {"inviteToken": token, "expiresIn": ttl}

    async def join_invite(self, invite_token: str, name: str, node_id: str, conn_id: str, account_id: str | None = None) -> dict[str, Any]:
        invite_token = normalize_invite_token(invite_token)
        invite_key = self.kinvite(invite_token)
        rid = await self.r.get(invite_key)
        if not rid:
            raise StoreError("INVITE_INVALID", "الدعوة غير صالحة أو انتهت أو تم استخدامها")
        rid = normalize_room_id(rid)
        player_token = new_token()
        player_tpl = {"token": player_token, "name": sanitize_name(name), "seat": -1, "nodeId": node_id, "connId": conn_id, "accountId": account_id, "connected": True, "ready": False, "disconnectedAt": None, "connectionEpoch": 1}
        script = WAITING_LUA + """
        if redis.call('GET', KEYS[1]) ~= ARGV[1] then return {-15} end
        if waiting_expired(KEYS[2]) then return {-18} end
        if redis.call('EXISTS', KEYS[2]) == 0 then return {-10} end
        local p = cjson.decode(ARGV[2])
        if p['accountId'] ~= nil and p['accountId'] ~= cjson.null and p['accountId'] ~= '' then
          for _,raw in ipairs(redis.call('HVALS', KEYS[3])) do
            if cjson.decode(raw)['accountId'] == p['accountId'] then return {-17} end
          end
        end
        if redis.call('HGET', KEYS[2], 'started') == '1' then return {-11} end
        local cap = tonumber(redis.call('HGET', KEYS[2], 'capacity'))
        local seat = -1
        for i=0,cap-1 do
          local existing = redis.call('HGET', KEYS[3], tostring(i))
          if existing then
          elseif seat < 0 then
            seat = i
          end
        end
        if seat < 0 then return {-12} end
        p['seat'] = seat
        redis.call('HSET', KEYS[3], tostring(seat), cjson.encode(p))
        redis.call('SET', KEYS[5], ARGV[1] .. ':' .. tostring(seat), 'EX', ARGV[3])
        redis.call('SADD', KEYS[6], ARGV[4])
        redis.call('DEL', KEYS[1])
        local count = redis.call('HLEN', KEYS[3])
        if count >= cap then redis.call('HSET', KEYS[2], 'started', '1') end
        redis.call('EXPIRE', KEYS[2], ARGV[3]); redis.call('EXPIRE', KEYS[3], ARGV[3]); redis.call('EXPIRE', KEYS[4], ARGV[3]); redis.call('EXPIRE', KEYS[6], ARGV[3])
        return {seat, count >= cap and 1 or 0}
        """
        ret = await self.r.eval(script, 6, invite_key, self.kroom(rid), self.kplayers(rid), self.kseq(rid), self.ktoken(player_token), self.knodes(rid), rid, json.dumps(player_tpl, separators=(",", ":")), str(TOKEN_TTL_SECONDS), node_id)
        code = int(ret[0])
        if code == -18: raise StoreError("ROOM_WAIT_EXPIRED", "انتهت مهلة انتظار اللاعبين")
        if code == -15: raise StoreError("INVITE_INVALID", "الدعوة غير صالحة أو تم استخدامها")
        if code == -10: raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
        if code == -11: raise StoreError("MATCH_STARTED", "المباراة بدأت بالفعل")
        if code == -12: raise StoreError("ROOM_FULL", "الغرفة ممتلئة")
        if code == -17: raise StoreError("ACCOUNT_ALREADY_SEATED", "الحساب موجود في الغرفة؛ استخدم رمز إعادة الاتصال")
        await self._touch(rid)
        data = await self.get_room_state(rid)
        data.update({"seat": code, "token": player_token, "connectionEpoch": 1, "justStarted": bool(int(ret[1]))})
        return data

    async def get_room_state(self, rid: str) -> dict[str, Any]:
        fields = ('capacity','settings','createdAt','begunAt','communityId','started','begun','finished','moveCount','waitingExpiresAt','waitingExpired','ownerSeat')
        pipe = self.r.pipeline(transaction=False)
        pipe.hmget(self.kroom(rid), *fields)
        pipe.hgetall(self.kplayers(rid))
        pipe.hgetall(self.kseq(rid))
        pipe.time()
        values, raw_players, seq_raw, clock = await pipe.execute()
        meta = dict(zip(fields, values))
        if not meta['capacity']:
            raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
        capacity = int(meta["capacity"])
        roster: list[dict[str, Any]] = []
        for seat in range(capacity):
            raw = raw_players.get(str(seat))
            p = json.loads(raw) if raw else None
            roster.append({
                "seat": seat,
                "name": p.get("name") if p else None,
                "accountId": p.get("accountId") if p else None,
                "connected": bool(p and p.get("connected")),
                "ready": bool(p and p.get("ready")),
            })
        expired = meta.get("waitingExpired") == "1" or (meta.get("started") != "1" and meta.get("begun") != "1" and int(meta.get("waitingExpiresAt") or 0) > 0 and clock[0]*1000+clock[1]//1000 >= int(meta["waitingExpiresAt"]))
        return {
            "waitingExpiresAt": int(meta.get("waitingExpiresAt") or 0),
            "waitingExpired": expired,
            "ownerSeat": int(meta.get("ownerSeat") or 0),
            "roomId": rid,
            "createdAt": int(meta.get("createdAt") or 0), "begunAt":int(meta.get("begunAt") or 0),
            "communityId": str(meta.get("communityId") or "majlis"),
            "capacity": capacity,
            "settings": json.loads(meta["settings"]),
            "started": meta.get("started") == "1",
            "begun": meta.get("begun") == "1",
            "finished": meta.get("finished") == "1",
            "roster": roster,
            "sequence": [int(seq_raw.get(str(i), 0)) for i in range(capacity)],
            "moveCount": int(meta.get("moveCount", 0)),
        }

    async def get_start(self, rid: str, seat: int) -> dict[str, Any]:
        state = await self.get_room_state(rid)
        if state.get("waitingExpired"): raise StoreError("ROOM_WAIT_EXPIRED", "انتهت مهلة انتظار اللاعبين")
        if not state["started"]:
            raise StoreError("MATCH_NOT_STARTED", "المباراة لم تبدأ")
        meta = await self.r.hmget(self.kroom(rid), "snapshot", "snapshotMoveCount", "moveCount")
        snapshot_raw, snapshot_count_raw, move_count_raw = meta
        snapshot = json.loads(snapshot_raw) if snapshot_raw else None
        snapshot_count = int(snapshot_count_raw or -1)
        all_history = [json.loads(x) for x in await self.r.lrange(self.khistory(rid), 0, -1)]
        history = all_history if snapshot is None else [e for e in all_history if int(e.get("moveIndex", -1)) >= snapshot_count]
        state.update({"seat": seat, "history": history, "snapshot": snapshot, "snapshotMoveCount": snapshot_count, "moveCount": int(move_count_raw or 0)})
        return state

    async def assert_connection(self, rid: str, seat: int, conn_id: str, connection_epoch: int) -> None:
        raw = await self.r.hget(self.kplayers(rid), str(seat))
        p = json.loads(raw) if raw else None
        if not p or not p.get("connected") or p.get("connId") != conn_id or int(p.get("connectionEpoch", 1)) != int(connection_epoch):
            raise StoreError("STALE_CONNECTION", "تم استبدال هذا الاتصال باتصال أحدث")

    async def get_connection_epochs(self, rid: str) -> list[int]:
        state = await self.get_room_state(rid)
        raw_players = await self.r.hgetall(self.kplayers(rid))
        out = []
        for seat in range(int(state["capacity"])):
            raw = raw_players.get(str(seat))
            p = json.loads(raw) if raw else None
            out.append(int(p.get("connectionEpoch", 1)) if p else 0)
        return out

    async def runtime_ready(self, rid: str, seat: int, conn_id: str, connection_epoch: int) -> bool:
        script = WAITING_LUA + """
        if waiting_expired(KEYS[1]) then return -18 end
        if redis.call('EXISTS', KEYS[1]) == 0 then return -10 end
        local raw = redis.call('HGET', KEYS[2], ARGV[1]); if not raw then return -11 end
        local p = cjson.decode(raw)
        if p['connected'] ~= true or p['connId'] ~= ARGV[2] or tonumber(p['connectionEpoch'] or 1) ~= tonumber(ARGV[3]) then return -12 end
        p['ready'] = true; redis.call('HSET', KEYS[2], ARGV[1], cjson.encode(p))
        redis.call('SADD', KEYS[3], ARGV[1])
        local cap = tonumber(redis.call('HGET', KEYS[1], 'capacity'))
        if redis.call('HGET', KEYS[1], 'started') == '1' and redis.call('HGET', KEYS[1], 'begun') ~= '1' and redis.call('SCARD', KEYS[3]) >= cap then
          local t=redis.call('TIME'); redis.call('HSET', KEYS[1], 'begun', '1', 'begunAt', string.format('%.0f',tonumber(t[1])*1000+math.floor(tonumber(t[2])/1000))); return 1
        end
        return 0
        """
        ret = int(await self.r.eval(script, 3, self.kroom(rid), self.kplayers(rid), self.kready(rid), str(seat), conn_id, str(connection_epoch)))
        if ret == -18: raise StoreError("ROOM_WAIT_EXPIRED", "انتهت مهلة انتظار اللاعبين")
        if ret == -12:
            raise StoreError("STALE_CONNECTION", "تم استبدال هذا الاتصال باتصال أحدث")
        if ret < 0:
            raise StoreError("NOT_IN_ROOM", "اللاعب غير موجود في غرفة")
        return ret == 1

    async def append_move(self, rid: str, seat: int, packet: dict[str, Any], conn_id: str | None = None, connection_epoch: int | None = None, *, authority_epoch: int | None = None, authority_shard: str | None = None) -> dict[str, Any]:
        if conn_id is not None and connection_epoch is not None:
            await self.assert_connection(rid, seat, conn_id, connection_epoch)
        if "__info" in packet:
            begun, move_count = await self.r.hmget(self.kroom(rid), 'begun', 'moveCount')
            if begun != '1': raise StoreError('MATCH_NOT_READY', 'المباراة لم تصبح جاهزة بعد')
            return {"seat": seat, "packet": packet, "moveIndex": int(move_count or 0), "infoAck": True, "infoOnly": True}
        n = packet.get("n"); move_id = packet.get("i")
        if not isinstance(n, int) or not isinstance(move_id, str):
            raise StoreError("BAD_MOVE", "حركة ناقصة")
        entry_base = {"seat": seat, "packet": packet}
        script = """
        if redis.call('EXISTS', KEYS[1]) == 0 or redis.call('HGET', KEYS[1], 'started') ~= '1' or redis.call('HGET', KEYS[1], 'begun') ~= '1' then return {-20,0,0} end
        local expected = tonumber(redis.call('HGET', KEYS[2], ARGV[1]) or '0')
        local actual = tonumber(ARGV[2])
        local mc = tonumber(redis.call('HGET', KEYS[1], 'moveCount') or '0')
        local trusted = ARGV[5] ~= ''
        local commitKey = ARGV[5] .. ':' .. ARGV[1] .. ':' .. ARGV[2]
        if trusted then
          if redis.call('HGET', KEYS[1], 'authorityEpoch') ~= ARGV[5] or redis.call('HGET', KEYS[1], 'authorityShard') ~= ARGV[6] then return {-22,0,0} end
          local previous = redis.call('HGET', KEYS[4], commitKey)
          if previous then return {tonumber(previous), expected, mc} end
        elseif expected ~= actual then return {-21, expected, mc} end
        redis.call('HSET', KEYS[2], ARGV[1], math.max(expected, actual + 1))
        local entry = cjson.decode(ARGV[3]); entry['moveIndex'] = mc
        redis.call('RPUSH', KEYS[3], cjson.encode(entry)); redis.call('LTRIM', KEYS[3], -tonumber(ARGV[4]), -1)
        if trusted then
          redis.call('HSET', KEYS[4], commitKey, mc)
          redis.call('RPUSH', KEYS[5], commitKey)
          redis.call('EXPIRE', KEYS[4], ARGV[7]); redis.call('EXPIRE', KEYS[5], ARGV[7])
          if redis.call('LLEN', KEYS[5]) > tonumber(ARGV[4]) then
            redis.call('HDEL', KEYS[4], redis.call('LPOP', KEYS[5]))
          end
        end
        redis.call('HINCRBY', KEYS[1], 'moveCount', 1)
        return {mc, expected + 1, mc + 1}
        """
        ret = await self.r.eval(script, 5, self.kroom(rid), self.kseq(rid), self.khistory(rid), self.kcommits(rid), self.kcommit_order(rid), str(seat), str(n), json.dumps(entry_base, separators=(",", ":")), str(MAX_HISTORY), str(authority_epoch) if authority_epoch is not None else '', authority_shard or '', str(ROOM_TTL_SECONDS))
        code = int(ret[0])
        if code == -20: raise StoreError("MATCH_NOT_READY", "المباراة لم تصبح جاهزة بعد")
        if code == -21: raise StoreError("DESYNC", json.dumps({"expected": int(ret[1]), "actual": n, "moveCount": int(ret[2])}))
        if code == -22: raise StoreError('STALE_AUTHORITY', 'تم استبدال خادم المباراة')
        await self._touch(rid)
        return {"seat": seat, "packet": packet, "moveIndex": code}

    async def append_chat(self, rid: str, seat: int, conn_id: str, connection_epoch: int, text: str, *, chat_bubble: str = "", sticker: dict | None = None) -> dict[str, Any]:
        message = {"id": secrets.token_urlsafe(9), "seat": int(seat), "text": str(text), "ts": now_ms(), "chatBubble": chat_bubble, **(sticker or {})}
        script = """
        if redis.call('EXISTS', KEYS[1]) == 0 then return -10 end
        local raw = redis.call('HGET', KEYS[2], ARGV[1]); if not raw then return -11 end
        local p = cjson.decode(raw)
        if p['connected'] ~= true or p['connId'] ~= ARGV[2] or tonumber(p['connectionEpoch'] or 1) ~= tonumber(ARGV[3]) then return -12 end
        redis.call('RPUSH', KEYS[3], ARGV[4])
        redis.call('LTRIM', KEYS[3], -tonumber(ARGV[5]), -1)
        redis.call('EXPIRE', KEYS[3], ARGV[6])
        return 1
        """
        code = int(await self.r.eval(script, 3, self.kroom(rid), self.kplayers(rid), self.kchat(rid), str(seat), conn_id, str(connection_epoch), json.dumps(message, ensure_ascii=False, separators=(",", ":")), str(CHAT_HISTORY_MAX), str(ROOM_TTL_SECONDS)))
        if code == -12:
            raise StoreError("STALE_CONNECTION", "تم استبدال هذا الاتصال باتصال أحدث")
        if code < 0:
            raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
        await self._touch(rid)
        return message

    async def chat_history(self, rid: str) -> list[dict[str, Any]]:
        if not await self.r.exists(self.kroom(rid)):
            raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
        raw = await self.r.lrange(self.kchat(rid), -CHAT_HISTORY_MAX, -1)
        out: list[dict[str, Any]] = []
        for item in raw:
            try:
                value = json.loads(item)
                if isinstance(value, dict):
                    out.append(value)
            except Exception:
                continue
        return out

    async def set_snapshot(self, rid: str, seat: int, state: dict[str, Any], move_count: int, revision: int = 0, *, authority_epoch: int | None = None, authority_shard: str | None = None) -> None:
        script = """
        if redis.call('EXISTS', KEYS[1]) == 0 or redis.call('HGET', KEYS[1], 'started') ~= '1' then return 0 end
        local liveEpoch = tonumber(redis.call('HGET', KEYS[1], 'authorityEpoch') or '0')
        local incomingEpoch = liveEpoch
        if ARGV[4] ~= '' then incomingEpoch = tonumber(ARGV[4]) end
        if incomingEpoch ~= liveEpoch then return 0 end
        if ARGV[5] ~= '' and redis.call('HGET', KEYS[1], 'authorityShard') ~= ARGV[5] then return 0 end
        local currentEpoch = tonumber(redis.call('HGET', KEYS[1], 'snapshotEpoch') or '0')
        local current = tonumber(redis.call('HGET', KEYS[1], 'snapshotMoveCount') or '-1')
        local currentRevision = tonumber(redis.call('HGET', KEYS[1], 'snapshotRevision') or '-1')
        local total = tonumber(redis.call('HGET', KEYS[1], 'moveCount') or '0')
        local incoming = tonumber(ARGV[1])
        local incomingRevision = tonumber(ARGV[3])
        if incoming < current or incoming > total then return 0 end
        if incomingEpoch == currentEpoch and incoming == current and incomingRevision < currentRevision then return 0 end
        redis.call('HSET', KEYS[1], 'snapshot', ARGV[2], 'snapshotMoveCount', incoming, 'snapshotRevision', incomingRevision, 'snapshotEpoch', incomingEpoch)
        return 1
        """
        await self.r.eval(script, 1, self.kroom(rid), str(move_count), json.dumps(state, separators=(",", ":")), str(revision), str(authority_epoch) if authority_epoch is not None else '', authority_shard or '')

    async def resync(self, rid: str) -> dict[str, Any]:
        state = await self.get_start(rid, 0)
        revision_raw = await self.r.hget(self.kroom(rid), "snapshotRevision")
        state["snapshotRevision"] = int(revision_raw or -1)
        return {k: state[k] for k in ("snapshot", "snapshotMoveCount", "snapshotRevision", "history", "moveCount", "sequence")}

    async def sync_sequence(self, rid: str, sequence: list[int]) -> None:
        script = """
        if redis.call('EXISTS', KEYS[1]) == 0 then return 0 end
        local seq = cjson.decode(ARGV[1])
        for i=1,#seq do
          local field = tostring(i-1)
          local current = tonumber(redis.call('HGET', KEYS[1], field) or '0')
          local authoritative = tonumber(seq[i]) or current
          if authoritative > current then redis.call('HSET', KEYS[1], field, authoritative) end
        end
        return 1
        """
        await self.r.eval(script, 1, self.kseq(rid), json.dumps(sequence, separators=(",", ":")))
        await self._touch(rid)

    async def claim_authority(self, rid: str, preferred_shard: str, renew: bool = False) -> dict[str, Any]:
        script = """
        if redis.call('EXISTS', KEYS[1]) == 0 then return {-1, '', 0, -1} end
        local shard = redis.call('HGET', KEYS[1], 'authorityShard') or ''
        local epoch = tonumber(redis.call('HGET', KEYS[1], 'authorityEpoch') or '0')
        if shard == '' then
          shard = ARGV[1]; epoch = 1
          redis.call('HSET', KEYS[1], 'authorityShard', shard, 'authorityEpoch', epoch, 'authorityRevision', '-1')
        elseif ARGV[2] == '1' then
          shard = ARGV[1]; epoch = epoch + 1
          redis.call('HSET', KEYS[1], 'authorityShard', shard, 'authorityEpoch', epoch, 'authorityRevision', '-1')
        end
        local revision = tonumber(redis.call('HGET', KEYS[1], 'authorityRevision') or '-1')
        return {1, shard, epoch, revision}
        """
        ret = await self.r.eval(script, 1, self.kroom(rid), preferred_shard, "1" if renew else "0")
        if int(ret[0]) < 0:
            raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
        return {"shard": str(ret[1]), "epoch": int(ret[2]), "revision": int(ret[3])}

    async def get_authority(self, rid: str) -> dict[str, Any] | None:
        shard, epoch, revision = await self.r.hmget(self.kroom(rid), "authorityShard", "authorityEpoch", "authorityRevision")
        if not shard:
            return None
        return {"shard": shard, "epoch": int(epoch or 0), "revision": int(revision or -1)}

    async def accept_authority_event(self, rid: str, shard: str, epoch: int, revision: int) -> bool:
        script = """
        if redis.call('HGET', KEYS[1], 'authorityShard') ~= ARGV[1] then return 0 end
        if tonumber(redis.call('HGET', KEYS[1], 'authorityEpoch') or '0') ~= tonumber(ARGV[2]) then return 0 end
        local current = tonumber(redis.call('HGET', KEYS[1], 'authorityRevision') or '-1')
        if tonumber(ARGV[3]) <= current then return 0 end
        redis.call('HSET', KEYS[1], 'authorityRevision', ARGV[3])
        return 1
        """
        return int(await self.r.eval(script, 1, self.kroom(rid), shard, str(epoch), str(revision))) == 1

    async def account_ids_for_room(self, rid: str) -> dict[int, str]:
        if not await self.r.exists(self.kroom(rid)):
            raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
        raw_players = await self.r.hgetall(self.kplayers(rid))
        out: dict[int, str] = {}
        for seat_raw, raw in raw_players.items():
            try:
                player = json.loads(raw)
                account_id = str(player.get("accountId") or "")
                if account_id:
                    out[int(seat_raw)] = account_id
            except Exception:
                continue
        return out

    async def claim_profile_result(self, rid: str) -> bool:
        script = """
        if redis.call('EXISTS', KEYS[1]) == 0 then return 0 end
        if redis.call('HGET', KEYS[1], 'profileResultClaimed') == '1' then return 0 end
        redis.call('HSET', KEYS[1], 'profileResultClaimed', '1')
        return 1
        """
        return int(await self.r.eval(script, 1, self.kroom(rid))) == 1

    async def allow_rate(self, key: str, limit: int, window_seconds: int) -> bool:
        if limit <= 0:
            return True
        script = """
        local n = redis.call('INCR', KEYS[1])
        if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
        return n
        """
        n = int(await self.r.eval(script, 1, self.krate(key), str(window_seconds)))
        return n <= limit

    async def leave_room(self, rid: str, seat: int, conn_id: str, connection_epoch: int, *, before_begin_only: bool = False) -> dict[str, Any]:
        raw = await self.r.hget(self.kplayers(rid), str(seat))
        current = json.loads(raw) if raw else None
        if not current:
            raise StoreError("NOT_IN_ROOM", "اللاعب غير موجود في غرفة")
        token = str(current.get("token") or "")
        token_key = self.ktoken(token) if token else f"{self.prefix}:token:invalid"
        script = """
        if redis.call('EXISTS', KEYS[1]) == 0 then return {-10,0,0} end
        local raw = redis.call('HGET', KEYS[2], ARGV[1]); if not raw then return {-11,0,0} end
        local p = cjson.decode(raw)
        if p['connected'] ~= true or p['connId'] ~= ARGV[2] or tonumber(p['connectionEpoch'] or 1) ~= tonumber(ARGV[3]) then return {-12,0,0} end
        if ARGV[6]=='1' and redis.call('HGET',KEYS[1],'begun')=='1' then return {1,0,0} end
        redis.call('DEL', KEYS[5])
        redis.call('SREM', KEYS[3], ARGV[1])
        local begun = redis.call('HGET', KEYS[1], 'begun') == '1'
        if not begun then
          redis.call('HDEL', KEYS[2], ARGV[1])
          redis.call('HSET', KEYS[4], ARGV[1], '0')
          redis.call('HSET', KEYS[1], 'started', '0')
          if tonumber(redis.call('HGET',KEYS[1],'ownerSeat') or '0')==tonumber(ARGV[1]) then
            local nextOwner=100
            for _,seat in ipairs(redis.call('HKEYS',KEYS[2])) do nextOwner=math.min(nextOwner,tonumber(seat)) end
            redis.call('HSET',KEYS[1],'ownerSeat',tostring(nextOwner))
          end
          redis.call('ZADD', KEYS[9], tonumber(redis.call('HGET', KEYS[1], 'waitingExpiresAt') or '0'), ARGV[5])
          local count = redis.call('HLEN', KEYS[2])
          if count == 0 then
            redis.call('ZREM', KEYS[9], ARGV[5])
            redis.call('DEL', KEYS[1], KEYS[2], KEYS[3], KEYS[4], KEYS[6], KEYS[7], KEYS[8])
            return {1,1,1}
          end
          return {1,1,0}
        end
        p['connected'] = false; p['ready'] = false; p['disconnectedAt'] = tonumber(ARGV[4])
        redis.call('HSET', KEYS[2], ARGV[1], cjson.encode(p))
        return {1,0,0}
        """
        ret = await self.r.eval(
            script, 9, self.kroom(rid), self.kplayers(rid), self.kready(rid), self.kseq(rid),
            token_key, self.khistory(rid), self.knodes(rid), self.kchat(rid), self.kwaiting(),
            str(seat), conn_id, str(connection_epoch), str(now_ms()), rid, "1" if before_begin_only else "0",
        )
        code = int(ret[0])
        if code == -12:
            raise StoreError("STALE_CONNECTION", "تم استبدال هذا الاتصال باتصال أحدث")
        if code < 0:
            raise StoreError("NOT_IN_ROOM", "اللاعب غير موجود في غرفة")
        if bool(int(ret[2])):
            await self.r.zrem(self.kroom_index(), rid)
        else:
            await self._touch(rid)
        return {"roomDeleted": bool(int(ret[2])), "seatFreed": bool(int(ret[1]))}

    async def mark_finished(self, rid: str) -> None:
        rid = normalize_room_id(rid)
        if await self.r.exists(self.kroom(rid)):
            p = self.r.pipeline(transaction=False)
            p.hset(self.kroom(rid), mapping={"finished": "1"})
            p.zrem(self.kroom_index(), rid)
            await p.execute()
            await self._touch(rid)

    async def add_spectator(self, rid: str, node_id: str, conn_id: str) -> None:
        rid = normalize_room_id(rid)
        state = await self.get_room_state(rid)
        if state.get("finished"):
            raise StoreError("MATCH_FINISHED", "المباراة انتهت")
        if not state.get("started"):
            raise StoreError("MATCH_NOT_STARTED", "المباراة لم تبدأ")
        await self.r.hset(self.kspectators(rid), conn_id, node_id)
        await self._touch(rid)

    async def remove_spectator(self, rid: str, conn_id: str) -> None:
        try:
            await self.r.hdel(self.kspectators(normalize_room_id(rid)), conn_id)
        except StoreError:
            return

    async def disconnect(self, rid: str, seat: int, conn_id: str) -> None:
        script = """
        local raw = redis.call('HGET', KEYS[1], ARGV[1]); if not raw then return 0 end
        local p = cjson.decode(raw); if p['connId'] ~= ARGV[2] then return 0 end
        p['connected'] = false; p['ready'] = false; p['disconnectedAt'] = tonumber(ARGV[3])
        redis.call('HSET', KEYS[1], ARGV[1], cjson.encode(p)); redis.call('SREM', KEYS[2], ARGV[1]); return 1
        """
        await self.r.eval(script, 2, self.kplayers(rid), self.kready(rid), str(seat), conn_id, str(now_ms()))

    async def room_nodes(self, rid: str) -> set[str]:
        nodes = set(await self.r.smembers(self.knodes(rid)))
        nodes.update(await self.r.hvals(self.kspectators(rid)))
        return {str(x) for x in nodes if x}

    async def publish_node(self, node_id: str, event: dict[str, Any]) -> None:
        await self.r.publish(self.node_channel(node_id), json.dumps(event, separators=(",", ":")))

    async def node_listener(self, node_id: str):
        pubsub = self.r.pubsub(ignore_subscribe_messages=True)
        try:
            await pubsub.execute_command('CLIENT', 'SETNAME', f'samidev:{self.prefix}:node:{node_id}')
            await pubsub.parse_response(block=True)  # consume SETNAME's OK before Pub/Sub messages
            await pubsub.subscribe(self.node_channel(node_id))
            yield {'control': 'stream_ready'}
            async for msg in pubsub.listen():
                if msg.get("type") == "message":
                    try:
                        yield json.loads(msg["data"])
                    except Exception:
                        continue
        finally:
            await pubsub.aclose()

    async def manage_waiting_table(self, rid, seat, conn_id, epoch, action, target_seat=-1):
        if action not in {'close','kick'}: raise StoreError('BAD_TABLE_ACTION','إجراء غير مدعوم')
        script = WAITING_LUA + """
        if redis.call('EXISTS',KEYS[1])==0 then return {-10} end
        local raw=redis.call('HGET',KEYS[2],ARGV[1]); if not raw then return {-11} end
        local p=cjson.decode(raw)
        if p['connId']~=ARGV[2] or tonumber(p['connectionEpoch'])~=tonumber(ARGV[3]) or p['connected']~=true then return {-11} end
        if redis.call('HGET',KEYS[1],'begun')=='1' or redis.call('HGET',KEYS[1],'finished')=='1' or waiting_expired(KEYS[1]) then return {-12} end
        if tonumber(redis.call('HGET',KEYS[1],'ownerSeat') or '0')~=tonumber(ARGV[1]) then return {-13} end
        local created=redis.call('HGET',KEYS[1],'createdAt')
        if ARGV[4]=='close' then
          redis.call('HSET',KEYS[1],'waitingExpired','1','finished','1','closedReason','TABLE_CLOSED')
          redis.call('ZREM',KEYS[5],ARGV[6]);redis.call('ZREM',KEYS[6],ARGV[6])
          return {1,created,'',''}
        end
        if ARGV[5]==ARGV[1] then return {-14} end
        local target=redis.call('HGET',KEYS[2],ARGV[5]);if not target then return {-15} end
        target=cjson.decode(target)
        redis.call('DEL',ARGV[7]..':token:'..target['token'])
        redis.call('HDEL',KEYS[2],ARGV[5]);redis.call('SREM',KEYS[3],ARGV[5]);redis.call('HSET',KEYS[4],ARGV[5],'0')
        redis.call('HSET',KEYS[1],'started','0')
        redis.call('ZADD',KEYS[5],tonumber(redis.call('HGET',KEYS[1],'waitingExpiresAt') or '0'),ARGV[6])
        return {1,created,target['connId'] or '',target['nodeId'] or ''}
        """
        ret=await self.r.eval(script,6,self.kroom(rid),self.kplayers(rid),self.kready(rid),self.kseq(rid),self.kwaiting(),self.kroom_index(),
            str(seat),conn_id,str(epoch),action,str(target_seat),rid,self.prefix)
        code=int(ret[0])
        errors={-10:('ROOM_NOT_FOUND','الطاولة غير موجودة'),-11:('STALE_CONNECTION','الاتصال غير صالح'),
            -12:('TABLE_MANAGEMENT_CLOSED','إدارة الطاولة متاحة قبل اللعب فقط'),-13:('TABLE_OWNER_REQUIRED','هذه العملية لمنشئ الطاولة فقط'),
            -14:('CANNOT_KICK_OWNER','لا يمكن إخراج منشئ الطاولة'),-15:('NOT_IN_ROOM','المقعد فارغ')}
        if code<0:raise StoreError(*errors[code])
        return {'roomId':rid,'createdAt':int(ret[1]),'reason':'TABLE_CLOSED' if action=='close' else 'TABLE_KICKED',
            'targetConnId':str(ret[2]),'targetNodeId':str(ret[3])}

    async def waiting_closures(self, room_ids) -> list[dict[str, Any]]:
        out = []
        ids = list(room_ids)
        for offset in range(0,len(ids),256):
            batch = ids[offset:offset+256]
            pipe = self.r.pipeline(transaction=False)
            for rid in batch:
                pipe.hmget(self.kroom(rid),'createdAt','waitingExpiresAt','waitingExpired','started','begun','closedReason')
            pipe.time()
            rows = await pipe.execute()
            clock = rows.pop(); current = clock[0]*1000+clock[1]//1000
            for rid, row in zip(batch,rows):
                created,deadline,expired,started,begun,reason = row
                if created and (expired == '1' or (started != '1' and begun != '1' and int(deadline or 0)>0 and current>=int(deadline))):
                    out.append({"roomId":rid,"createdAt":int(created),"reason":reason or "ROOM_WAIT_EXPIRED"})
        return out

    async def expire_waiting_rooms(self, limit: int = 200) -> list[dict[str, Any]]:
        script = WAITING_LUA + """
        local t = redis.call('TIME')
        local clock = tonumber(t[1])*1000+math.floor(tonumber(t[2])/1000)
        local ids = redis.call('ZRANGEBYSCORE', KEYS[1], '-inf', clock, 'LIMIT', 0, tonumber(ARGV[2]))
        local out = {}
        for _,rid in ipairs(ids) do
          local key = ARGV[1] .. ':room:' .. rid
          if waiting_expired(key) and redis.call('HGET',key,'waitingExpired') ~= '1' then
            redis.call('HSET',key,'waitingExpired','1','finished','1')
            redis.call('ZREM',KEYS[2],rid)
            table.insert(out,cjson.encode({roomId=rid,createdAt=tonumber(redis.call('HGET',key,'createdAt') or '0')}))
          end
          redis.call('ZREM',KEYS[1],rid)
        end
        return out
        """
        rows = await self.r.eval(script, 2, self.kwaiting(), self.kroom_index(), self.prefix, str(max(1,min(1000,limit))))
        return [json.loads(row) for row in rows]

    async def sweep(self) -> None:
        return
