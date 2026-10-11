from __future__ import annotations

import asyncio
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from social_platform import (  # noqa: E402
    MATCH_REWARD_COINS,
    MATCH_REWARD_DAILY_LIMIT,
    STORE_CATALOG,
    PlatformError,
    PlatformService,
    public_user,
)


async def make_user(service: PlatformService, suffix: str):
    return await service.create_user(f"store_{suffix}", "Test-password-123", f"Store {suffix}")


async def main() -> None:
    assert MATCH_REWARD_COINS == 50, MATCH_REWARD_COINS
    assert MATCH_REWARD_DAILY_LIMIT == 5, MATCH_REWARD_DAILY_LIMIT
    assert set(STORE_CATALOG) == {"carrom_classic", "carrom_cat", "pool_midnight", "pool_emerald", "crazy8_original", "soccer_original"}
    assert all(item["price"] == 0 and item["availableToAll"] for item in STORE_CATALOG.values())

    tz = ZoneInfo("Asia/Riyadh")
    day1 = int(datetime(2026, 10, 4, 12, 0, tzinfo=tz).timestamp() * 1000)
    day2 = int(datetime(2026, 10, 5, 12, 0, tzinfo=tz).timestamp() * 1000)

    service = PlatformService(None)
    user = await make_user(service, "basic")
    uid = str(user["id"])

    results = []
    for i in range(1, 8):
        results.append(await service.award_daily_match_coins(uid, f"ROOM{i}", at_ms=day1 + i))
    assert [x["awarded"] for x in results] == [True, True, True, True, True, False, False]
    assert results[4]["coins"] == 250
    assert results[5]["remainingMatches"] == 0

    duplicate = await service.award_daily_match_coins(uid, "ROOM1", at_ms=day1 + 999)
    assert duplicate["awarded"] is False and duplicate["duplicate"] is True
    assert duplicate["coins"] == 250

    snapshot = await service.store_snapshot(uid, at_ms=day1)
    assert snapshot["coins"] == 250
    assert snapshot["dailyReward"]["rewardedMatches"] == 5
    assert snapshot["dailyReward"]["remainingMatches"] == 0
    assert snapshot["dailyReward"]["maxCoins"] == 250
    assert len(snapshot["ledger"]) == 5
    assert all(row["type"] == "daily_match_reward" and row["amount"] == 50 for row in snapshot["ledger"])
    assert "coins" not in public_user(await service.get_user(uid) or {}), "wallet balance must not leak through public profiles"

    next_day = await service.award_daily_match_coins(uid, "NEXT01", at_ms=day2)
    assert next_day["awarded"] is True
    assert next_day["coins"] == 300
    day2_snapshot = await service.store_snapshot(uid, at_ms=day2)
    assert day2_snapshot["dailyReward"]["rewardedMatches"] == 1
    assert day2_snapshot["dailyReward"]["remainingMatches"] == 4

    # Race regression: many distinct completed matches arriving together must still cap at five rewards.
    race_user = await make_user(service, "race")
    race_uid = str(race_user["id"])
    race = await asyncio.gather(*[
        service.award_daily_match_coins(race_uid, f"RACE{i:02d}", at_ms=day1 + i)
        for i in range(20)
    ])
    assert sum(1 for x in race if x["awarded"]) == 5
    assert (await service.store_snapshot(race_uid, at_ms=day1))["coins"] == 250

    # Match integration rewards every registered participant, not only the winner.
    from app import SamiDevRealtime  # noqa: E402

    p1 = await make_user(service, "participant1")
    p2 = await make_user(service, "participant2")
    class FakeRoomStore:
        async def account_ids_for_room(self, room_id):
            assert room_id == "ABCDEF"
            return {0: str(p1["id"]), 1: str(p2["id"])}
    runtime = object.__new__(SamiDevRealtime)
    runtime.store = FakeRoomStore()
    runtime.platform = service
    await runtime._award_daily_match_rewards("ABCDEF", {"gameOver": True})
    assert (await service.store_snapshot(str(p1["id"]))) ["coins"] == 50
    assert (await service.store_snapshot(str(p2["id"]))) ["coins"] == 50
    await runtime._award_daily_match_rewards("ABCDEF", {"gameOver": True})
    assert (await service.store_snapshot(str(p1["id"]))) ["coins"] == 50
    assert (await service.store_snapshot(str(p2["id"]))) ["coins"] == 50

    # Client-facing equip path cannot manufacture ownership or arbitrary item ids.
    try:
        await service.equip_store_item(uid, "forged_item")
    except PlatformError as exc:
        assert exc.code == "STORE_ITEM_NOT_FOUND"
    else:
        raise AssertionError("forged item was accepted")

    app_source = (ROOT / "backend" / "app.py").read_text()
    platform_source = (ROOT / "backend" / "social_platform.py").read_text()
    ui_source = (ROOT / "game" / "platform" / "platform.js").read_text()
    html_source = (ROOT / "game" / "platform" / "index.html").read_text()
    assert 'add_get("/api/store", api.store_state)' in app_source
    assert 'add_post("/api/store/equip", api.store_equip)' in app_source
    assert "/api/store/grant" not in app_source and "/api/store/coins" not in app_source
    assert "award_daily_match_coins" in app_source and "gameOver" in app_source
    assert "HINCRBY" in platform_source and "match-claim" in platform_source
    assert "localStorage" not in platform_source[platform_source.index("async def award_daily_match_coins"):platform_source.index("async def create_session")]
    assert "page-store" in html_source and "/api/store" in ui_source

    print("store_rewards_v23_regression: OK")


if __name__ == "__main__":
    asyncio.run(main())
