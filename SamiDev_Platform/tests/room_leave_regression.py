from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from store import MemoryStore, StoreError, sanitize_settings  # noqa: E402


async def main() -> None:
    store = MemoryStore()
    settings = sanitize_settings({"players": 0, "live": 1, "gamemode": 0, "break": 0})

    # Before begin: an explicit exit must free the seat and allow a replacement.
    a = await store.create_room("A", settings, "node-a", "conn-a")
    b = await store.join_room(a["roomId"], "B", None, "node-b", "conn-b")
    assert b["seat"] == 1
    assert (await store.get_room_state(a["roomId"]))["started"] is True
    left = await store.leave_room(a["roomId"], 1, "conn-b", b["connectionEpoch"])
    assert left == {"roomDeleted": False, "seatFreed": True}
    st = await store.get_room_state(a["roomId"])
    assert st["started"] is False
    assert st["roster"][1]["name"] is None
    c = await store.join_room(a["roomId"], "C", None, "node-c", "conn-c")
    assert c["seat"] == 1

    # Once authoritative play begins: keep the seat identity but invalidate reconnect ownership.
    await store.runtime_ready(a["roomId"], 0, "conn-a", a["connectionEpoch"])
    await store.runtime_ready(a["roomId"], 1, "conn-c", c["connectionEpoch"])
    assert (await store.get_room_state(a["roomId"]))["begun"] is True
    token_c = c["token"]
    left2 = await store.leave_room(a["roomId"], 1, "conn-c", c["connectionEpoch"])
    assert left2 == {"roomDeleted": False, "seatFreed": False}
    st2 = await store.get_room_state(a["roomId"])
    assert st2["roster"][1]["name"] == "C"
    assert st2["roster"][1]["connected"] is False
    try:
        await store.join_room(a["roomId"], "C", token_c, "node-c", "conn-c2")
    except StoreError as e:
        assert e.code == "MATCH_STARTED", e.code
    else:
        raise AssertionError("explicit leave token unexpectedly reconnected to begun match")

    # An empty waiting room is deleted immediately.
    solo = await store.create_room("Solo", settings, "node-s", "conn-s")
    left3 = await store.leave_room(solo["roomId"], 0, "conn-s", solo["connectionEpoch"])
    assert left3 == {"roomDeleted": True, "seatFreed": True}
    try:
        await store.get_room_state(solo["roomId"])
    except StoreError as e:
        assert e.code == "ROOM_NOT_FOUND"
    else:
        raise AssertionError("empty explicit-left room still exists")

    print("ROOM_LEAVE_REGRESSION_PASS")


if __name__ == "__main__":
    asyncio.run(main())
