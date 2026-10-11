from __future__ import annotations

import argparse
import asyncio
import json
import time

import aiohttp


async def recv_type(ws: aiohttp.ClientWebSocketResponse, wanted: set[str], timeout: float = 5.0) -> dict:
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
            return {"type": "closed", "seen": seen}
    raise TimeoutError((wanted, seen))


async def run(ws_url: str, http_url: str) -> dict:
    report: dict[str, object] = {}
    async with aiohttp.ClientSession() as session:
        owner = await session.ws_connect(ws_url)
        await owner.send_json({"type": "create_room", "name": "Inviter", "settings": {"players": 0, "live": 1, "gamemode": 2, "break": 0}})
        created = await recv_type(owner, {"created", "error"})
        report["roomCreated"] = created.get("type") == "created"

        await owner.send_json({"type": "create_invite"})
        invite = await recv_type(owner, {"invite_created", "error"})
        token = str(invite.get("inviteToken") or "")
        report["inviteCreated"] = invite.get("type") == "invite_created" and len(token) >= 20
        report["inviteTtl"] = int(invite.get("expiresIn", 0)) > 0
        report["inviteDoesNotExposeRoom"] = created.get("roomId") not in token

        guest = await session.ws_connect(ws_url)
        await guest.send_json({"type": "join_invite", "inviteToken": token, "name": "Guest"})
        joined = await recv_type(guest, {"joined", "error"})
        report["inviteJoin"] = joined.get("type") == "joined" and joined.get("viaInvite") is True
        report["sameRoom"] = joined.get("roomId") == created.get("roomId")

        replay = await session.ws_connect(ws_url)
        await replay.send_json({"type": "join_invite", "inviteToken": token, "name": "Replay"})
        replay_result = await recv_type(replay, {"joined", "error"})
        report["oneTimeOnly"] = replay_result.get("type") == "error" and replay_result.get("code") == "INVITE_INVALID"

        await owner.send_json({"type": "create_invite"})
        full_result = await recv_type(owner, {"invite_created", "error"})
        report["noInviteAfterFull"] = full_result.get("type") == "error" and full_result.get("code") == "MATCH_STARTED"

        async with session.get(http_url.rstrip("/") + "/client-config.js") as r:
            config_js = await r.text()
            report["clientConfigEndpoint"] = r.status == 200 and "inviteTtlSeconds" in config_js and "production" in config_js
            report["clientConfigNoStore"] = "no-store" in r.headers.get("Cache-Control", "")

        await owner.close(); await guest.close(); await replay.close()

    report["ok"] = all(bool(v) for k, v in report.items() if k != "ok")
    return report


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="ws://127.0.0.1:8088/ws")
    ap.add_argument("--http", default="http://127.0.0.1:8088")
    args = ap.parse_args()
    report = await run(args.url, args.http)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if not report["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    asyncio.run(main())
