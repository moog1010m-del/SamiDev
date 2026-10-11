from __future__ import annotations

import argparse
import asyncio
import json
import time

import aiohttp


async def recv_type(ws: aiohttp.ClientWebSocketResponse, wanted: set[str], timeout: float = 5.0) -> dict:
    end = time.monotonic() + timeout
    seen: list[dict] = []
    while time.monotonic() < end:
        msg = await asyncio.wait_for(ws.receive(), end - time.monotonic())
        if msg.type == aiohttp.WSMsgType.TEXT:
            data = json.loads(msg.data)
            seen.append(data)
            if data.get("type") in wanted:
                return data
        elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
            return {"type": "closed", "seen": seen}
    raise TimeoutError((wanted, seen))


async def run(ws_url: str) -> dict:
    report: dict[str, object] = {}
    async with aiohttp.ClientSession() as session:
        owner = await session.ws_connect(ws_url)
        guest = await session.ws_connect(ws_url)
        try:
            await owner.send_json({"type": "create_room", "name": "Owner", "settings": {"players": 0, "live": 1, "gamemode": 2, "break": 0}})
            created = await recv_type(owner, {"created", "error"})
            report["roomCreated"] = created.get("type") == "created"
            rid = str(created.get("roomId") or "")

            await guest.send_json({"type": "join_room", "roomId": rid, "name": "Guest"})
            joined = await recv_type(guest, {"joined", "error"})
            report["guestJoined"] = joined.get("type") == "joined"
            guest_token = str(joined.get("token") or "")

            await recv_type(owner, {"start"})
            await recv_type(guest, {"start"})

            await owner.send_json({"type": "chat_send", "text": "مرحبا من الويب"})
            owner_msg = await recv_type(owner, {"chat_message", "error"})
            guest_msg = await recv_type(guest, {"chat_message", "error"})
            report["chatReplicated"] = owner_msg.get("type") == "chat_message" and guest_msg.get("id") == owner_msg.get("id")
            report["chatSeatTrusted"] = owner_msg.get("seat") == 0 and "name" not in owner_msg

            await guest.send_json({"type": "chat_history"})
            history = await recv_type(guest, {"chat_history", "error"})
            report["historyAvailable"] = any(m.get("id") == owner_msg.get("id") for m in history.get("messages", []))

            await guest.close()
            guest2 = await session.ws_connect(ws_url)
            try:
                await guest2.send_json({"type": "join_room", "roomId": rid, "token": guest_token, "name": "Guest Reconnected"})
                rejoined = await recv_type(guest2, {"joined", "error"})
                history2 = await recv_type(guest2, {"chat_history", "error"})
                report["reconnectByPlayerToken"] = rejoined.get("type") == "joined" and int(rejoined.get("connectionEpoch", 0)) >= 2
                report["historyAfterReconnect"] = any(m.get("id") == owner_msg.get("id") for m in history2.get("messages", []))
            finally:
                await guest2.close()
        finally:
            await owner.close()
            if not guest.closed:
                await guest.close()

    report["ok"] = all(bool(v) for k, v in report.items() if k != "ok")
    return report


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
