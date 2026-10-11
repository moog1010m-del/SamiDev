from __future__ import annotations

import argparse
import asyncio
import json
import statistics
import time
from dataclasses import dataclass

import aiohttp


@dataclass
class RoomResult:
    ok: bool
    setup_ms: float = 0.0
    move_ms: float = 0.0
    error: str = ""


async def recv_type(ws: aiohttp.ClientWebSocketResponse, wanted: set[str], timeout: float = 15.0) -> dict:
    end = asyncio.get_running_loop().time() + timeout
    while True:
        left = end - asyncio.get_running_loop().time()
        if left <= 0:
            raise TimeoutError(f"waiting for {wanted}")
        msg = await asyncio.wait_for(ws.receive(), left)
        if msg.type == aiohttp.WSMsgType.TEXT:
            data = json.loads(msg.data)
            if data.get("type") in wanted:
                return data
            if data.get("type") == "error":
                raise RuntimeError(f"server: {data}")
        elif msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.CLOSED, aiohttp.WSMsgType.ERROR):
            raise RuntimeError("websocket closed")


async def game_room(session: aiohttp.ClientSession, ws_url: str, idx: int, seats: int, hold: float, sem: asyncio.Semaphore) -> RoomResult:
    async with sem:
        sockets: list[aiohttp.ClientWebSocketResponse] = []
        t0 = time.perf_counter()
        try:
            owner = await session.ws_connect(ws_url, heartbeat=20, compress=0, max_msg_size=65536)
            sockets.append(owner)
            await owner.send_json({"type": "create_room", "name": f"P1-{idx}", "settings": {"live": 1, "players": 0 if seats == 2 else 1, "gamemode": 0, "break": 0}})
            created = await recv_type(owner, {"created"})
            room = created["roomId"]

            for seat in range(1, seats):
                ws = await session.ws_connect(ws_url, heartbeat=20, compress=0, max_msg_size=65536)
                sockets.append(ws)
                await ws.send_json({"type": "join_room", "name": f"P{seat+1}-{idx}", "roomId": room})
                joined = await recv_type(ws, {"joined"})
                if joined.get("seat") != seat:
                    raise RuntimeError(f"seat mismatch: expected {seat}, got {joined.get('seat')}")

            # Once the final player joins, every player receives start.
            await asyncio.gather(*(recv_type(ws, {"start"}) for ws in sockets))
            setup_ms = (time.perf_counter() - t0) * 1000

            for ws in sockets:
                await ws.send_json({"type": "runtime_ready"})
            await asyncio.gather(*(recv_type(ws, {"begin_match"}) for ws in sockets))

            tm = time.perf_counter()
            await owner.send_json({"type": "move", "packet": {"n": 0, "i": f"load-{idx}", "m": {"m": 0}}})
            moves = await asyncio.gather(*(recv_type(ws, {"move"}) for ws in sockets))
            if any(m.get("moveIndex") != 0 for m in moves):
                raise RuntimeError("bad move index")
            move_ms = (time.perf_counter() - tm) * 1000

            if hold:
                await asyncio.sleep(hold)
            return RoomResult(True, setup_ms, move_ms)
        except Exception as e:
            return RoomResult(False, error=f"{type(e).__name__}: {e}")
        finally:
            await asyncio.gather(*(ws.close() for ws in sockets), return_exceptions=True)


async def main() -> None:
    ap = argparse.ArgumentParser(description="SamiDev Authoritative Realtime concurrent WebSocket load test")
    ap.add_argument("--url", default="ws://127.0.0.1:8088/ws")
    ap.add_argument("--players", type=int, default=1000)
    ap.add_argument("--seats", type=int, choices=(2, 4), default=2, help="players per room")
    ap.add_argument("--concurrency", type=int, default=100, help="concurrent rooms being created")
    ap.add_argument("--hold", type=float, default=1.0)
    args = ap.parse_args()
    if args.players < args.seats or args.players % args.seats:
        raise SystemExit(f"--players must be divisible by --seats ({args.seats})")
    rooms = args.players // args.seats
    sem = asyncio.Semaphore(args.concurrency)
    timeout = aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=45)
    connector = aiohttp.TCPConnector(limit=0, ttl_dns_cache=300)
    started = time.perf_counter()
    async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
        results = await asyncio.gather(*(game_room(session, args.url, i, args.seats, args.hold, sem) for i in range(rooms)))
    elapsed = time.perf_counter() - started
    ok = [r for r in results if r.ok]
    bad = [r for r in results if not r.ok]
    print(f"players={args.players} seats={args.seats} rooms={rooms} ok_rooms={len(ok)} failed_rooms={len(bad)} elapsed={elapsed:.2f}s")
    if ok:
        for label, xs in (("setup_ms", [r.setup_ms for r in ok]), ("move_fanout_ms", [r.move_ms for r in ok])):
            xs_sorted = sorted(xs)
            p95 = xs_sorted[min(len(xs_sorted)-1, int(len(xs_sorted)*0.95))]
            print(f"{label}: avg={statistics.mean(xs):.2f} p50={statistics.median(xs):.2f} p95={p95:.2f} max={max(xs):.2f}")
    if bad:
        print("first_errors:")
        for r in bad[:10]:
            print(" -", r.error)
        raise SystemExit(2)


if __name__ == "__main__":
    asyncio.run(main())
