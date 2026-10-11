from __future__ import annotations

import asyncio
import hashlib
import json
import os
from typing import Any, Awaitable, Callable

import aiohttp


class GameHostError(Exception):
    def __init__(self, code: str, message: str, status: int = 500, payload: dict[str, Any] | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.payload = payload or {}


class GameHostClient:
    """Client/router for authoritative GameHost shards.

    A room gets a persisted shard lease + authority epoch in the store. Rendezvous hashing
    is used only when a lease is first created (or explicitly renewed), preventing a shard
    list change from silently creating two authoritative copies of the same room.
    """

    def __init__(self, base_url: str | None = None) -> None:
        raw = os.getenv("SAMIDEV_GAMEHOST_URLS") or base_url or os.getenv("SAMIDEV_GAMEHOST_URL", "http://127.0.0.1:8091")
        self.base_urls = [x.strip().rstrip("/") for x in raw.split(",") if x.strip()]
        if not self.base_urls:
            raise RuntimeError("At least one SamiDev GameHost URL is required")
        self.service_key = os.getenv("SAMIDEV_GAMEHOST_SERVICE_KEY", "samidev-local-development-key-change-me")
        self.session: aiohttp.ClientSession | None = None
        self.listener_tasks: list[asyncio.Task] = []
        self.on_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None

    def shard_for(self, room_id: str) -> str:
        rid = str(room_id or "").upper()
        return max(self.base_urls, key=lambda u: hashlib.sha256(f"{rid}|{u}".encode()).digest())

    def has_shard(self, shard: str) -> bool:
        return shard in self.base_urls

    @property
    def headers(self) -> dict[str, str]:
        return {"X-SamiDev-Service-Key": self.service_key}

    async def start(self, on_event: Callable[[dict[str, Any]], Awaitable[None]] | None = None) -> None:
        self.on_event = on_event
        timeout = aiohttp.ClientTimeout(total=8, connect=2, sock_connect=2, sock_read=6)
        self.session = aiohttp.ClientSession(timeout=timeout, headers=self.headers)
        await self.health()
        if on_event:
            self.listener_tasks = [
                asyncio.create_task(self._listen_events(url), name=f"samidev-gamehost-events-{i}")
                for i, url in enumerate(self.base_urls)
            ]

    async def close(self) -> None:
        for task in self.listener_tasks:
            task.cancel()
        for task in self.listener_tasks:
            try:
                await task
            except (asyncio.CancelledError, Exception):
                pass
        self.listener_tasks.clear()
        if self.session:
            await self.session.close()
            self.session = None

    async def _json(self, method: str, base_url: str, path: str, body: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.session:
            raise GameHostError("GAMEHOST_OFFLINE", "Game Host client is not started")
        try:
            async with self.session.request(method, base_url + path, json=body) as r:
                data = await r.json(content_type=None)
                if r.status >= 400 or not data.get("ok", False):
                    data.setdefault("shard", base_url)
                    raise GameHostError(str(data.get("code") or "GAMEHOST_ERROR"), str(data.get("message") or data.get("error") or "Game Host error"), r.status, data)
                data.setdefault("shard", base_url)
                return data
        except GameHostError:
            raise
        except Exception as e:
            raise GameHostError("GAMEHOST_OFFLINE", f"{base_url}: {e}") from e

    async def health(self) -> dict[str, Any]:
        results = await asyncio.gather(*(self._json("GET", u, "/health") for u in self.base_urls), return_exceptions=True)
        bad = [r for r in results if isinstance(r, Exception)]
        if bad:
            raise GameHostError("GAMEHOST_OFFLINE", "; ".join(str(x) for x in bad))
        return {"ok": True, "shards": results}

    async def ensure_room(
        self,
        room_id: str,
        settings: dict[str, Any],
        capacity: int,
        snapshot: dict[str, Any] | None = None,
        *,
        shard: str | None = None,
        authority_epoch: int = 1,
        connection_epochs: list[int] | None = None,
        begun: bool = False,
    ) -> dict[str, Any]:
        base = shard or self.shard_for(room_id)
        return await self._json("POST", base, "/v1/room/init", {
            "roomId": room_id,
            "settings": settings,
            "capacity": capacity,
            "snapshot": snapshot,
            "authorityEpoch": authority_epoch,
            "connectionEpochs": connection_epochs or [],
            "begun": begun,
        })

    async def claim_connection(self, room_id: str, seat: int, connection_epoch: int, *, shard: str, authority_epoch: int) -> dict[str, Any]:
        return await self._json("POST", shard, "/v1/room/claim-connection", {
            "roomId": room_id,
            "seat": seat,
            "connectionEpoch": connection_epoch,
            "authorityEpoch": authority_epoch,
        })

    async def move(self, room_id: str, seat: int, packet: dict[str, Any], *, shard: str, authority_epoch: int, connection_epoch: int) -> dict[str, Any]:
        return await self._json("POST", shard, "/v1/room/move", {
            "roomId": room_id,
            "seat": seat,
            "packet": packet,
            "authorityEpoch": authority_epoch,
            "connectionEpoch": connection_epoch,
        })

    async def state(self, room_id: str, *, shard: str | None = None) -> dict[str, Any]:
        base = shard or self.shard_for(room_id)
        return await self._json("GET", base, f"/v1/room/{room_id}")

    async def _listen_events(self, base_url: str) -> None:
        backoff = 0.5
        while True:
            try:
                timeout = aiohttp.ClientTimeout(total=None, sock_read=None)
                async with aiohttp.ClientSession(timeout=timeout, headers=self.headers) as s:
                    async with s.get(base_url + "/events") as r:
                        if r.status != 200:
                            raise RuntimeError(f"events status={r.status}")
                        backoff = 0.5
                        async for raw in r.content:
                            line = raw.decode("utf-8", "replace").strip()
                            if not line.startswith("data:"):
                                continue
                            try:
                                event = json.loads(line[5:].strip())
                            except Exception:
                                continue
                            if self.on_event and isinstance(event, dict) and event.get("type") != "hello":
                                event.setdefault("shard", base_url)
                                try:
                                    await self.on_event(event)
                                except Exception as e:
                                    print("[SamiDev GameHost] event handler", type(e).__name__, e)
            except asyncio.CancelledError:
                raise
            except Exception as e:
                print("[SamiDev GameHost] event stream", base_url, type(e).__name__, e)
                await asyncio.sleep(backoff)
                backoff = min(5.0, backoff * 1.8)
