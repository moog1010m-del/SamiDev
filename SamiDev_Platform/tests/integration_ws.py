from __future__ import annotations

import argparse
import asyncio
import json
import time

import aiohttp


async def recv_until(ws: aiohttp.ClientWebSocketResponse, wanted: str, timeout: float = 8.0) -> tuple[dict, list[dict]]:
    end = time.monotonic() + timeout
    seen: list[dict] = []
    while time.monotonic() < end:
        msg = await asyncio.wait_for(ws.receive(), end - time.monotonic())
        if msg.type != aiohttp.WSMsgType.TEXT:
            continue
        data = json.loads(msg.data)
        seen.append(data)
        if data.get("type") == wanted:
            return data, seen
    raise TimeoutError((wanted, seen))


async def run(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        p1 = await session.ws_connect(url)
        p2 = await session.ws_connect(url)
        try:
            await p1.send_json({"type": "create_room", "name": "P1", "settings": {"players": 0, "gamemode": 0, "live": 1, "break": 0}})
            created, _ = await recv_until(p1, "created")
            room_id = created["roomId"]
            await p2.send_json({"type": "join_room", "roomId": room_id, "name": "P2"})
            joined, _ = await recv_until(p2, "joined")
            await recv_until(p1, "start")
            await recv_until(p2, "start")
            await p1.send_json({"type": "runtime_ready"})
            await p2.send_json({"type": "runtime_ready"})
            begin1, _ = await recv_until(p1, "begin_match")
            await recv_until(p2, "begin_match")

            legal = {"i": "integration-start", "m": {"m": 0}, "n": 0}
            await p1.send_json({"type": "move", "packet": legal})
            move1, _ = await recv_until(p1, "move")
            move2, _ = await recv_until(p2, "move")

            await p2.send_json({"type": "move", "packet": {"i": "wrong-turn", "m": {"m": 6, "ps": 0}, "n": 0}})
            rejected, _ = await recv_until(p2, "error")

            await p2.send_json({"type": "snapshot", "state": {"hacked": True}, "moveCount": 999})
            ignored, _ = await recv_until(p2, "snapshot_ignored")

            await p2.send_json({"type": "resync"})
            resync, _ = await recv_until(p2, "resync_state")

            report = {
                "ok": True,
                "roomId": room_id,
                "seats": [created["seat"], joined["seat"]],
                "authorityBegin": begin1.get("authority"),
                "legalMoveAuthority": move1.get("authority"),
                "sameMoveOnBothClients": move1.get("packet") == move2.get("packet"),
                "wrongTurnRejected": rejected.get("code") == "MOVE_REJECTED",
                "clientSnapshotIgnored": ignored.get("reason") == "server_authoritative",
                "resyncHasServerSnapshot": isinstance(resync.get("snapshot"), dict),
                "resyncSequence": resync.get("sequence"),
                "maliciousSnapshotPersisted": bool(isinstance(resync.get("snapshot"), dict) and resync["snapshot"].get("hacked")),
            }
            report["ok"] = all([
                report["sameMoveOnBothClients"], report["wrongTurnRejected"],
                report["clientSnapshotIgnored"], report["resyncHasServerSnapshot"],
                not report["maliciousSnapshotPersisted"],
            ])
            return report
        finally:
            await p1.close()
            await p2.close()


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="ws://127.0.0.1:8088/ws")
    args = ap.parse_args()
    report = await run(args.url)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    asyncio.run(main())
