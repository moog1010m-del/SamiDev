"""Regression test for V37 Profile Stickers and Stars System.
- Name badge cosmetics (slot: name_badge, single-slot constraint).
- Profile stars stackable up to 5 purchases (slot: profile_stars, maxQuantity: 5).
- Grandfathering rule: legacy accounts keep 5 stars.
- Store catalog categories, buy endpoint, ledger recording.
"""
import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from social_platform import PlatformService, PlatformError, public_user, STORE_CATALOG, STORE_DEFAULT_EQUIPPED


def test_catalog_spec():
    assert "badge_palm_swords" not in STORE_CATALOG
    assert "badge_shard" in STORE_CATALOG
    assert "badge_ember" in STORE_CATALOG
    assert "profile_star" in STORE_CATALOG

    crown = STORE_CATALOG["badge_shard"]
    assert crown["slot"] == "name_badge"
    assert crown["category"] == "profile"
    assert crown["price"] == 150

    fire = STORE_CATALOG["badge_ember"]
    assert fire["slot"] == "name_badge"
    assert fire["category"] == "profile"
    assert fire["price"] == 150

    star = STORE_CATALOG["profile_star"]
    assert star["slot"] == "profile_stars"
    assert star["category"] == "profile"
    assert star["price"] == 50
    assert star["maxQuantity"] == 5

    assert STORE_DEFAULT_EQUIPPED.get("name_badge") == ""


async def test_service_flow():
    svc = PlatformService(None)

    # 1. Grandfathering
    legacy_user = {"id": "legacy_99", "username": "oldtimer", "displayName": "عضو قديم", "wins": "5"}
    pub_legacy = public_user(legacy_user)
    assert pub_legacy["starsCount"] == 5, "Legacy user without starsCount must have 5 stars"
    assert pub_legacy["nameBadge"] == ""

    # 2. New user
    new_user = await svc.create_user("new_tester", "SamiDevPass12345!", "عضو جديد")
    uid = str(new_user["id"])
    pub_new = public_user(new_user)
    assert pub_new["starsCount"] == 0, "New user starts with 0 stars"
    assert pub_new["nameBadge"] == ""

    # 3. Snapshot with 0 coins
    snap = await svc.store_snapshot(uid)
    assert snap["coins"] == 0
    assert snap["starsCount"] == 0

    # 4. Buy star without coins
    try:
        await svc.buy_store_item(uid, "profile_star")
        assert False, "Should fail without coins"
    except PlatformError as e:
        assert e.code == "STORE_INSUFFICIENT_COINS"

    # 5. Grant coins and buy 5 stars
    svc.mem_users[uid]["coins"] = "1000"
    for i in range(1, 6):
        res = await svc.buy_store_item(uid, "profile_star")
        assert res["starsCount"] == i
        assert res["coins"] == 1000 - (i * 50)

    user_updated = await svc.get_user(uid)
    assert public_user(user_updated)["starsCount"] == 5

    # 6. Buying 6th star is capped
    try:
        await svc.buy_store_item(uid, "profile_star")
        assert False, "6th star must fail"
    except PlatformError as e:
        assert e.code == "STORE_STAR_MAX"

    # 7. Buy and equip crown badge
    await svc.buy_store_item(uid, "badge_shard")
    eq1 = await svc.equip_store_item(uid, "badge_shard")
    assert eq1["name_badge"] == "badge_shard"
    user_updated = await svc.get_user(uid)
    assert public_user(user_updated)["nameBadge"] == "badge_shard"

    # 8. Buy and equip fire badge (replaces crown)
    await svc.buy_store_item(uid, "badge_ember")
    eq2 = await svc.equip_store_item(uid, "badge_ember")
    assert eq2["name_badge"] == "badge_ember"
    user_updated = await svc.get_user(uid)
    assert public_user(user_updated)["nameBadge"] == "badge_ember"

    # 9. Equipped badges count must always be 1
    equipped_badges = [v for k, v in eq2.items() if k == "name_badge"]
    assert len(equipped_badges) == 1

    # Removed free art cannot be restored through an old ID.
    try:
        await svc.equip_store_item(uid, "badge_palm_swords")
        raise AssertionError("Removed free badge was equipped")
    except PlatformError as error:
        assert error.code == "STORE_ITEM_NOT_FOUND"
    assert public_user(await svc.get_user(uid))["nameBadge"] == "badge_ember"


def test_ui_contract():
    game_profile_ui = (ROOT / "game/player-profile-ui.js").read_text("utf-8")
    platform_html = (ROOT / "game/platform/index.html").read_text("utf-8")
    platform_js = (ROOT / "game/platform/platform.js").read_text("utf-8")
    platform_css = (ROOT / "game/platform/platform.css").read_text("utf-8")

    # In-game profile contract
    assert "badgeMarkup" in game_profile_ui
    assert "starsMarkup" in game_profile_ui
    assert "sdpp-emblem" in game_profile_ui
    assert "sdpp-icon-star" in game_profile_ui
    assert ".sdpp-stars .sdpp-icon-star.dim" in game_profile_ui

    # Platform store contract
    assert "store-category-bar" in platform_html
    assert "store-category-btn" in platform_html
    assert "data-category=\"profile\"" in platform_html
    assert "buyStoreItem" in platform_js
    assert "/api/store/buy" in platform_js
    assert "store-item-btn-buy" in platform_css
    assert ".profile-sprite-star.dim" in platform_css


if __name__ == "__main__":
    test_catalog_spec()
    asyncio.run(test_service_flow())
    test_ui_contract()
    print("ALL V37 PROFILE STICKERS AND STARS TESTS PASSED!")
