import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app import SamiDevRealtime  # noqa: E402
from social_platform import public_user  # noqa: E402


async def main():
    realtime = SamiDevRealtime()
    a = await realtime.platform.create_user("winner_a", "Test-password-123", "Winner A")
    b = await realtime.platform.create_user("winner_b", "Test-password-123", "Winner B")
    settings = {"players": 0, "live": 1, "gamemode": 0, "break": 0}
    room = await realtime.store.create_room("Winner A", settings, "n1", "c1", str(a["id"]))
    joined = await realtime.store.join_room(room["roomId"], "Winner B", None, "n1", "c2", str(b["id"]))
    assert joined["started"] is True

    event = {"gameOver": True, "finishOrder": [[0], [1]], "teams": [[0], [1]]}
    assert realtime._winner_seats_from_authority(event) == [0]
    await realtime._award_profile_wins(room["roomId"], event)
    # A second post-game authority revision must not double-count the match.
    await realtime._award_profile_wins(room["roomId"], event)

    a_now = public_user(await realtime.platform.get_user(str(a["id"])))
    b_now = public_user(await realtime.platform.get_user(str(b["id"])))
    assert a_now["wins"] == 1
    assert b_now["wins"] == 0

    team_event = {"gameOver": True, "finishOrder": [[0], [1]], "teams": [[0, 2], [1, 3]]}
    assert realtime._winner_seats_from_authority(team_event) == [0, 2]
    print("profile_win_stats_regression: PASS")


if __name__ == "__main__":
    asyncio.run(main())
