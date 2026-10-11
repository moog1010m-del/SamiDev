from __future__ import annotations

import asyncio
import pathlib
import sys
ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from store import MemoryStore, StoreError


async def main() -> None:
    store = MemoryStore()
    settings = {"players": 0, "gamemode": 0, "live": 1, "break": 0}
    created = await store.create_room("Host", settings, "node-a", "conn-a", community_id="majlis")
    rid = created["roomId"]
    await store.join_room(rid, "Guest", None, "node-b", "conn-b")
    await store.runtime_ready(rid, 0, "conn-a", 1)
    begun = await store.runtime_ready(rid, 1, "conn-b", 1)
    assert begun is True

    before = await store.get_room_state(rid)
    assert sum(1 for p in before["roster"] if p.get("name")) == 2
    await store.add_spectator(rid, "node-watch", "spectator-1")
    start = await store.get_start(rid, -1)
    assert start["seat"] == -1
    assert start["begun"] is True
    assert start["finished"] is False
    assert "node-watch" in await store.room_nodes(rid)
    after = await store.get_room_state(rid)
    assert sum(1 for p in after["roster"] if p.get("name")) == 2, "spectator must not consume a player seat"

    await store.mark_finished(rid)
    visible = await store.list_public_rooms(50)
    assert rid not in {x["roomId"] for x in visible}, "finished match must disappear from lobby"
    try:
        await store.add_spectator(rid, "node-watch2", "spectator-2")
    except StoreError as exc:
        assert exc.code == "MATCH_FINISHED"
    else:
        raise AssertionError("finished match accepted a new spectator")

    await store.remove_spectator(rid, "spectator-1")
    print("SPECTATOR_LIFECYCLE_REGRESSION_PASS")


if __name__ == "__main__":
    asyncio.run(main())
