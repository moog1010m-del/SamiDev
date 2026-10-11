import asyncio
import base64
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from social_platform import PlatformError, PlatformService, normalize_avatar_data, public_user  # noqa: E402

# 1x1 PNG, enough to verify server-side type/magic/size handling.
PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
)
DATA = "data:image/png;base64," + base64.b64encode(PNG).decode("ascii")


def test_avatar_validation():
    assert normalize_avatar_data(DATA) == DATA
    try:
        normalize_avatar_data("data:image/png;base64," + base64.b64encode(b"not-png").decode("ascii"))
    except PlatformError as exc:
        assert exc.code == "BAD_AVATAR"
    else:
        raise AssertionError("invalid image content was accepted")


async def test_profile_store():
    svc = PlatformService()
    user = await svc.create_user("profile_test", "Test-password-123", "Profile Test")
    assert "avatarData" not in public_user(user)
    updated = await svc.update_profile(str(user["id"]), avatar_data=DATA, update_avatar=True)
    own = public_user(updated, include_avatar=True)
    assert own["avatarData"] == DATA
    assert own["createdAt"] > 0
    assert own["accountAgeDays"] == 0
    assert own["wins"] == 0
    assert own["reputation"] == 0
    assert await svc.increment_wins(str(user["id"])) == 1
    own = public_user(await svc.get_user(str(user["id"])), include_avatar=True)
    assert own["wins"] == 1


def test_frontend_contract():
    html = (ROOT / "game/platform/index.html").read_text("utf-8")
    js = (ROOT / "game/platform/platform.js").read_text("utf-8")
    css = (ROOT / "game/platform/platform.css").read_text("utf-8")
    runtime = (ROOT / "game/browser-runtime.js").read_text("utf-8")
    sheet = (ROOT / "game/platform/assets/profile/profile-sheet.svg").read_text("utf-8")
    combined = (html + js + css).lower()
    assert "SamiDev" not in combined
    assert "SamiDev" not in combined
    assert "لاعب منذ" in html or "لاعب منذ" in js
    assert html.count('profile-sprite-star') == 5
    assert 'profile-sprite-emblem' in html
    assert 'profile-sprite-trophy' in html
    assert 'profile-sprite-calendar' in html
    assert 'profile-sprite-reputation' in html
    assert 'id="profile-wins"' in html
    assert 'id="profile-reputation"' in html
    assert 'id="profile-since-value"' in html
    assert 'id="profile-avatar-image"' in html
    assert 'id="profile-edit-toggle"' in html
    assert 'id="profile-editor"' in html
    assert 'aria-hidden="true"' in html
    assert 'id="profile-display-input"' in html
    assert 'accept="image/*"' in html
    assert html.count('data-avatar-preset=') == 5
    assert "presetAvatarData" in js
    assert "saveAvatarData" in js
    assert "playerSinceValue" in js
    assert "accountAgeDays" in js
    assert "86400000" in js  # backwards-compatible fallback only
    assert "/api/profile" in js
    assert ".profile-workspace" in css
    assert ".profile-editor.open" in css
    assert ".profile-stats" in css
    assert "profile-sheet.svg" in css
    assert 'id="star"' in sheet and 'id="trophy"' in sheet and 'id="emblem"' in sheet
    assert "profile-wins" in js
    assert "profile-reputation" in js
    # The native game avatar path must use the authenticated profile avatar.
    assert "/api/avatar/" in runtime
    assert "setOnAvatarsReadyListener" in runtime
    assert "refreshNativeAvatars" in runtime
    assert "accountId" in runtime


if __name__ == "__main__":
    test_avatar_validation()
    asyncio.run(test_profile_store())
    test_frontend_contract()
    print("profile_ui_regression: PASS")
