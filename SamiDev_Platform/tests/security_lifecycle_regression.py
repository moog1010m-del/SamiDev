from __future__ import annotations

import argparse
import asyncio
import json
import time

import aiohttp


async def recv_types(ws: aiohttp.ClientWebSocketResponse, wanted: set[str], timeout: float = 6.0) -> dict:
    end = time.monotonic() + timeout
    seen = []
    while time.monotonic() < end:
        msg = await asyncio.wait_for(ws.receive(), end - time.monotonic())
        if msg.type == aiohttp.WSMsgType.TEXT:
            data = json.loads(msg.data)
            seen.append(data)
            if data.get("type") in wanted:
                return data
        elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
            return {"type": "closed", "closeCode": ws.close_code, "seen": seen}
    raise TimeoutError((wanted, seen))


async def run(ws_url: str, gamehost_url: str, service_key: str) -> dict:
    report: dict[str, object] = {}
    async with aiohttp.ClientSession() as session:
        # A: moves before both runtimes are ready must not reach authority.
        a1 = await session.ws_connect(ws_url)
        a2 = await session.ws_connect(ws_url)
        await a1.send_json({"type": "create_room", "name": "A1", "settings": {"players": 0, "live": 1, "gamemode": 0, "break": 0}})
        created = await recv_types(a1, {"created"})
        await a2.send_json({"type": "join_room", "roomId": created["roomId"], "name": "A2"})
        await recv_types(a2, {"joined"})
        await recv_types(a1, {"start"})
        await recv_types(a2, {"start"})
        await a1.send_json({"type": "move", "packet": {"i": "pre-ready", "m": {"m": 0}, "n": 0}})
        pre_ready = await recv_types(a1, {"error"})
        report["preReadyRejected"] = pre_ready.get("code") == "MATCH_NOT_READY"

        # B: one WebSocket cannot create/join a second room while attached.
        await a1.send_json({"type": "create_room", "name": "ghost", "settings": {"players": 0}})
        second_room = await recv_types(a1, {"error"})
        report["secondRoomRejected"] = second_room.get("code") == "ALREADY_IN_ROOM"
        await a1.close(); await a2.close()

        # C: reconnect replaces the old socket and its old epoch at GameHost.
        p1 = await session.ws_connect(ws_url)
        p2 = await session.ws_connect(ws_url)
        await p1.send_json({"type": "create_room", "name": "P1", "settings": {"players": 0, "live": 1, "gamemode": 0, "break": 0}})
        c = await recv_types(p1, {"created"})
        rid, token = c["roomId"], c["token"]
        await p2.send_json({"type": "join_room", "roomId": rid, "name": "P2"})
        await recv_types(p2, {"joined"})
        await recv_types(p1, {"start"}); await recv_types(p2, {"start"})
        await p1.send_json({"type": "runtime_ready"}); await p2.send_json({"type": "runtime_ready"})
        await recv_types(p1, {"begin_match"}); await recv_types(p2, {"begin_match"})

        p1_new = await session.ws_connect(ws_url)
        await p1_new.send_json({"type": "join_room", "roomId": rid, "name": "P1-new", "token": token})
        rejoined = await recv_types(p1_new, {"joined"})
        report["reconnectEpochAdvanced"] = int(rejoined.get("connectionEpoch", 0)) >= 2

        old_result = await recv_types(p1, {"error"}, timeout=2.0)
        report["oldSocketClosed"] = old_result.get("type") == "closed"

        # Directly prove the authoritative host rejects the old generation too.
        async with session.post(
            gamehost_url.rstrip("/") + "/v1/room/move",
            headers={"X-SamiDev-Service-Key": service_key},
            json={"roomId": rid, "seat": 0, "packet": {"i": "old-epoch", "m": {"m": 0}, "n": 0}, "authorityEpoch": 1, "connectionEpoch": 1},
        ) as r:
            stale_body = await r.json()
            report["oldEpochRejectedByGameHost"] = r.status == 409 and stale_body.get("code") == "STALE_CONNECTION"

        await p1_new.send_json({"type": "move", "packet": {"i": "new-epoch", "m": {"m": 0}, "n": 0}})
        new_move = await recv_types(p1_new, {"move", "error"})
        report["newSocketCanMove"] = new_move.get("type") == "move"

        # D: internal mutation endpoints require the service key.
        async with session.get(gamehost_url.rstrip("/") + f"/v1/room/{rid}") as r:
            no_auth = await r.json()
            report["gameHostServiceAuth"] = r.status == 401 and no_auth.get("code") == "SERVICE_AUTH_REQUIRED"

        await p1_new.close(); await p2.close()

    report["ok"] = all(bool(v) for k, v in report.items() if k != "ok")
    return report


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="ws://127.0.0.1:8088/ws")
    ap.add_argument("--gamehost", default="http://127.0.0.1:8091")
    ap.add_argument("--service-key", default="samidev-local-development-key-change-me")
    args = ap.parse_args()
    report = await run(args.url, args.gamehost, args.service_key)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    asyncio.run(main())
