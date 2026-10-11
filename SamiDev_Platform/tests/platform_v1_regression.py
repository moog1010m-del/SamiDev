from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

os.environ.setdefault("SAMIDEV_REQUIRE_GAME_AUTH", "1")
os.environ.setdefault("SAMIDEV_STORE", "memory")

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from aiohttp.test_utils import TestClient, TestServer
import app as mod


async def _fake_start(_cb=None):
    return None


async def _fake_close():
    return None


async def main() -> None:
    mod.SERVICE.gamehost.start = _fake_start
    mod.SERVICE.gamehost.close = _fake_close
    client = TestClient(TestServer(mod.make_app()))
    await client.start_server()
    try:
        registered = await client.post(
            "/api/auth/register",
            json={"username": "platform_test", "password": "Test-password-123", "displayName": "Platform Test"},
        )
        assert registered.status == 200, await registered.text()
        user = (await registered.json())["user"]
        assert user["displayName"] == "Platform Test"

        me = await client.get("/api/me")
        assert me.status == 200

        ticket_response = await client.post("/api/game-ticket", json={})
        ticket = (await ticket_response.json())["ticket"]
        assert ticket

        ws = await client.ws_connect(f"/ws?ticket={ticket}")
        await ws.send_json({
            "type": "create_room",
            "name": "Spoofed Name",
            "settings": {"players": 0, "gamemode": 0, "live": 1, "break": 0},
        })
        created = None
        for _ in range(6):
            message = await ws.receive(timeout=2)
            if message.type.name != "TEXT":
                continue
            payload = json.loads(message.data)
            if payload.get("type") == "created":
                created = payload
                break
        assert created, "create_room did not emit created"

        lobby = await client.get("/api/lobby/rooms")
        rooms = (await lobby.json())["rooms"]
        room = next(x for x in rooms if x["roomId"] == created["roomId"])
        assert room["hostName"] == "Platform Test", room
        assert room["occupied"] == 1

        # The ticket was one-time, but the session cookie keeps authenticated reconnects working.
        ws2 = await client.ws_connect("/ws")
        await ws2.send_json({"type": "ping", "t": 123})
        pong = json.loads((await ws2.receive(timeout=2)).data)
        assert pong["type"] == "pong"

        await ws.close()
        await ws2.close()
        print(json.dumps({"ok": True, "roomId": created["roomId"], "hostName": room["hostName"]}, ensure_ascii=False))
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
