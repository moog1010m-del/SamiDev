from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import secrets
import signal
import time
import unicodedata
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from aiohttp import WSMsgType, web

from store import MemoryStore, RedisStore, StoreError, sanitize_settings
from gamehost_client import GameHostClient, GameHostError
from social_platform import PlatformService, PlatformHttp, PlatformError, cosmetic_id
from games import GAMES, game_id
from game_views import client_state
from quick_play import QuickPlay

ROOT = Path(__file__).resolve().parent.parent
GAME_ROOT = ROOT / "game"
UI_BUILD = json.loads((GAME_ROOT / "platform/build.json").read_text(encoding="utf-8"))
MAIN_JS_SHA256 = hashlib.sha256((GAME_ROOT / "main.js").read_bytes()).hexdigest()
GAME_CATALOG = {gid: {**info, "mainJsSha256": hashlib.sha256((GAME_ROOT / info["main"]).read_bytes()).hexdigest()} for gid, info in GAMES.items()}
NODE_ID = os.getenv("SAMIDEV_NODE_ID") or f"node-{secrets.token_hex(4)}"
STORE_MODE = os.getenv("SAMIDEV_STORE", "memory").lower()
REDIS_URL = os.getenv("SAMIDEV_REDIS_URL", "redis://redis:6379/0")
PLATFORM_STORE = os.getenv("SAMIDEV_PLATFORM_STORE", "postgres" if os.getenv("SAMIDEV_PRODUCTION") == "1" else STORE_MODE).lower()
DATABASE_URL = os.getenv("SAMIDEV_DATABASE_URL", "")
MAX_WS_MESSAGE = int(os.getenv("SAMIDEV_MAX_WS_MESSAGE", "65536"))
MAX_HTTP_BODY = max(MAX_WS_MESSAGE, int(os.getenv("SAMIDEV_MAX_HTTP_BODY", str(512 * 1024))))
MAX_MSG_RATE = float(os.getenv("SAMIDEV_MAX_MSG_RATE", "90"))
RATE_BURST = float(os.getenv("SAMIDEV_RATE_BURST", "150"))
ALLOWED_ORIGINS = {x.strip() for x in os.getenv("SAMIDEV_ALLOWED_ORIGINS", "*").split(",") if x.strip()}
TRUST_PROXY = os.getenv("SAMIDEV_TRUST_PROXY", "0") == "1"
TRUST_FORWARDED_HTTPS = os.getenv("SAMIDEV_TRUST_FORWARDED_HTTPS", "0") == "1"
CREATE_RATE_PER_MINUTE = int(os.getenv("SAMIDEV_CREATE_RATE_PER_MINUTE", "600"))
JOIN_RATE_PER_MINUTE = int(os.getenv("SAMIDEV_JOIN_RATE_PER_MINUTE", "1200"))
INVITE_RATE_PER_MINUTE = int(os.getenv("SAMIDEV_INVITE_RATE_PER_MINUTE", "30"))
INVITE_TTL_SECONDS = max(30, min(3600, int(os.getenv("SAMIDEV_INVITE_TTL_SECONDS", "600"))))
PRODUCTION_MODE = os.getenv("SAMIDEV_PRODUCTION", "0") == "1"
CHAT_MAX_CHARS = max(32, min(500, int(os.getenv("SAMIDEV_CHAT_MAX_CHARS", "160"))))
CHAT_RATE_MESSAGES = max(1, min(60, int(os.getenv("SAMIDEV_CHAT_RATE_MESSAGES", "8"))))
CHAT_RATE_WINDOW = max(1, min(60, int(os.getenv("SAMIDEV_CHAT_RATE_WINDOW", "10"))))
REQUIRE_GAME_AUTH = os.getenv("SAMIDEV_REQUIRE_GAME_AUTH", "1") == "1"


class AuthUnavailable(RuntimeError):
    """A dependency failure is not an invalid/revoked session."""


@dataclass
class Metrics:
    accepted: int = 0
    active: int = 0
    messages_in: int = 0
    messages_out: int = 0
    moves: int = 0
    errors: int = 0
    rate_limited: int = 0
    chat_messages: int = 0
    errors_by_code: dict[str, int] = field(default_factory=dict)
    listener_reconnects: int = 0
    send_timeouts: int = 0
    latencies: dict[str, deque] = field(default_factory=dict)
    started_at: float = field(default_factory=time.monotonic)


@dataclass
class Conn:
    ws: web.WebSocketResponse
    conn_id: str
    peer: str
    room_id: str | None = None
    room_created_at: int = 0
    seat: int | None = None
    token: str | None = None
    connection_epoch: int = 0
    name: str = "Player"
    account_id: str | None = None
    account_role: str = "guest"
    auth_session_key: str | None = None
    auth_version: str = "0"
    auth_expires_at: float = 0
    community_id: str = "majlis"
    community_blocked: str | None = None
    spectator: bool = False
    tokens: float = RATE_BURST
    last_refill: float = field(default_factory=time.monotonic)
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def allow_message(self) -> bool:
        now = time.monotonic()
        self.tokens = min(RATE_BURST, self.tokens + (now - self.last_refill) * MAX_MSG_RATE)
        self.last_refill = now
        if self.tokens < 1:
            return False
        self.tokens -= 1
        return True


class SamiDevRealtime:
    def __init__(self) -> None:
        if STORE_MODE not in {"memory", "redis"}:
            raise RuntimeError("SAMIDEV_STORE must be memory or redis")
        if PLATFORM_STORE not in {"memory", "redis", "postgres"}:
            raise RuntimeError("SAMIDEV_PLATFORM_STORE must be memory, redis or postgres")
        if PLATFORM_STORE in {"redis", "postgres"} and STORE_MODE != "redis":
            raise RuntimeError("Shared platform storage requires SAMIDEV_STORE=redis")
        if STORE_MODE == "redis" and PLATFORM_STORE == "memory":
            raise RuntimeError("Shared gateways cannot use in-memory accounts")
        self.store = RedisStore(REDIS_URL, prefix=os.getenv('SAMIDEV_REALTIME_PREFIX', 'sd')) if STORE_MODE == "redis" else MemoryStore()
        if PLATFORM_STORE == "postgres":
            from postgres_platform import PostgresPlatformService
            self.platform = PostgresPlatformService(DATABASE_URL, self.store.r,
                max_connections=int(os.getenv("SAMIDEV_DATABASE_POOL_SIZE", "10")))
        else:
            self.platform = PlatformService(getattr(self.store, "r", None))
        self.platform_http = PlatformHttp(self.platform, self.store, trust_proxy=TRUST_PROXY, trust_forwarded_https=TRUST_FORWARDED_HTTPS)
        self.quick_play = QuickPlay(self.store)
        self.gamehost = GameHostClient()
        self.metrics = Metrics()
        self.connections: dict[str, Conn] = {}
        self.room_local: dict[str, set[str]] = defaultdict(set)
        self.listener_task: asyncio.Task | None = None
        self.sweeper_task: asyncio.Task | None = None
        self.auth_task: asyncio.Task | None = None
        self.redis_listener_ready = False

    async def start(self, app: web.Application) -> None:
        if PRODUCTION_MODE:
            if not REQUIRE_GAME_AUTH:
                raise RuntimeError("SAMIDEV_REQUIRE_GAME_AUTH=1 is required in production")
            service_key = self.gamehost.service_key
            if len(service_key) < 32 or service_key in {"samidev-local-development-key-change-me", "CHANGE_ME_TO_A_LONG_RANDOM_SECRET"}:
                raise RuntimeError("Production requires a private SAMIDEV_GAMEHOST_SERVICE_KEY of at least 32 characters")
            if STORE_MODE != "redis":
                raise RuntimeError("SAMIDEV_PRODUCTION=1 requires SAMIDEV_STORE=redis")
            if PLATFORM_STORE != "postgres":
                raise RuntimeError("SAMIDEV_PRODUCTION=1 requires SAMIDEV_PLATFORM_STORE=postgres")
            if not ALLOWED_ORIGINS or "*" in ALLOWED_ORIGINS:
                raise RuntimeError("SAMIDEV_ALLOWED_ORIGINS must be explicit in production")
        try:
            if getattr(self.store, "distributed", False):
                await self.store.ping()
            await self.platform.start()
            self.gamehost.on_reconnect = self._recover_local_rooms
            await self.gamehost.start(self._on_gamehost_event)
            if getattr(self.store, "distributed", False):
                self.listener_task = asyncio.create_task(self._listen_remote(), name="samidev-redis-listener")
            async with asyncio.timeout(5):
                while not all(self.gamehost.event_connected.get(url, False) for url in self.gamehost.base_urls) or (
                    getattr(self.store, 'distributed', False) and not self.redis_listener_ready):
                    await asyncio.sleep(.01)
        except BaseException:
            if self.listener_task:
                self.listener_task.cancel()
                await asyncio.gather(self.listener_task, return_exceptions=True)
            await self.gamehost.close()
            if PLATFORM_STORE == "postgres": await self.platform.close()
            if getattr(self.store, "r", None) is not None: await self.store.r.aclose()
            raise
        self.auth_task = asyncio.create_task(self._auth_sweeper(), name="samidev-auth")
        self.sweeper_task = asyncio.create_task(self._sweeper(), name="samidev-sweeper")
        print(f"[SamiDev Realtime] node={NODE_ID} store={STORE_MODE}")

    async def stop(self, app: web.Application) -> None:
        for task in (self.listener_task, self.sweeper_task, self.auth_task):
            if task:
                task.cancel()
        await asyncio.gather(*(t for t in (self.listener_task, self.sweeper_task, self.auth_task) if t), return_exceptions=True)
        async def close_client(c):
            try:
                async with asyncio.timeout(2): await c.ws.close(code=1001, message=b'server shutdown')
            except (TimeoutError, ConnectionError): pass
        await asyncio.gather(*(close_client(c) for c in list(self.connections.values())), return_exceptions=True)
        await self.gamehost.close()
        await self.platform.live.close()
        if PLATFORM_STORE == "postgres": await self.platform.close()
        if getattr(self.store, "r", None) is not None: await self.store.r.aclose()

    async def connection_authorized(self, c: Conn) -> bool:
        if not c.account_id: return not REQUIRE_GAME_AUTH
        try:
            if c.auth_session_key:
                user = await self.platform.resolve_session_key(c.auth_session_key)
            else:
                if PRODUCTION_MODE or time.monotonic() >= c.auth_expires_at: return False
                user = await self.platform.get_user(c.account_id)
            if not user or str(user.get("banned") or "0") == "1" or str(user.get("authVersion") or "0") != c.auth_version: return False
            c.account_role = str(user.get("role") or "user")
            c.community_blocked = None
            try: self.platform.community_rules.check(user,c.community_id)
            except PlatformError as error: c.community_blocked = error.code
            return True
        except Exception as exc:
            raise AuthUnavailable(type(exc).__name__) from exc

    async def _auth_sweeper(self):
        while True:
            await asyncio.sleep(5)
            for c in list(self.connections.values()):
                try:
                    authorized = await self.connection_authorized(c)
                except AuthUnavailable:
                    await c.ws.close(code=1013, message=b'authentication service unavailable; retry')
                    continue
                if authorized and c.community_blocked and c.room_id and c.seat is not None and not c.spectator:
                    rid = c.room_id
                    try:
                        departed=await self.store.leave_room(rid,c.seat,c.conn_id,c.connection_epoch,before_begin_only=True)
                        if departed.get('seatFreed'):
                            self.room_local[rid].discard(c.conn_id)
                            c.room_id=None;c.seat=None;c.token=None
                            await self.send(c,{'type':'left_room','reason':c.community_blocked,'message':'أُخرجت من هذه المساحة','roomId':rid})
                            if not departed.get('roomDeleted'): await self.fanout(rid,await self.room_state_event(rid))
                    except StoreError: pass
                    except Exception: await c.ws.close(code=1013,message=b'community service unavailable; retry')
                if not authorized:
                    await c.ws.close(code=4003, message=b"authentication expired")

    async def _sweeper(self) -> None:
        ticks = 0
        while True:
            await asyncio.sleep(5)
            try:
                await self.store.expire_waiting_rooms()
                for rid in [rid for rid,ids in self.room_local.items() if not ids]: self.room_local.pop(rid,None)
                # Recoverable notification: each gateway checks its own attached
                # rooms, so a crash or a lost Pub/Sub message cannot strand users.
                for event in await self.store.waiting_closures(list(self.room_local)):
                    await self.deliver_local({"roomId":event["roomId"],"payload":{
                        "type":"left_room", "roomId":event["roomId"], "createdAt":event["createdAt"],
                        "reason":event.get("reason") or "ROOM_WAIT_EXPIRED", "message":"أُغلقت الطاولة أو انتهت مهلة انتظار اللاعبين"}})
                ticks += 1
                if ticks % 12 == 0: await self.store.sweep()
            except Exception as e:
                print("[SamiDev] sweeper", type(e).__name__)

    async def _listen_remote(self) -> None:
        backoff = 0.5
        subscribed = False
        while True:
            try:
                async for event in self.store.node_listener(NODE_ID):
                    if not isinstance(event, dict): continue
                    if event.get('control') == 'stream_ready':
                        self.redis_listener_ready = True
                        backoff = 0.5
                        if subscribed:
                            self.metrics.listener_reconnects += 1
                            await self._recover_local_rooms()
                        subscribed = True
                        continue
                    if event.get("control") == "close_connection":
                        old = self.connections.get(str(event.get("connId") or ""))
                        if old and not old.ws.closed:
                            await old.ws.close(code=4001, message=b"connection replaced")
                        continue
                    payload = event.get("payload")
                    if isinstance(payload, dict) and payload.get("type") == "__samidev_start_local":
                        await self.handle_internal_local_start(str(event.get("roomId") or ""))
                    else:
                        await self.deliver_local(event)
                raise ConnectionError('Redis subscription ended')
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print('[SamiDev] redis listener retry', type(e).__name__)
            finally:
                self.redis_listener_ready = False
            await asyncio.sleep(backoff)
            backoff = min(5.0, backoff * 2)

    async def _recover_local_rooms(self) -> None:
        # Pub/Sub/SSE do not replay lost packets. Ask each local replica for a
        # seat-filtered current checkpoint once the subscription is restored.
        for rid in list(self.room_local):
            await self.deliver_local({'roomId': rid, 'payload': {'type': 'sync_required', 'reason': 'event_stream_reconnected'}})

    async def _ensure_authority(self, rid: str, renew: bool = False) -> dict[str, Any]:
        start = await self.store.get_start(rid, 0)
        if start["settings"].get("gameId") == "pool" and start["settings"].get("gameType") in (8, 9):
            raise StoreError("RETIRED_POOL_MODE", "هذه مباراة هرم من نسخة سابقة؛ تم إيقاف هذا النوع")
        lease = await self.store.get_authority(rid)
        preferred = self.gamehost.shard_for(rid)
        if lease is None:
            lease = await self.store.claim_authority(rid, preferred, renew=False)
        elif not self.gamehost.has_shard(str(lease.get("shard") or "")):
            lease = await self.store.claim_authority(rid, preferred, renew=True)
        elif renew:
            lease = await self.store.claim_authority(rid, str(lease["shard"]), renew=True)
        epochs = await self.store.get_connection_epochs(rid)
        authority = await self.gamehost.ensure_room(
            rid, start["settings"], int(start["capacity"]), start.get("snapshot"),
            shard=str(lease["shard"]), authority_epoch=int(lease["epoch"]), connection_epochs=epochs,
            begun=bool(start.get("begun")),
        )
        authority["lease"] = lease
        await self._persist_live_authority(rid, authority)
        return authority

    async def _authority_lease(self, rid: str) -> dict[str, Any]:
        lease = await self.store.get_authority(rid)
        if lease is None or not self.gamehost.has_shard(str(lease.get("shard") or "")):
            authority = await self._ensure_authority(rid, renew=lease is not None)
            lease = authority["lease"]
        return lease

    async def _persist_live_authority(self, rid: str, authority: dict[str, Any]) -> None:
        """Persist a safe live GameHost checkpoint without ever trusting a browser snapshot."""
        sequence = authority.get("sequence")
        if isinstance(sequence, list):
            await self.store.sync_sequence(rid, sequence)
        snapshot = authority.get("snapshot")
        if not isinstance(snapshot, dict):
            return
        room = await self.store.get_room_state(rid)
        move_count = int(room.get("moveCount", 0))
        try:
            revision = int(authority.get("authorityRevision", authority.get("revision", 0)) or 0)
        except (TypeError, ValueError):
            revision = 0
        await self.store.set_snapshot(rid, -1, snapshot, move_count, revision=revision)

    async def _client_start(self, rid: str, seat: int) -> dict[str, Any]:
        start = await self.store.get_start(rid, seat)
        if game_id(start["settings"]) in {"crazy8", "pool"}:
            # Card games need the server's deal before any browser initializes.
            await self._ensure_authority(rid)
            start = await self.store.get_start(rid, seat)
        start["cosmetics"] = await self.room_cosmetics(rid, start["settings"])
        return client_state(start, start["settings"], seat)

    async def _client_resync(self, rid: str, seat: int) -> dict[str, Any]:
        payload = await self._authoritative_resync(rid)
        room = await self.store.get_room_state(rid)
        payload["cosmetics"] = await self.room_cosmetics(rid, room["settings"])
        return client_state(payload, room["settings"], seat)

    async def _authoritative_resync(self, rid: str) -> dict[str, Any]:
        """Prefer a current GameHost checkpoint; fall back to the durable store if unavailable."""
        fallback = await self.store.resync(rid)
        try:
            lease = await self._authority_lease(rid)
            live = await self.gamehost.state(rid, shard=str(lease["shard"]))
            await self._persist_live_authority(rid, live)
            payload = await self.store.resync(rid)
            payload.update({
                "authorityEpoch": live.get("authorityEpoch", lease.get("epoch")),
                "revision": live.get("authorityRevision"),
                "turn": live.get("turn") or [],
                "gameOver": bool(live.get("gameOver")),
                "snapshotDeferred": bool(live.get("snapshotDeferred")),
            })
            return payload
        except Exception as e:
            # Resync remains available during a transient GameHost/SSE outage. The browser keeps
            # its authority mismatch pending and will retry if this stored checkpoint is stale.
            print("[SamiDev] live resync fallback", type(e).__name__, e)
            return fallback

    def _winner_seats_from_authority(self, event: dict[str, Any]) -> list[int]:
        finish_order = event.get("finishOrder")
        if not isinstance(finish_order, list) or not finish_order or not isinstance(finish_order[0], list):
            return []
        teams = event.get("teams")
        winner_seats: set[int] = set()
        for raw_index in finish_order[0]:
            try:
                index = int(raw_index)
            except (TypeError, ValueError):
                continue
            if isinstance(teams, list) and 0 <= index < len(teams) and isinstance(teams[index], list):
                for raw_seat in teams[index]:
                    try:
                        seat = int(raw_seat)
                    except (TypeError, ValueError):
                        continue
                    if seat >= 0:
                        winner_seats.add(seat)
            elif index >= 0:
                winner_seats.add(index)
        return sorted(winner_seats)

    async def _award_profile_wins(self, rid: str, event: dict[str, Any]) -> None:
        if not bool(event.get("gameOver")):
            return
        winner_seats = self._winner_seats_from_authority(event)
        if not winner_seats:
            return
        account_ids = await self.store.account_ids_for_room(rid)
        room = await self.store.get_room_state(rid)
        gid = game_id(room['settings'])
        created = int(room['createdAt'])
        # A room code may be reused. The creation time distinguishes matches;
        # account result + per-game counters + overall wins commit atomically.
        match = f'{rid}:{created}'
        tied = len(event['finishOrder'][0]) > 1
        for uid in sorted({str(v) for v in account_ids.values() if v}):
            winner = any(account_ids.get(seat) == uid for seat in winner_seats)
            try:
                await self.platform.record_game_result(uid, gid, match, won=winner and not tied, drawn=winner and tied)
            except PlatformError as exc:
                print("[SamiDev] profile win award", uid, exc.code)

    async def _award_daily_match_rewards(self, rid: str, event: dict[str, Any]) -> None:
        if not bool(event.get("gameOver")):
            return
        account_ids = await self.store.account_ids_for_room(rid)
        for uid in sorted({str(v) for v in account_ids.values() if v}):
            try:
                result = await self.platform.award_daily_match_coins(uid, rid)
                if not result.get('duplicate'):
                    notice = {'type': 'match_reward', 'roomId': rid,
                              'id': f"{result['day']}:{rid}:{uid}",
                              'amount': result.get('amount', 0),
                              'rewardedMatches': result.get('rewardedMatchesToday', 0),
                              'remainingMatches': result.get('remainingMatches', 0)}
                    delivery = {'roomId': rid, 'payloadBySeat': {
                        str(seat): notice for seat, account in account_ids.items() if str(account) == uid
                    }}
                    await self.deliver_local(delivery)
                    if getattr(self.store, 'distributed', False):
                        for node in await self.store.room_nodes(rid):
                            if node != NODE_ID:
                                await self.store.publish_node(node, delivery)
                if result.get("awarded"):
                    print(f"[SamiDev Store] daily match reward uid={uid} room={rid} +{result.get('amount')} coins")
            except PlatformError as exc:
                print("[SamiDev Store] daily match reward", uid, exc.code)

    async def _on_gamehost_event(self, event: dict[str, Any]) -> None:
        event_type = event.get("type")
        if event_type not in {"authority_state", "authority_alarm"}:
            return
        rid = str(event.get("roomId") or "")
        if not rid:
            return
        shard = str(event.get("shard") or "")
        try:
            epoch = int(event.get("authorityEpoch"))
            revision = int(event.get("revision"))
        except (TypeError, ValueError):
            return
        snapshot = event.get("snapshot")
        try:
            # All gateways listen to GameHost events. Redis atomically accepts each
            # authority revision once, so exactly one gateway republishes it cluster-wide.
            if not await self.store.accept_authority_event(rid, shard, epoch, revision):
                return
            if bool(event.get("gameOver")):
                await self.store.mark_finished(rid)
            authority_sequence = event.get("sequence")
            if isinstance(authority_sequence, list):
                await self.store.sync_sequence(rid, authority_sequence)
            room = await self.store.get_room_state(rid)
            move_count = int(room.get("moveCount", 0))
            # Snapshot persistence is optional for an event. Never drop a valid alarm just
            # because the current physics checkpoint is intentionally not serializable yet.
            if isinstance(snapshot, dict):
                await self.store.set_snapshot(rid, -1, snapshot, move_count, revision=revision)
            if event_type == "authority_alarm":
                reveal_by_seat = event.get("revealBySeat") if isinstance(event.get("revealBySeat"), dict) else {}
                if not reveal_by_seat:
                    return
                base = {
                    "type": "authority_alarm",
                    "roomId": rid,
                    "alarmId": event.get("alarmId"),
                    "authorityEpoch": epoch,
                    "revision": revision,
                    "turn": event.get("turn") or [],
                    "sequence": event.get("sequence") or [],
                    **({"pool":event["pool"]} if "pool" in event else {}),
                    "gameOver": bool(event.get("gameOver")),
                    "moveCount": move_count,
                }
                await self.fanout_personalized(rid, base, reveal_by_seat)
            else:
                await self.fanout(rid, {
                    "type": "authority_state",
                    "roomId": rid,
                    "reason": event.get("reason"),
                    "authorityEpoch": epoch,
                    "revision": revision,
                    "turn": event.get("turn") or [],
                    "sequence": event.get("sequence") or [],
                    **({"pool":event["pool"]} if "pool" in event else {}),
                    "gameOver": bool(event.get("gameOver")),
                    "moveCount": move_count,
                })
            if event.get("gameOver") and isinstance(snapshot, dict):
                # A timeout can end a game with no later player move to repair a
                # paused replica. Push the final seat-filtered checkpoint now.
                await self.fanout_finished_checkpoint(rid, room, event, move_count)
            # Gameplay/terminal state is delivered before SQL rewards. A wallet
            # transaction must not hide a turn/result from the other player.
            await self._award_profile_wins(rid, event)
            await self._award_daily_match_rewards(rid, event)
        except Exception as e:
            print("[SamiDev] authority event", type(e).__name__, e)

    async def send(self, c: Conn, payload: dict[str, Any]) -> None:
        if c.ws.closed:
            return
        try:
            async with asyncio.timeout(3):
                async with c.send_lock:
                    await c.ws.send_str(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
        except (TimeoutError, ConnectionError, RuntimeError):
            self.metrics.send_timeouts += 1
            try:
                async with asyncio.timeout(1):
                    await c.ws.close(code=1013, message=b'slow connection; reconnect')
            except (TimeoutError, ConnectionError, RuntimeError): pass
            return
        self.metrics.messages_out += 1

    async def error(self, c: Conn, code: str, message: str, **extra: Any) -> None:
        self.record_problem(c, code, **extra)
        await self.send(c, {"type": "error", "code": code, "message": message, **extra})

    def record_problem(self, c: Conn, code: str, **diagnostics: Any) -> None:
        self.metrics.errors += 1
        self.metrics.errors_by_code[code] = self.metrics.errors_by_code.get(code, 0) + 1
        event = {'event':'ws_error','node':NODE_ID,'roomId':c.room_id,
            'connectionId':c.conn_id,'seat':c.seat,'code':code,'time':int(time.time()*1000)}
        # Bounded diagnosis only; never log packets, auth tokens or user content.
        for key in ('expectedSequence', 'packetSequence', 'moveAction'):
            value = diagnostics.get(key)
            if type(value) is int and 0 <= value <= 2**53-1:
                event[key] = value
        reason = diagnostics.get('reason')
        if isinstance(reason, str) and re.fullmatch(r'[A-Z_]{1,80}', reason):
            event['reason'] = reason
        print(json.dumps(event, separators=(',', ':')))

    def observe(self, stage: str, began: float) -> None:
        self.metrics.latencies.setdefault(stage, deque(maxlen=512)).append((time.monotonic()-began)*1000)

    def attach(self, c: Conn, data: dict[str, Any]) -> None:
        if c.room_id:
            self.room_local[c.room_id].discard(c.conn_id)
        c.room_id = data["roomId"]
        c.room_created_at = int(data.get("createdAt") or 0)
        c.community_id = str(data.get("communityId") or c.community_id)
        c.seat = int(data["seat"])
        c.token = data["token"]
        c.connection_epoch = int(data.get("connectionEpoch", 1))
        c.spectator = False
        self.room_local[c.room_id].add(c.conn_id)

    async def attach_spectator(self, c: Conn, room_id: str) -> None:
        if c.room_id:
            self.room_local[c.room_id].discard(c.conn_id)
        await self.store.add_spectator(room_id, NODE_ID, c.conn_id)
        c.room_id = room_id
        c.seat = None
        c.token = None
        c.connection_epoch = 0
        c.spectator = True
        self.room_local[room_id].add(c.conn_id)

    async def invalidate_replaced_connection(self, data: dict[str, Any]) -> None:
        old_conn = str(data.get("replacedConnId") or "")
        old_node = str(data.get("replacedNodeId") or "")
        if not old_conn or old_conn == data.get("connId"):
            return
        if old_node == NODE_ID:
            old = self.connections.get(old_conn)
            if old and not old.ws.closed:
                await old.ws.close(code=4001, message=b"connection replaced")
        elif old_node and getattr(self.store, "distributed", False):
            await self.store.publish_node(old_node, {"control": "close_connection", "connId": old_conn})

    def public_join_data(self, data: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in data.items() if k not in {"replacedNodeId", "replacedConnId"}}

    async def enforce_action_rate(self, c: Conn, action: str, limit: int) -> None:
        if not await self.store.allow_rate(f"{action}:{c.peer}", limit, 60):
            self.metrics.rate_limited += 1
            raise StoreError("RATE_LIMIT", "تم تجاوز معدل هذه العملية المسموح")

    def effective_name(self, c: Conn, msg: dict[str, Any]) -> str:
        if c.account_id:
            return c.name
        return str(msg.get("name") or "Player")

    def sanitize_chat_text(self, value: Any) -> str:
        text = unicodedata.normalize("NFC", str(value or ""))
        text = "".join(ch for ch in text if ch in (" ", "\t") or unicodedata.category(ch) not in {"Cc", "Cf", "Cs"})
        text = " ".join(text.split()).strip()
        if not text:
            raise StoreError("CHAT_EMPTY", "الرسالة فارغة")
        if len(text) > CHAT_MAX_CHARS:
            raise StoreError("CHAT_TOO_LONG", f"الحد الأقصى للرسالة {CHAT_MAX_CHARS} حرفًا")
        return text

    async def send_chat_history(self, c: Conn) -> None:
        if not c.room_id:
            return
        messages = await self.store.chat_history(c.room_id)
        await self.send(c, {"type": "chat_history", "messages": messages})

    async def room_state_event(self, rid: str) -> dict[str, Any]:
        state = await self.store.get_room_state(rid)
        return {"type": "room_state", "cosmetics": await self.room_cosmetics(rid, state["settings"]), **{k: state[k] for k in ("roomId", "capacity", "settings", "started", "begun", "finished", "roster", "moveCount", "waitingExpiresAt", "waitingExpired", "ownerSeat")}}

    async def room_cosmetics(self, rid: str, settings: dict) -> dict:
        if game_id(settings) != "pool":
            return {}
        accounts = await self.store.account_ids_for_room(rid)
        result = {}
        for seat, uid in accounts.items():
            theme = "pool_midnight"
            cue = "pool_cue_classic"
            if uid:
                owned = await self.platform.store_snapshot(str(uid))
                if owned["equipped"].get("pool_theme") == "pool_emerald":
                    theme = "pool_emerald"
                if owned["equipped"].get("pool_cue") == "pool_cue_moon":
                    cue = "pool_cue_moon"
            result[str(seat)] = {"pool_theme": theme, "pool_cue": cue}
        return result

    async def fanout_finished_checkpoint(self, rid: str, room: dict, authority: dict, move_count: int) -> None:
        checkpoint = {"type": "resync_state", "roomId": rid, "reason": "game_finished",
                      "snapshot": authority["snapshot"], "snapshotMoveCount": move_count,
                      "moveCount": move_count, "history": [], "gameOver": True,
                      "turn": authority.get("turn") or [], "sequence": authority.get("sequence") or [],
                      "authorityEpoch": authority.get("authorityEpoch"), "revision": authority.get("revision"),
                      "cosmetics": await self.room_cosmetics(rid, room["settings"])}
        event = {"roomId": rid, "payloadBySeat": {
            str(seat): client_state(checkpoint, room["settings"], seat) for seat in range(room["capacity"])
        }, "spectatorPayload": client_state(checkpoint, room["settings"], -1)}
        await self.deliver_local(event)
        if getattr(self.store, "distributed", False):
            for node in await self.store.room_nodes(rid):
                if node != NODE_ID:
                    await self.store.publish_node(node, event)

    async def fanout(self, rid: str, payload: dict[str, Any], include_local: bool = True) -> None:
        event = {"roomId": rid, "payload": payload}
        if include_local:
            await self.deliver_local(event)
        if getattr(self.store, "distributed", False):
            nodes = await self.store.room_nodes(rid)
            for node in nodes:
                if node != NODE_ID:
                    await self.store.publish_node(node, event)

    async def fanout_personalized(self, rid: str, base_payload: dict[str, Any], reveal_by_seat: dict[str, Any]) -> None:
        state = await self.store.get_room_state(rid)
        capacity = int(state.get("capacity", 0))
        payload_by_seat: dict[str, dict[str, Any]] = {}
        for seat in range(capacity):
            payload = dict(base_payload)
            reveal = reveal_by_seat.get(str(seat))
            if reveal is not None:
                payload["reveal"] = reveal
            payload_by_seat[str(seat)] = payload
        spectator_payload = {
            "type": "spectator_resync",
            "roomId": rid,
            "sourceType": base_payload.get("type"),
            "authorityEpoch": base_payload.get("authorityEpoch"),
            "revision": base_payload.get("revision"),
            "gameOver": bool(base_payload.get("gameOver")),
        }
        if game_id(state["settings"]) == "pool":
            # Pool has no hidden hands. Spectators can receive the same public
            # trajectory, while existing card-game privacy remains unchanged.
            public = next((r for r in reveal_by_seat.values() if isinstance(r, dict) and isinstance(r.get("pool"), dict)), None)
            if public is not None:
                spectator_payload = {**base_payload, "reveal": {"pool": public["pool"], "frames": public.get("frames", []), "soundEvents": public.get("soundEvents", [])}}
        event = {"roomId": rid, "payloadBySeat": payload_by_seat, "spectatorPayload": spectator_payload}
        await self.deliver_local(event)
        if getattr(self.store, "distributed", False):
            nodes = await self.store.room_nodes(rid)
            for node in nodes:
                if node != NODE_ID:
                    await self.store.publish_node(node, event)

    async def deliver_local(self, event: dict[str, Any]) -> None:
        rid = event.get("roomId")
        payload = event.get("payload")
        payload_by_seat = event.get("payloadBySeat")
        spectator_payload = event.get("spectatorPayload")
        if not rid or (not isinstance(payload, dict) and not isinstance(payload_by_seat, dict) and not isinstance(spectator_payload, dict)):
            return
        ids = list(self.room_local.get(rid, ()))
        if not ids:
            return
        sends = []
        for cid in ids:
            c = self.connections.get(cid)
            if not c:
                continue
            selected = spectator_payload if c.spectator and isinstance(spectator_payload, dict) else payload
            if isinstance(payload_by_seat, dict) and not c.spectator and c.seat is not None:
                selected = payload_by_seat.get(str(c.seat))
            if isinstance(selected, dict):
                if selected.get("type") == "left_room" and selected.get("reason") in {"ROOM_WAIT_EXPIRED","TABLE_CLOSED","TABLE_KICKED"}:
                    if selected.get("targetConnId") and selected["targetConnId"] != cid: continue
                    if c.room_created_at != int(selected.get("createdAt") or 0): continue
                    self.room_local[rid].discard(cid)
                    c.room_id = None; c.seat = None; c.token = None; c.connection_epoch = 0
                    if not self.room_local[rid]: self.room_local.pop(rid,None)
                sends.append(self.send(c, selected))
        if sends:
            await asyncio.gather(*sends, return_exceptions=True)

    async def maybe_send_start_to_all(self, rid: str) -> None:
        state = await self.store.get_room_state(rid)
        if not state["started"]:
            return
        for cid in list(self.room_local.get(rid, ())):
            c = self.connections.get(cid)
            if not c or c.seat is None:
                continue
            try:
                start = await self._client_start(rid, c.seat)
                await self.send(c, {"type": "start", **start})
            except StoreError:
                pass
        if getattr(self.store, "distributed", False):
            # Remote nodes learn that the room has started; each node builds start data for its local seats.
            nodes = await self.store.room_nodes(rid)
            for node in nodes:
                if node != NODE_ID:
                    await self.store.publish_node(node, {"roomId": rid, "payload": {"type": "__samidev_start_local"}})

    async def handle_internal_local_start(self, rid: str) -> None:
        for cid in list(self.room_local.get(rid, ())):
            c = self.connections.get(cid)
            if c and c.seat is not None:
                try:
                    await self.send(c, {"type": "start", **await self._client_start(rid, c.seat)})
                except StoreError:
                    pass

    async def handle(self, c: Conn, msg: dict[str, Any]) -> None:
        kind = msg.get("type")
        if c.account_id and kind in {'quick_play','create_room','join_room','watch_room','join_invite'}:
            cid = c.community_id
            if kind in {'join_room','watch_room'}:
                room = await self.store.get_room_state(str(msg.get('roomId') or ''))
                cid = room.get('communityId') or 'majlis'
            if kind=='join_invite':
                token=str(msg.get('inviteToken') or '')
                if getattr(self.store,'distributed',False):
                    rid=await self.store.r.get(self.store.kinvite(token))
                else:
                    entry=self.store.invites.get(token);rid=entry[0] if entry else None
                if rid: cid=(await self.store.get_room_state(rid)).get('communityId') or 'majlis'
            await self.platform.community_rules.access(c.account_id,cid)
        if c.account_id and kind=='chat_send':
            await self.platform.community_rules.access(c.account_id,c.community_id,chat=True)
        if kind=='manage_table':
            if c.room_id is None or c.seat is None or c.spectator:raise StoreError('NOT_IN_ROOM','ادخل طاولتك أولًا')
            await self.enforce_action_rate(c,'manage-table',30)
            target=msg.get('targetSeat',-1)
            if type(target) is not int or not -1<=target<=3:raise StoreError('BAD_SEAT','المقعد غير صالح')
            rid=c.room_id
            result=await self.store.manage_waiting_table(rid,c.seat,c.conn_id,c.connection_epoch,str(msg.get('action') or ''),target)
            payload={'type':'left_room',**{k:v for k,v in result.items() if k!='targetNodeId'},
                'message':'أُغلقت الطاولة' if result['reason']=='TABLE_CLOSED' else 'أخرجك منشئ الطاولة قبل بدء اللعب'}
            await self.fanout(rid,payload)
            if result['reason']=='TABLE_KICKED': await self.fanout(rid,await self.room_state_event(rid))
            return
        if kind == "quick_play":
            if c.room_id is not None:
                raise StoreError("ALREADY_IN_ROOM", "الاتصال موجود بالفعل في غرفة")
            await self.enforce_action_rate(c, "create", CREATE_RATE_PER_MINUTE)
            if set(msg) - {"type", "preset", "name"}:
                raise StoreError("INVALID_QUICK_FIELDS", "إعدادات البحث غير صالحة")
            try:
                data, created = await self.quick_play.match(str(msg.get("preset") or ""),
                    self.effective_name(c, msg), NODE_ID, c.conn_id, c.account_id, c.community_id)
            except TimeoutError:
                raise StoreError("MATCHMAKING_BUSY", "تأخر البحث، حاول مجددًا")
            self.attach(c, data)
            await self.send(c, {"type": "created" if created else "joined", **self.public_join_data(data), "quickPlay": True})
            await self.send_chat_history(c)
            await self.fanout(c.room_id, await self.room_state_event(c.room_id))
            if data["started"]:
                await self.maybe_send_start_to_all(c.room_id)
            return

        if kind == "create_room":
            if c.room_id is not None:
                raise StoreError("ALREADY_IN_ROOM", "الاتصال موجود بالفعل في غرفة")
            await self.enforce_action_rate(c, "create", CREATE_RATE_PER_MINUTE)
            raw_settings = dict(msg.get("settings") or {}) if isinstance(msg.get("settings"), dict) else {}
            if "gameId" in msg:
                raw_settings["gameId"] = msg["gameId"]
            settings = sanitize_settings(raw_settings)
            data = await self.store.create_room(self.effective_name(c, msg), settings, NODE_ID, c.conn_id, c.account_id, c.community_id)
            self.attach(c, data)
            await self.send(c, {"type": "created", **self.public_join_data(data)})
            await self.send_chat_history(c)
            await self.fanout(c.room_id, await self.room_state_event(c.room_id))
            return

        if kind == "join_invite":
            if c.room_id is not None:
                raise StoreError("ALREADY_IN_ROOM", "الاتصال موجود بالفعل في غرفة")
            await self.enforce_action_rate(c, "join", JOIN_RATE_PER_MINUTE)
            data = await self.store.join_invite(str(msg.get("inviteToken") or ""), self.effective_name(c, msg), NODE_ID, c.conn_id, c.account_id)
            self.attach(c, data)
            await self.send(c, {"type": "joined", **self.public_join_data(data), "viaInvite": True})
            await self.send_chat_history(c)
            await self.fanout(c.room_id, await self.room_state_event(c.room_id))
            if data["started"]:
                if data.get("justStarted"):
                    await self.maybe_send_start_to_all(c.room_id)
                else:
                    await self.send(c, {"type": "start", **await self._client_start(c.room_id, c.seat)})
            return

        if kind == "join_room":
            if c.room_id is not None:
                raise StoreError("ALREADY_IN_ROOM", "الاتصال موجود بالفعل في غرفة")
            await self.enforce_action_rate(c, "join", JOIN_RATE_PER_MINUTE)
            raw_token = msg.get("token")
            data = await self.store.join_room(str(msg.get("roomId") or ""), self.effective_name(c, msg), raw_token if raw_token else None, NODE_ID, c.conn_id, c.account_id)
            self.attach(c, data)
            # If a match is already authoritative, update GameHost's seat generation
            # before acknowledging the reconnect. Old sockets are rejected after this point.
            if data.get("begun"):
                lease = await self._authority_lease(c.room_id)
                try:
                    await self.gamehost.claim_connection(c.room_id, c.seat, c.connection_epoch, shard=str(lease["shard"]), authority_epoch=int(lease["epoch"]))
                except GameHostError as e:
                    if e.code == "ROOM_NOT_LOADED":
                        authority = await self._ensure_authority(c.room_id, renew=True)
                        lease = authority["lease"]
                        await self.gamehost.claim_connection(c.room_id, c.seat, c.connection_epoch, shard=str(lease["shard"]), authority_epoch=int(lease["epoch"]))
                    else:
                        raise StoreError(e.code, e.message)
            await self.invalidate_replaced_connection(data)
            await self.send(c, {"type": "joined", **self.public_join_data(data)})
            await self.send_chat_history(c)
            await self.fanout(c.room_id, await self.room_state_event(c.room_id))
            if data["started"]:
                if data.get("justStarted"):
                    await self.maybe_send_start_to_all(c.room_id)
                else:
                    await self.send(c, {"type": "start", **await self._client_start(c.room_id, c.seat)})
            return

        if kind == "watch_room":
            if c.room_id is not None:
                raise StoreError("ALREADY_IN_ROOM", "الاتصال موجود بالفعل في غرفة")
            await self.enforce_action_rate(c, "join", JOIN_RATE_PER_MINUTE)
            rid = str(msg.get("roomId") or "")
            start = await self._client_start(rid, -1)
            if start.get("finished"):
                raise StoreError("MATCH_FINISHED", "المباراة انتهت")
            if not start.get("begun"):
                raise StoreError("MATCH_NOT_READY", "المباراة لم تبدأ فعليًا بعد")
            await self.attach_spectator(c, str(start["roomId"]))
            await self.send(c, {
                "type": "watching",
                "roomId": start["roomId"],
                "communityId": start.get("communityId") or c.community_id,
                "seat": -1,
                "spectator": True,
                "capacity": start["capacity"],
                "settings": start["settings"],
                "roster": start["roster"],
                "started": True,
                "begun": True,
            })
            await self.send(c, {"type": "start", **start, "seat": -1, "spectator": True})
            await self.send_chat_history(c)
            return

        if kind == "ping":
            reply = {"type": "pong", "t": msg.get("t"), "node": NODE_ID}
            if c.room_id and msg.get('waiting') is True and await self.store.allow_rate(f'waiting-probe:{c.conn_id}', 1, 3):
                room = await self.room_state_event(c.room_id)
                await self.send(c, room)
                if room['started'] and c.seat is not None:
                    await self.send(c, {'type':'start', **await self._client_start(c.room_id, c.seat)})
                    if room['begun']:
                        await self.send(c, {'type':'begin_match','roomId':c.room_id})
            if c.room_id and msg.get('authority') is True:
                if not await self.store.allow_rate(f'authority-probe:{c.conn_id}', 1, 3):
                    await self.send(c, reply)
                    return
                lease = await self.store.get_authority(c.room_id)
                if lease:
                    try:
                        public_state = await self.gamehost.authority(c.room_id, shard=str(lease['shard']))
                        reply['authority'] = {key: public_state[key] for key in
                            ('roomId','turn','sequence','gameOver','lastValidAnim','nextAlarmId','authorityEpoch','revision') if key in public_state}
                    except GameHostError:
                        reply['syncUnavailable'] = True
            await self.send(c, reply)
            return

        if c.spectator:
            if kind == "resync":
                await self.send(c, {"type": "resync_state", **await self._client_resync(c.room_id, -1 if c.spectator else c.seat)})
                return
            if kind == "chat_history":
                await self.send_chat_history(c)
                return
            if kind == "leave_room":
                rid = c.room_id
                await self.store.remove_spectator(rid, c.conn_id)
                self.room_local[rid].discard(c.conn_id)
                c.room_id = None
                c.seat = None
                c.token = None
                c.connection_epoch = 0
                c.spectator = False
                await self.send(c, {"type": "left_room", "roomId": rid, "spectator": True})
                return
            raise StoreError("SPECTATOR_READ_ONLY", "المشاهدة للقراءة فقط")

        if not c.room_id or c.seat is None:
            raise StoreError("NOT_IN_ROOM", "اللاعب غير موجود في غرفة")

        await self.store.assert_connection(c.room_id, c.seat, c.conn_id, c.connection_epoch)

        if kind == "refresh_cosmetics":
            await self.enforce_action_rate(c, "cosmetics", 30)
            await self.fanout(c.room_id, await self.room_state_event(c.room_id))
            return

        if kind == "chat_send":
            rate_identity = c.peer
            if not await self.store.allow_rate(f"chat:{rate_identity}:{c.room_id}", CHAT_RATE_MESSAGES, CHAT_RATE_WINDOW):
                self.metrics.rate_limited += 1
                raise StoreError("CHAT_RATE_LIMIT", "أرسلت رسائل كثيرة بسرعة؛ حاول بعد قليل")
            text = self.sanitize_chat_text(msg.get("text"))
            user = await self.platform.get_user(c.account_id) if c.account_id else None
            bubble = cosmetic_id((user or {}).get("chatBubble"), "chat_bubble")
            entry = await self.store.append_chat(c.room_id, c.seat, c.conn_id, c.connection_epoch, text, chat_bubble=bubble)
            self.metrics.chat_messages += 1
            await self.fanout(c.room_id, {"type": "chat_message", **entry})
            return

        if kind == "chat_history":
            await self.send_chat_history(c)
            return

        if kind == "create_invite":
            await self.enforce_action_rate(c, "invite", INVITE_RATE_PER_MINUTE)
            invite = await self.store.create_invite(c.room_id, c.seat, c.conn_id, c.connection_epoch, INVITE_TTL_SECONDS)
            await self.send(c, {"type": "invite_created", **invite})
            return

        if kind == "leave_room":
            rid = c.room_id
            seat = int(c.seat)
            result = await self.store.leave_room(rid, seat, c.conn_id, c.connection_epoch)
            self.room_local[rid].discard(c.conn_id)
            c.room_id = None
            c.seat = None
            c.token = None
            c.connection_epoch = 0
            await self.send(c, {"type": "left_room", "roomId": rid, **result})
            if not result.get("roomDeleted"):
                try:
                    await self.fanout(rid, await self.room_state_event(rid))
                except StoreError:
                    pass
            return

        if kind == "runtime_ready":
            # A transient host failure must leave the room retryable. Do not commit
            # the begun flag until the game-specific authoritative runtime exists.
            authority = await self._ensure_authority(c.room_id)
            if not authority.get("server"):
                raise StoreError("AUTHORITY_FAILED", "تعذر تشغيل GameLogic في وضع السيرفر")
            begun = await self.store.runtime_ready(c.room_id, c.seat, c.conn_id, c.connection_epoch)
            if game_id((await self.store.get_room_state(c.room_id))["settings"]) in {"crazy8", "pool"}:
                # Both engines freeze their alarms while clients load. Resume the
                # authority after committing readiness, before announcing begin.
                state = await self.store.get_room_state(c.room_id)
                if state.get("begun"):
                    authority = await self._ensure_authority(c.room_id)
                    begun = True  # Also allows recovery after a transient begin failure.
            await self.fanout(c.room_id, await self.room_state_event(c.room_id))
            if begun:
                # The match cannot begin until the authoritative copy of main.js is alive.
                await self.fanout(c.room_id, {
                    "type": "begin_match", "roomId": c.room_id,
                    "authority": {"server": True, "mainJsSha256": authority.get("mainJsSha256")},
                })
            return

        if kind == "move":
            packet = msg.get("packet")
            if not isinstance(packet, dict):
                raise StoreError("BAD_MOVE", "حركة غير صالحة")

            room_state = await self.store.get_room_state(c.room_id)
            if not room_state.get("begun"):
                raise StoreError("MATCH_NOT_READY", "المباراة لم تصبح جاهزة بعد")

            # Single source of truth: the exact headless main.js decides whether this packet is legal.
            lease = await self._authority_lease(c.room_id)
            host_began = time.monotonic()
            try:
                authority = await self.gamehost.move(
                    c.room_id, c.seat, packet, shard=str(lease["shard"]),
                    authority_epoch=int(lease["epoch"]), connection_epoch=c.connection_epoch,
                )
            except GameHostError as e:
                if e.code == "ROOM_NOT_LOADED":
                    restored = await self._ensure_authority(c.room_id, renew=True)
                    lease = restored["lease"]
                    authority = await self.gamehost.move(
                        c.room_id, c.seat, packet, shard=str(lease["shard"]),
                        authority_epoch=int(lease["epoch"]), connection_epoch=c.connection_epoch,
                    )
                else:
                    raise StoreError(e.code, e.message)

            if not authority.get("accepted"):
                seq = authority.get("sequence") or []
                expected = seq[c.seat] if c.seat < len(seq) else None
                actual = packet.get("n")
                if isinstance(expected, int) and isinstance(actual, int) and actual != expected:
                    self.record_problem(c, 'DESYNC', expectedSequence=expected, packetSequence=actual)
                    await self.send(c, {
                        "type": "desync", "seat": c.seat, "expected": expected,
                        "actual": actual, "moveCount": (await self.store.get_room_state(c.room_id))["moveCount"],
                        "source": "GameLogic",
                    })
                else:
                    context = authority.get("rejectionContext") or {}
                    await self.error(c, "MOVE_REJECTED", "GameLogic رفض الحركة", turn=authority.get("turn") or [],
                        reason=authority.get("rejectionReason") or "RULES_ENGINE_REJECTED",
                        expectedSequence=expected, packetSequence=actual, moveAction=context.get("moveAction"))
                return

            self.observe('gamehost_move', host_began)
            commit_began = time.monotonic()

            official_packet = authority.get("packet") if isinstance(authority.get("packet"), dict) else packet
            info_only = "__info" in official_packet
            if info_only:
                room_state = await self.store.get_room_state(c.room_id)
                move_count = int(room_state.get("moveCount", 0))
                entry = {
                    "seat": c.seat, "packet": official_packet,
                    "moveIndex": move_count, "infoAck": True, "infoOnly": True,
                }
            else:
                try:
                    entry = await self.store.append_move(c.room_id, c.seat, official_packet,
                        authority_epoch=int(lease['epoch']), authority_shard=str(lease['shard']))
                except StoreError as e:
                    # Store sequence is defense-in-depth; GameLogic remains the authority.
                    if e.code == "DESYNC":
                        self.record_problem(c, 'DESYNC')
                        d = json.loads(e.message)
                        await self.send(c, {"type": "desync", "seat": c.seat, **d, "source": "Store"})
                        return
                    raise
                move_count = int(entry["moveIndex"]) + 1

            snapshot = authority.get("snapshot")
            if isinstance(snapshot, dict):
                await self.store.set_snapshot(c.room_id, -1, snapshot, move_count, revision=int(authority.get("authorityRevision", 0) or 0))

            # A normal player move can end the match without producing a separate SSE
            # authority event. Results/rewards are idempotent per account and match.
            if bool(authority.get("gameOver")):
                await self.store.mark_finished(c.room_id)

            self.metrics.moves += 1
            self.observe('commit_move', commit_began)
            payload = {
                "type": "move",
                **{k: v for k, v in entry.items() if k != "infoOnly"},
                "authority": {
                    "turn": authority.get("turn") or [],
                    "sequence": authority.get("sequence") or [],
                    "gameOver": bool(authority.get("gameOver")),
                    "authorityEpoch": authority.get("authorityEpoch"),
                    "revision": authority.get("authorityRevision"),
                    "lastValidAnim": authority.get("lastValidAnim"),
                    **({"pool":authority["pool"]} if "pool" in authority else {}),
                },
            }
            reveal_by_seat = authority.get("revealBySeat") if isinstance(authority.get("revealBySeat"), dict) else {}
            fanout_began = time.monotonic()
            if reveal_by_seat:
                await self.fanout_personalized(c.room_id, payload, reveal_by_seat)
            else:
                await self.fanout(c.room_id, payload)
            self.observe('fanout_move', fanout_began)
            await self._award_profile_wins(c.room_id, authority)
            await self._award_daily_match_rewards(c.room_id, authority)
            return

        if kind == "snapshot":
            # Client snapshots are deliberately non-authoritative. Never write them to Redis.
            await self.send(c, {"type": "snapshot_ignored", "reason": "server_authoritative"})
            return

        if kind == "resync":
            await self.send(c, {"type": "resync_state", **await self._client_resync(c.room_id, -1 if c.spectator else c.seat)})
            return

        raise StoreError("UNKNOWN_MESSAGE", "نوع رسالة غير معروف")

    async def websocket(self, request: web.Request) -> web.StreamResponse:
        origin = request.headers.get("Origin")
        if "*" not in ALLOWED_ORIGINS and origin not in ALLOWED_ORIGINS:
            return web.Response(status=403, text="Origin not allowed")
        peer = self.platform_http._peer(request)
        if not await self.platform.allow_rate(f"ws-connect:{peer}", 120, 60):
            return web.Response(status=429, text="Connection rate exceeded")
        ticket_data = await self.platform.consume_game_ticket(request.query.get("ticket"))
        if not ticket_data:
            session_user = await self.platform.resolve_session(request.cookies.get("samidev_session"))
            if session_user:
                ticket_data = {
                    "uid": session_user.get("id"), "username": session_user.get("username"),
                    "displayName": session_user.get("displayName"), "role": session_user.get("role", "user"),
                    "sessionKey": self.platform.token_key(request.cookies.get("samidev_session")),
                    "authVersion": str(session_user.get("authVersion") or "0"),
                }
        if REQUIRE_GAME_AUTH and not ticket_data:
            return web.Response(status=401, text="Game authentication required")
        if ticket_data and sum(c.account_id == ticket_data.get("uid") for c in self.connections.values()) >= 8:
            return web.Response(status=429, text="Account connection limit")
        ws = web.WebSocketResponse(heartbeat=25, receive_timeout=90, max_msg_size=MAX_WS_MESSAGE, compress=False, autoping=True)
        await ws.prepare(request)
        peer = request.remote or "?"
        if TRUST_PROXY:
            forwarded = request.headers.get("X-Real-IP") or request.headers.get("X-Forwarded-For", "").split(",", 1)[0].strip()
            if forwarded:
                peer = forwarded
        c = Conn(ws=ws, conn_id=secrets.token_urlsafe(12), peer=peer)
        if ticket_data:
            c.account_id = str(ticket_data.get("uid") or "") or None
            c.account_role = str(ticket_data.get("role") or "user")
            c.auth_session_key = ticket_data.get("sessionKey")
            c.auth_version = str(ticket_data.get("authVersion") or "0")
            c.auth_expires_at = time.monotonic() + 3600
            c.community_id = str(ticket_data.get("communityId") or "majlis")[:32]
            c.name = str(ticket_data.get("displayName") or ticket_data.get("username") or "Player")[:24]
        self.connections[c.conn_id] = c
        self.metrics.accepted += 1
        self.metrics.active += 1
        try:
            async for item in ws:
                if item.type == WSMsgType.TEXT:
                    auth_began = time.monotonic()
                    try:
                        authorized = await self.connection_authorized(c)
                    except AuthUnavailable:
                        await self.error(c, 'AUTH_SERVICE_UNAVAILABLE', 'خدمة التوثيق غير متاحة مؤقتًا؛ جارٍ إعادة الاتصال')
                        await ws.close(code=1013, message=b'authentication service unavailable; retry')
                        break
                    self.observe('authenticate_message', auth_began)
                    if not authorized:
                        await ws.close(code=4003, message=b"authentication expired")
                        break
                    self.metrics.messages_in += 1
                    if not c.allow_message():
                        self.metrics.rate_limited += 1
                        await self.error(c, "RATE_LIMIT", "تم تجاوز معدل الرسائل المسموح")
                        continue
                    try:
                        msg = json.loads(item.data)
                        if not isinstance(msg, dict):
                            raise ValueError
                    except Exception:
                        await self.error(c, "BAD_JSON", "رسالة JSON غير صالحة")
                        continue
                    try:
                        await self.handle(c, msg)
                    except (StoreError, PlatformError) as e:
                        await self.error(c, e.code, e.message)
                    except Exception as e:
                        print("[SamiDev] handler error", type(e).__name__, e)
                        await self.error(c, "SERVER_ERROR", "خطأ داخلي في السيرفر")
                elif item.type in (WSMsgType.ERROR, WSMsgType.CLOSE, WSMsgType.CLOSED):
                    break
        finally:
            self.connections.pop(c.conn_id, None)
            self.metrics.active = max(0, self.metrics.active - 1)
            if c.room_id:
                self.room_local[c.room_id].discard(c.conn_id)
                try:
                    if c.spectator:
                        await self.store.remove_spectator(c.room_id, c.conn_id)
                    elif c.seat is not None:
                        await self.store.disconnect(c.room_id, int(c.seat), c.conn_id)
                        await self.fanout(c.room_id, await self.room_state_event(c.room_id))
                except Exception:
                    pass
        return ws

    async def health(self, request: web.Request) -> web.Response:
        redis_ok = True
        if getattr(self.store, "distributed", False):
            try: redis_ok = await asyncio.wait_for(self.store.ping(), timeout=3)
            except Exception: redis_ok = False
        database_ok = True
        if PLATFORM_STORE == "postgres":
            try: database_ok = await asyncio.wait_for(self.platform.r.ping(), timeout=3)
            except Exception: database_ok = False
        streams_ok = all(self.gamehost.event_connected.get(url, False) for url in self.gamehost.base_urls)
        listener_ok = not getattr(self.store, 'distributed', False) or self.redis_listener_ready
        healthy = redis_ok and database_ok and streams_ok and listener_ok
        return web.json_response({"ok": healthy, "service": "SamiDev Realtime", "release": UI_BUILD["release"], "buildId": UI_BUILD["buildId"],
            "storage": {"realtime": STORE_MODE, "platform": PLATFORM_STORE},
            "dependencies": {"redis": redis_ok if STORE_MODE == 'redis' else None,
                "database": database_ok if PLATFORM_STORE == 'postgres' else None,
                "gamehostEvents": streams_ok, "redisSubscription": listener_ok if STORE_MODE == 'redis' else None},
            "production": PRODUCTION_MODE, "node": NODE_ID}, status=200 if healthy else 503)

    async def metrics_endpoint(self, request: web.Request) -> web.Response:
        m = self.metrics
        uptime = max(0.001, time.monotonic() - m.started_at)
        text = "\n".join([
            "# TYPE samidev_connections gauge",
            f"samidev_connections {m.active}",
            "# TYPE samidev_connections_accepted counter",
            f"samidev_connections_accepted {m.accepted}",
            "# TYPE samidev_messages_in counter",
            f"samidev_messages_in {m.messages_in}",
            "# TYPE samidev_messages_out counter",
            f"samidev_messages_out {m.messages_out}",
            "# TYPE samidev_moves counter",
            f"samidev_moves {m.moves}",
            "# TYPE samidev_errors counter",
            f"samidev_errors {m.errors}",
            "# TYPE samidev_rate_limited counter",
            f"samidev_rate_limited {m.rate_limited}",
            "# TYPE samidev_chat_messages counter",
            f"samidev_chat_messages {m.chat_messages}",
            "# TYPE samidev_uptime_seconds gauge",
            f"samidev_uptime_seconds {uptime:.3f}",
            "",
        ])
        text += '# TYPE samidev_errors_by_code counter\n'
        for code, count in sorted(m.errors_by_code.items()):
            text += f'samidev_errors_by_code{{code={json.dumps(code)}}} {count}\n'
        text += f'samidev_listener_reconnects {m.listener_reconnects}\nsamidev_send_timeouts {m.send_timeouts}\n'
        for stage, samples in sorted(m.latencies.items()):
            ordered = sorted(samples)
            if ordered:
                text += f'samidev_stage_recent_p95_ms{{stage={json.dumps(stage)}}} {ordered[min(len(ordered)-1,int(len(ordered)*.95))]:.3f}\n'
        return web.Response(text=text, content_type="text/plain")

    async def client_config(self, request: web.Request) -> web.Response:
        payload = {"inviteTtlSeconds": INVITE_TTL_SECONDS, "production": PRODUCTION_MODE, "chatMaxChars": CHAT_MAX_CHARS, "platformEnabled": True, "requireGameAuth": REQUIRE_GAME_AUTH, "mainJsSha256": MAIN_JS_SHA256, "games": GAME_CATALOG}
        body = "window.__SAMIDEV_CLIENT_CONFIG=" + json.dumps(payload, ensure_ascii=False, separators=(",", ":")) + ";\n"
        return web.Response(text=body, content_type="application/javascript", headers={"Cache-Control": "no-store"})

    async def game_catalog(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True, "games": list(GAME_CATALOG.values())}, headers={"Cache-Control": "no-store"})

    async def ui_build(self, request: web.Request) -> web.Response:
        return web.json_response({"ok": True, **UI_BUILD}, headers={"Cache-Control": "no-store"})

    async def index(self, request: web.Request) -> web.StreamResponse:
        return web.FileResponse(GAME_ROOT / "platform" / "index.html", headers={"Cache-Control": "no-store", "X-SamiDev-Build": UI_BUILD["buildId"]})

    async def platform_redirect(self, request: web.Request) -> web.StreamResponse:
        raise web.HTTPPermanentRedirect("/platform/")

    async def static_game(self, request: web.Request) -> web.StreamResponse:
        rel = request.match_info.get("path", "")
        if any(part.startswith(".") for part in Path(rel).parts):
            raise web.HTTPNotFound()
        path = (GAME_ROOT / rel).resolve()
        if GAME_ROOT.resolve() not in path.parents and path != GAME_ROOT.resolve():
            raise web.HTTPForbidden()
        if not path.is_file():
            raise web.HTTPNotFound()
        suffix = path.suffix.lower()
        cache_control = "no-store" if suffix in {".html", ".js", ".css", ".json"} else "public, max-age=3600"
        return web.FileResponse(path, headers={"Cache-Control": cache_control})


SERVICE = SamiDevRealtime()


def _origin_allowed(origin: str | None) -> bool:
    if not origin:
        return not PRODUCTION_MODE
    return "*" in ALLOWED_ORIGINS or origin in ALLOWED_ORIGINS


@web.middleware
async def platform_origin_middleware(request: web.Request, handler):
    if PRODUCTION_MODE and (request.path.startswith("/api/") or request.path == "/ws") and not SERVICE.platform_http._secure(request):
        return web.json_response({"ok":False,"error":"HTTPS_REQUIRED"},status=426)
    if request.path.startswith("/api/") and request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
        origin = request.headers.get("Origin")
        fetch_site = (request.headers.get("Sec-Fetch-Site") or "").lower()
        if fetch_site == "cross-site" or not _origin_allowed(origin):
            return web.json_response({"ok": False, "error": "ORIGIN_FORBIDDEN", "message": "مصدر الطلب غير مسموح"}, status=403)
    return await handler(request)


@web.middleware
async def platform_error_middleware(request: web.Request, handler):
    try:
        return await handler(request)
    except PlatformError as e:
        return web.json_response({"ok": False, "error": e.code, "message": e.message}, status=e.status)


async def security_headers(request: web.Request, response: web.StreamResponse):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=(), payment=()"
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "private, no-store"
        response.headers["Vary"] = "Cookie, Origin"
    script = "'self'" if request.path.startswith("/platform") or request.path == "/" else "'self' 'unsafe-inline'"
    connect = "'self'"
    frame = "'self'"
    if SERVICE.platform.firebase.enabled and request.path.startswith("/platform"):
        connect += " https://identitytoolkit.googleapis.com https://securetoken.googleapis.com https://apis.google.com"
        script += " https://apis.google.com"
        frame += " https://" + SERVICE.platform.firebase.project + ".firebaseapp.com"
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src " + script + "; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; media-src 'self' blob:; connect-src " + connect + "; frame-src " + frame + "; object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'"
    if PRODUCTION_MODE and SERVICE.platform_http._secure(request):
        response.headers["Strict-Transport-Security"] = "max-age=31536000"


def make_app() -> web.Application:
    app = web.Application(client_max_size=MAX_HTTP_BODY, middlewares=[platform_origin_middleware, platform_error_middleware])
    api = SERVICE.platform_http
    from account_security import AccountSecurityHttp
    AccountSecurityHttp(api).install(app.router)
    app.router.add_post("/api/auth/guest", api.guest)
    app.router.add_post("/api/auth/register", api.register)
    app.router.add_get("/api/auth/config", api.auth_config)
    app.router.add_post("/api/auth/firebase", api.firebase_exchange)
    app.router.add_post("/api/auth/login", api.login)
    app.router.add_post("/api/auth/logout", api.logout)
    app.router.add_get("/api/me", api.me)
    app.router.add_get("/api/games", SERVICE.game_catalog)
    app.router.add_get("/api/build", SERVICE.ui_build)
    app.router.add_get("/api/store", api.store_state)
    app.router.add_post("/api/store/equip", api.store_equip)
    app.router.add_post("/api/store/buy", api.store_buy)
    app.router.add_patch("/api/profile", api.profile_update)
    app.router.add_get("/api/avatar/{user_id}", api.avatar_image)
    app.router.add_post("/api/heartbeat", api.heartbeat)
    app.router.add_get("/api/communities", api.communities)
    app.router.add_get("/api/communities/{community_id}", api.community_state)
    app.router.add_post("/api/communities/{community_id}/enter", api.community_enter)
    app.router.add_post("/api/communities/{community_id}/leave", api.community_leave)
    app.router.add_get("/api/communities/{community_id}/events", api.community_events)
    app.router.add_post("/api/communities/{community_id}/chat", api.community_chat)
    app.router.add_post("/api/communities/{community_id}/moderation", api.community_moderate)
    app.router.add_get("/api/lobby/rooms", api.lobby_rooms)
    app.router.add_post("/api/game-ticket", api.game_ticket)
    app.router.add_get("/api/friends", api.friends)
    app.router.add_post("/api/friends/request", api.friend_request)
    app.router.add_post("/api/friends/respond", api.friend_respond)
    app.router.add_delete("/api/friends/{user_id}", api.friend_remove)
    app.router.add_get("/api/users/search", api.user_search)
    app.router.add_get("/api/public-profile/{user_id}", api.public_profile)
    app.router.add_post("/api/users/{user_id}/reputation", api.reputation_give)
    app.router.add_post("/api/users/{user_id}/report", api.report_user)
    app.router.add_get("/api/admin/users", api.admin_users)
    app.router.add_get("/api/admin/stats", api.admin_stats)
    app.router.add_get("/api/admin/reports", api.admin_reports)
    app.router.add_post("/api/admin/users/{user_id}/ban", api.admin_ban)
    app.router.add_post("/api/admin/users/{user_id}/role", api.admin_role)
    app.router.add_get("/ws", SERVICE.websocket)
    async def close_community_streams(app):
        await SERVICE.platform.live.close()
    app.on_shutdown.append(close_community_streams)
    app.router.add_get("/health", SERVICE.health)
    app.router.add_get("/metrics", SERVICE.metrics_endpoint)
    app.router.add_get("/client-config.js", SERVICE.client_config)
    app.router.add_get("/", SERVICE.index)
    app.router.add_get("/platform", SERVICE.platform_redirect)
    app.router.add_get("/platform/", SERVICE.index)
    app.router.add_get("/{path:.*}", SERVICE.static_game)
    app.on_response_prepare.append(security_headers)
    app.on_startup.append(SERVICE.start)
    app.on_startup.append(SERVICE.platform.deletions.start)
    app.on_shutdown.append(SERVICE.platform.deletions.stop)
    app.on_cleanup.append(SERVICE.stop)
    return app


if __name__ == "__main__":
    try:
        import uvloop
        uvloop.install()
    except Exception:
        pass
    web.run_app(make_app(), host=os.getenv("SAMIDEV_HOST", "0.0.0.0"), port=int(os.getenv("SAMIDEV_PORT", "8088")), access_log=None, print=None)
