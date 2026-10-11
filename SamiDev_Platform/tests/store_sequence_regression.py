from __future__ import annotations

import asyncio
import json

from backend.store import MemoryStore, sanitize_settings


async def main() -> None:
    store = MemoryStore()
    created = await store.create_room("P1", sanitize_settings({"players": 0, "live": 1, "gamemode": 0, "break": 0}), "node", "c1")
    rid = created["roomId"]
    await store.join_room(rid, "P2", None, "node", "c2")
    await store.runtime_ready(rid, 0, "c1", 1)
    await store.runtime_ready(rid, 1, "c2", 1)

    # One ordinary seat-0 packet is persisted normally.
    await store.append_move(rid, 0, {"i": "start", "m": {"m": 0}, "n": 0})
    before = (await store.get_room_state(rid))["sequence"]

    # GameHost then executes a server-generated m:3 auto move. The gateway must
    # advance its defense-in-depth sequence without inventing a history packet.
    await store.sync_sequence(rid, [2, 0])
    after = (await store.get_room_state(rid))["sequence"]

    # Delayed authority events must never roll sequence backwards.
    await store.sync_sequence(rid, [1, 0])
    after_stale = (await store.get_room_state(rid))["sequence"]

    # The next real packet from seat 0 now uses n=2 and must be accepted by store.
    entry = await store.append_move(rid, 0, {"i": "after-timeout", "m": {"m": 6, "ps": 0.5}, "n": 2})
    final = (await store.get_room_state(rid))["sequence"]

    report = {
        "ok": before == [1, 0] and after == [2, 0] and after_stale == [2, 0] and final == [3, 0],
        "before": before,
        "afterAuthorityAutoMove": after,
        "afterStaleAuthorityEvent": after_stale,
        "nextRealMoveIndex": entry["moveIndex"],
        "final": final,
    }
    print(json.dumps(report, indent=2))
    if not report["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    asyncio.run(main())
