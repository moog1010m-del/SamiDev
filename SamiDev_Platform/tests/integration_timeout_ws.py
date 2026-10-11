from __future__ import annotations

import argparse
import asyncio
import json
import time

import aiohttp


async def recv_until(ws: aiohttp.ClientWebSocketResponse, wanted: str, timeout: float = 40.0) -> tuple[dict, list[dict]]:
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
    raise TimeoutError((wanted, seen[-12:]))


async def run(url: str) -> dict:
    async with aiohttp.ClientSession() as session:
        p0 = await session.ws_connect(url)
        p1 = await session.ws_connect(url)
        try:
            await p0.send_json({"type": "create_room", "name": "P0", "settings": {"players": 0, "gamemode": 0, "live": 1, "break": 0}})
            created, _ = await recv_until(p0, "created", 5)
            rid = created["roomId"]
            await p1.send_json({"type": "join_room", "roomId": rid, "name": "P1"})
            await recv_until(p1, "joined", 5)
            await recv_until(p0, "start", 5)
            await recv_until(p1, "start", 5)
            await p0.send_json({"type": "runtime_ready"})
            await p1.send_json({"type": "runtime_ready"})
            await recv_until(p0, "begin_match", 5)
            await recv_until(p1, "begin_match", 5)

            await p0.send_json({"type": "move", "packet": {"i": "timeout-start", "m": {"m": 0}, "n": 0}})
            await recv_until(p0, "move", 5)
            await recv_until(p1, "move", 5)

            alarm0, _ = await recv_until(p0, "authority_alarm", 35)
            alarm1, _ = await recv_until(p1, "authority_alarm", 5)
            state0, _ = await recv_until(p0, "authority_state", 5)
            state1, _ = await recv_until(p1, "authority_state", 5)

            await p0.send_json({"type": "resync"})
            resync0, _ = await recv_until(p0, "resync_state", 5)

            # The new active player must be able to move immediately after the timeout.
            await p1.send_json({"type": "move", "packet": {"i": "after-timeout", "m": {"m": 6, "ps": 0.75}, "n": 0}})
            move1, _ = await recv_until(p1, "move", 5)
            move0, _ = await recv_until(p0, "move", 5)

            auto0 = alarm0.get("reveal", {}).get("__auto", [])
            auto1 = alarm1.get("reveal", {}).get("__auto", [])
            snapshot = resync0.get("snapshot") if isinstance(resync0.get("snapshot"), dict) else {}
            report = {
                "ok": False,
                "roomId": rid,
                "alarmHasNativeAutoMove": bool(auto0 and auto1 and auto0[0].get("d", {}).get("m") == 3 and auto0[0].get("s") == 0),
                "alarmSequence": alarm0.get("sequence"),
                "serverTurnAfterMissTimer": state0.get("turn"),
                "sameTurnOnBothGateways": state0.get("turn") == state1.get("turn") == [1],
                "resyncSequence": resync0.get("sequence"),
                "resyncSnapshotTurn": snapshot.get("t"),
                "resyncSnapshotSequence": snapshot.get("n"),
                "nextPlayerMoveAccepted": move1.get("packet", {}).get("i") == "after-timeout",
                "sameMoveOnBothClients": move1.get("packet") == move0.get("packet"),
            }
            report["ok"] = all([
                report["alarmHasNativeAutoMove"],
                report["sameTurnOnBothGateways"],
                report["resyncSequence"] == [2, 0],
                report["resyncSnapshotTurn"] == [1],
                report["resyncSnapshotSequence"] == [2, 0],
                report["nextPlayerMoveAccepted"],
                report["sameMoveOnBothClients"],
            ])
            return report
        finally:
            await p0.close()
            await p1.close()


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
