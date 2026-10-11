from __future__ import annotations

import asyncio
import json

from backend.store import MemoryStore, sanitize_settings


async def main() -> None:
    store = MemoryStore()
    created = await store.create_room("P1", sanitize_settings({"players": 0}), "g1", "c1")
    rid = created["roomId"]
    await store.join_room(rid, "P2", None, "g2", "c2")
    await store.runtime_ready(rid, 0, "c1", 1)
    await store.runtime_ready(rid, 1, "c2", 1)

    lease1 = await store.claim_authority(rid, "http://gh1", renew=False)
    first = await store.accept_authority_event(rid, "http://gh1", lease1["epoch"], 1)
    duplicate = await store.accept_authority_event(rid, "http://gh1", lease1["epoch"], 1)
    wrong_shard = await store.accept_authority_event(rid, "http://gh2", lease1["epoch"], 2)

    await store.set_snapshot(rid, -1, {"version": "new"}, 0, revision=5)
    await store.set_snapshot(rid, -1, {"version": "old"}, 0, revision=4)
    snap = await store.resync(rid)

    lease2 = await store.claim_authority(rid, "http://gh2", renew=True)
    old_epoch = await store.accept_authority_event(rid, "http://gh1", lease1["epoch"], 99)
    new_epoch = await store.accept_authority_event(rid, "http://gh2", lease2["epoch"], 1)

    report = {
        "firstAccepted": first,
        "duplicateRejected": not duplicate,
        "wrongShardRejected": not wrong_shard,
        "newerSnapshotPreserved": snap.get("snapshot", {}).get("version") == "new",
        "epochAdvanced": lease2["epoch"] == lease1["epoch"] + 1,
        "oldEpochRejected": not old_epoch,
        "newEpochAccepted": new_epoch,
    }
    report["ok"] = all(report.values())
    print(json.dumps(report, indent=2))
    if not report["ok"]:
        raise SystemExit(2)


if __name__ == "__main__":
    asyncio.run(main())
