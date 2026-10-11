from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

runtime = (ROOT / "game/browser-runtime.js").read_text("utf-8")
menu = (ROOT / "game/room-menu.js").read_text("utf-8")
launcher = (ROOT / "game/launcher.js").read_text("utf-8")
social = (ROOT / "backend/social_platform.py").read_text("utf-8")

# Opponent avatar fetch must not require the platform session cookie. User ids are
# opaque random ids, image-only, same-origin and rate-limited.
avatar_method = re.search(r"async def avatar_image\(self, request: web\.Request\).*?async def profile_update", social, re.S)
assert avatar_method, "avatar_image method not found"
block = avatar_method.group(0)
assert "await self._user(request)" not in block
assert 'allow_rate(f"avatar:{peer}", 240, 60)' in block
assert 'Cross-Origin-Resource-Policy' in block
assert 'X-Robots-Tag' in block

# A failed first request must be retryable during the same match.
assert "profileAvatarTextureCache.delete(cacheKey)" in runtime

# Three-dot exit must submit the native resignation move before leaving the room.
assert "resignOnlineMatch" in runtime
assert "logic.localMove({m:4}, false)" in runtime
assert "m:{m:4}" in runtime
assert "await gameUi()?.resignMatch?.(5000)" in menu
assert "room kept alive" in menu
assert "window.SamiDevRoomUI = {openExit: openConfirm, exitMatch: confirmExit}" in menu
assert "window.SamiDevRoomUI?.openExit" in launcher

print("AVATAR_EXIT_REGRESSION_PASS")
