import asyncio
import base64
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from store import MemoryStore  # noqa: E402


async def main():
    store = MemoryStore()
    settings = {"players": 0, "live": 1, "gamemode": 0, "break": 0}
    room = await store.create_room("Avatar A", settings, "n1", "c1", "acct-a")
    await store.join_room(room["roomId"], "Avatar B", None, "n1", "c2", "acct-b")

    state = await store.get_room_state(room["roomId"])
    roster = [p for p in state["roster"] if p and p.get("name")]
    assert {p.get("accountId") for p in roster} == {"acct-a", "acct-b"}

    # Public lobby must not expose account identifiers.
    public = await store.list_public_rooms()
    for item in public:
        for p in item.get("roster", []):
            assert "accountId" not in p

    runtime = (ROOT / "game/browser-runtime.js").read_text("utf-8")
    assert "profileAvatarTexture" in runtime
    assert "/api/avatar/" in runtime
    assert "refreshNativeAvatars" in runtime
    assert "state.avatarsReady(info)" in runtime
    print("profile_game_avatar_regression: PASS")


if __name__ == "__main__":
    asyncio.run(main())
