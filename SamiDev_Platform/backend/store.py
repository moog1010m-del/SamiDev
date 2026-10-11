from __future__ import annotations

import asyncio
import json
import re
import secrets
import time
from dataclasses import dataclass, field
from typing import Any
from games import GAMES, game_id, game_capacity

ROOM_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
ROOM_TTL_SECONDS = 6 * 60 * 60
TOKEN_TTL_SECONDS = ROOM_TTL_SECONDS
INVITE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,64}$")
MAX_HISTORY = 1200
CHAT_HISTORY_MAX = 30
CHAT_MAX_CHARS = 160
ROOM_RE = re.compile(r"^[ABCDEFGHJKLMNPQRSTUVWXYZ23456789]{6}$")
TOKEN_RE = re.compile(r"^[A-Za-z0-9_-]{20,64}$")


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
        return {"gameId":"pool", "gameType":0, "players":0, "live":1, "break":clamp_int(raw.get("break"),0,1,0), "trickShots":0}
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
    players: dict[int, MemPlayer] = field(default_factory=dict)
    started: bool = False
    begun: bool = False
    sequence: list[int] = field(default_factory=list)
    history: list[dict[str, Any]] = field(default_factory=list)
    chat: list[dict[str, Any]] = field(default_factory=list)
    move_count: int = 0
    snapshot: dict[str, Any] | None = None
    snapshot_move_count: int = -1
    snapshot_revision: int = -1
    authority_shard: str | None = None
    authority_epoch: int = 0
    authority_revision: int = -1
    profile_result_claimed: bool = False
    finished: bool = False
    spectator_nodes: dict[str, str] = field(default_factory=dict)
    expires_at: float = field(default_factory=lambda: time.monotonic() + ROOM_TTL_SECONDS)

    def __post_init__(self) -> None:
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

    def _room_payload(self, room: MemRoom) -> dict[str, Any]:
        return {
            "roomId": room.room_id,
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
                if room.finished:
                    continue
                roster = self._roster(room, include_account_ids=False)
                occupied = sum(1 for p in room.players.values())
                out.append({
                    "roomId": room.room_id, "communityId": room.community_id, "capacity": room.capacity, "occupied": occupied,
                    "settings": dict(room.settings), "started": bool(room.started), "begun": bool(room.begun),
                    "createdAt": room.created_at, "hostName": roster[0]["name"] if roster else None,
                    "roster": roster,
                })
            return out

    async def create_invite(self, room_id: str, seat: int, conn_id: str, connection_epoch: int, ttl_seconds: int) -> dict[str, Any]:
        room_id = normalize_room_id(room_id)
        async with self.lock:
            room = self.rooms.get(room_id)
            if not room:
                raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
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
                return True
            return False

    async def append_move(self, room_id: str, seat: int, packet: dict[str, Any], conn_id: str | None = None, connection_epoch: int | None = None) -> dict[str, Any]:
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
            if n != expected:
                raise StoreError("DESYNC", json.dumps({"expected": expected, "actual": n, "moveCount": room.move_count}))
            room.sequence[seat] += 1
            entry = {"seat": seat, "packet": packet, "moveIndex": room.move_count}
            room.move_count += 1
            room.history.append(entry)
            if len(room.history) > MAX_HISTORY:
                room.history = room.history[-MAX_HISTORY:]
            room.expires_at = time.monotonic() + ROOM_TTL_SECONDS
            return entry

    async def append_chat(self, room_id: str, seat: int, conn_id: str, connection_epoch: int, text: str) -> dict[str, Any]:
        async with self.lock:
            room = self.rooms.get(room_id)
            player = room.players.get(seat) if room else None
            if not player or not player.connected or player.conn_id != conn_id or player.connection_epoch != connection_epoch:
                raise StoreError("STALE_CONNECTION", "تم استبدال هذا الاتصال باتصال أحدث")
            message = {"id": secrets.token_urlsafe(9), "seat": int(seat), "text": str(text), "ts": now_ms()}
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

    async def set_snapshot(self, room_id: str, seat: int, state: dict[str, Any], move_count: int, revision: int = 0) -> None:
        async with self.lock:
            room = self.rooms.get(room_id)
            if not room or not room.started:
                return
            if move_count < room.snapshot_move_count or move_count > room.move_count:
                return
            if move_count == room.snapshot_move_count and revision < room.snapshot_revision:
                return
            room.snapshot = state
            room.snapshot_move_count = move_count
            room.snapshot_revision = revision

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

    async def leave_room(self, room_id: str, seat: int, conn_id: str, connection_epoch: int) -> dict[str, Any]:
        async with self.lock:
            room = self.rooms.get(room_id)
            p = room.players.get(seat) if room else None
            if not p or not p.connected or p.conn_id != conn_id or p.connection_epoch != connection_epoch:
                raise StoreError("STALE_CONNECTION", "تم استبدال هذا الاتصال باتصال أحدث")
            # Explicit exit invalidates reconnect ownership. Before the authoritative
            # match begins, also free the seat so a replacement player may join.
            self.tokens.pop(p.token, None)
            if not room.begun:
                room.players.pop(seat, None)
                room.started = False
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
    def node_channel(self, node_id: str) -> str: return f"{self.prefix}:node:{node_id}"
    def krate(self, key: str) -> str: return f"{self.prefix}:rate:{key}"
    def kroom_index(self) -> str: return f"{self.prefix}:rooms:index"

    async def ping(self) -> bool:
        return bool(await self.r.ping())

    async def _touch(self, rid: str) -> None:
        keys = [self.kroom(rid), self.kplayers(rid), self.kseq(rid), self.khistory(rid), self.kready(rid), self.knodes(rid), self.kspectators(rid), self.kchat(rid)]
        p = self.r.pipeline(transaction=False)
        for key in keys:
            p.expire(key, ROOM_TTL_SECONDS)
        await p.execute()

    async def create_room(self, name: str, settings: dict[str, int], node_id: str, conn_id: str, account_id: str | None = None, community_id: str = "majlis") -> dict[str, Any]:
        capacity = game_capacity(settings)
        for _ in range(30):
            rid = new_room_id()
            token = new_token()
            player = {"token": token, "name": sanitize_name(name), "seat": 0, "nodeId": node_id, "connId": conn_id, "accountId": account_id, "connected": True, "ready": False, "disconnectedAt": None, "connectionEpoch": 1}
            script = """
            if redis.call('EXISTS', KEYS[1]) == 1 then return 0 end
            redis.call('HSET', KEYS[1], 'capacity', ARGV[1], 'settings', ARGV[2], 'communityId', ARGV[8], 'started', '0', 'begun', '0', 'moveCount', '0', 'snapshotMoveCount', '-1', 'snapshotRevision', '-1', 'authorityShard', '', 'authorityEpoch', '0', 'authorityRevision', '-1', 'profileResultClaimed', '0', 'finished', '0', 'createdAt', ARGV[3])
            redis.call('HSET', KEYS[2], '0', ARGV[4])
            for i=0,tonumber(ARGV[1])-1 do redis.call('HSET', KEYS[3], tostring(i), '0') end
            redis.call('SET', KEYS[4], ARGV[5], 'EX', ARGV[6])
            redis.call('SADD', KEYS[5], ARGV[7])
            redis.call('EXPIRE', KEYS[1], ARGV[6]); redis.call('EXPIRE', KEYS[2], ARGV[6]); redis.call('EXPIRE', KEYS[3], ARGV[6]); redis.call('EXPIRE', KEYS[5], ARGV[6])
            return 1
            """
            ok = await self.r.eval(script, 5, self.kroom(rid), self.kplayers(rid), self.kseq(rid), self.ktoken(token), self.knodes(rid), str(capacity), json.dumps(settings, separators=(",", ":")), str(now_ms()), json.dumps(player, separators=(",", ":")), f"{rid}:0", str(TOKEN_TTL_SECONDS), node_id, str(community_id or "majlis")[:32])
            if int(ok) == 1:
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
                    script = """
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
                        script, 3, self.kplayers(rid), self.knodes(rid), self.kready(rid),
                        str(seat), sanitize_name(name), node_id, conn_id, str(account_id or ""), token,
                    )
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
        script = """
        if redis.call('EXISTS', KEYS[1]) == 0 then return {-10} end
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
        raw = await p.execute()
        out: list[dict[str, Any]] = []
        stale: list[str] = []
        for i, rid in enumerate(rids):
            room = raw[i * 2] or {}
            players = raw[i * 2 + 1] or {}
            if not room:
                stale.append(rid)
                continue
            if room.get("finished") == "1":
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
                "hostName": roster[0]["name"] if roster else None, "roster": roster,
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
        script = """
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
        script = """
        if redis.call('GET', KEYS[1]) ~= ARGV[1] then return {-15} end
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
        meta = await self.r.hgetall(self.kroom(rid))
        if not meta:
            raise StoreError("ROOM_NOT_FOUND", "الغرفة غير موجودة")
        capacity = int(meta["capacity"])
        raw_players = await self.r.hgetall(self.kplayers(rid))
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
        seq_raw = await self.r.hgetall(self.kseq(rid))
        return {
            "roomId": rid,
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
        script = """
        if redis.call('EXISTS', KEYS[1]) == 0 then return -10 end
        local raw = redis.call('HGET', KEYS[2], ARGV[1]); if not raw then return -11 end
        local p = cjson.decode(raw)
        if p['connected'] ~= true or p['connId'] ~= ARGV[2] or tonumber(p['connectionEpoch'] or 1) ~= tonumber(ARGV[3]) then return -12 end
        p['ready'] = true; redis.call('HSET', KEYS[2], ARGV[1], cjson.encode(p))
        redis.call('SADD', KEYS[3], ARGV[1])
        local cap = tonumber(redis.call('HGET', KEYS[1], 'capacity'))
        if redis.call('HGET', KEYS[1], 'started') == '1' and redis.call('HGET', KEYS[1], 'begun') ~= '1' and redis.call('SCARD', KEYS[3]) >= cap then
          redis.call('HSET', KEYS[1], 'begun', '1'); return 1
        end
        return 0
        """
        ret = int(await self.r.eval(script, 3, self.kroom(rid), self.kplayers(rid), self.kready(rid), str(seat), conn_id, str(connection_epoch)))
        if ret == -12:
            raise StoreError("STALE_CONNECTION", "تم استبدال هذا الاتصال باتصال أحدث")
        if ret < 0:
            raise StoreError("NOT_IN_ROOM", "اللاعب غير موجود في غرفة")
        return ret == 1

    async def append_move(self, rid: str, seat: int, packet: dict[str, Any], conn_id: str | None = None, connection_epoch: int | None = None) -> dict[str, Any]:
        if conn_id is not None and connection_epoch is not None:
            await self.assert_connection(rid, seat, conn_id, connection_epoch)
        state = await self.get_room_state(rid)
        if not state.get("begun"):
            raise StoreError("MATCH_NOT_READY", "المباراة لم تصبح جاهزة بعد")
        if "__info" in packet:
            return {"seat": seat, "packet": packet, "moveIndex": state["moveCount"], "infoAck": True, "infoOnly": True}
        n = packet.get("n"); move_id = packet.get("i")
        if not isinstance(n, int) or not isinstance(move_id, str):
            raise StoreError("BAD_MOVE", "حركة ناقصة")
        entry_base = {"seat": seat, "packet": packet}
        script = """
        if redis.call('EXISTS', KEYS[1]) == 0 or redis.call('HGET', KEYS[1], 'started') ~= '1' or redis.call('HGET', KEYS[1], 'begun') ~= '1' then return {-20,0,0} end
        local expected = tonumber(redis.call('HGET', KEYS[2], ARGV[1]) or '0')
        local actual = tonumber(ARGV[2])
        local mc = tonumber(redis.call('HGET', KEYS[1], 'moveCount') or '0')
        if expected ~= actual then return {-21, expected, mc} end
        redis.call('HINCRBY', KEYS[2], ARGV[1], 1)
        local entry = cjson.decode(ARGV[3]); entry['moveIndex'] = mc
        redis.call('RPUSH', KEYS[3], cjson.encode(entry)); redis.call('LTRIM', KEYS[3], -tonumber(ARGV[4]), -1)
        redis.call('HINCRBY', KEYS[1], 'moveCount', 1)
        return {mc, expected + 1, mc + 1}
        """
        ret = await self.r.eval(script, 3, self.kroom(rid), self.kseq(rid), self.khistory(rid), str(seat), str(n), json.dumps(entry_base, separators=(",", ":")), str(MAX_HISTORY))
        code = int(ret[0])
        if code == -20: raise StoreError("MATCH_NOT_READY", "المباراة لم تصبح جاهزة بعد")
        if code == -21: raise StoreError("DESYNC", json.dumps({"expected": int(ret[1]), "actual": n, "moveCount": int(ret[2])}))
        await self._touch(rid)
        return {"seat": seat, "packet": packet, "moveIndex": code}

    async def append_chat(self, rid: str, seat: int, conn_id: str, connection_epoch: int, text: str) -> dict[str, Any]:
        message = {"id": secrets.token_urlsafe(9), "seat": int(seat), "text": str(text), "ts": now_ms()}
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

    async def set_snapshot(self, rid: str, seat: int, state: dict[str, Any], move_count: int, revision: int = 0) -> None:
        script = """
        local current = tonumber(redis.call('HGET', KEYS[1], 'snapshotMoveCount') or '-1')
        local currentRevision = tonumber(redis.call('HGET', KEYS[1], 'snapshotRevision') or '-1')
        local total = tonumber(redis.call('HGET', KEYS[1], 'moveCount') or '0')
        local incoming = tonumber(ARGV[1])
        local incomingRevision = tonumber(ARGV[3])
        if incoming < current or incoming > total then return 0 end
        if incoming == current and incomingRevision < currentRevision then return 0 end
        redis.call('HSET', KEYS[1], 'snapshot', ARGV[2], 'snapshotMoveCount', incoming, 'snapshotRevision', incomingRevision)
        return 1
        """
        await self.r.eval(script, 1, self.kroom(rid), str(move_count), json.dumps(state, separators=(",", ":")), str(revision))

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

    async def leave_room(self, rid: str, seat: int, conn_id: str, connection_epoch: int) -> dict[str, Any]:
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
        redis.call('DEL', KEYS[5])
        redis.call('SREM', KEYS[3], ARGV[1])
        local begun = redis.call('HGET', KEYS[1], 'begun') == '1'
        if not begun then
          redis.call('HDEL', KEYS[2], ARGV[1])
          redis.call('HSET', KEYS[4], ARGV[1], '0')
          redis.call('HSET', KEYS[1], 'started', '0')
          local count = redis.call('HLEN', KEYS[2])
          if count == 0 then
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
            script, 8, self.kroom(rid), self.kplayers(rid), self.kready(rid), self.kseq(rid),
            token_key, self.khistory(rid), self.knodes(rid), self.kchat(rid),
            str(seat), conn_id, str(connection_epoch), str(now_ms()),
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
        await pubsub.subscribe(self.node_channel(node_id))
        try:
            async for msg in pubsub.listen():
                if msg.get("type") == "message":
                    try:
                        yield json.loads(msg["data"])
                    except Exception:
                        continue
        finally:
            await pubsub.aclose()

    async def sweep(self) -> None:
        return
