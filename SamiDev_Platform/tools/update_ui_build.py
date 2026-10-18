"""Version the platform assets and record the exact files the launcher must serve."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "game"
ASSETS = ["platform/game-entry.js", "platform/game-preload.js", "platform/desktop-layout.css", "platform/settings.css", "platform/account-settings.js", "platform/firebase-auth.js","cosmetic-ui.css","cosmetic-ui.js","platform/store.css","sticker-art.js","platform/platform.css", "platform/profile-identity.css", "platform/platform.js", "platform/community-live.js", "platform/game-host.js", "samidev-games.js", "profile-details.css", "profile-details.js"]


def build() -> dict:
    index = GAME / "platform/index.html"
    html = index.read_text(encoding="utf-8")
    for rel in ASSETS:
        digest = hashlib.sha256((GAME / rel).read_bytes()).hexdigest()[:16]
        html, count = re.subn(
            r'(["\'])/' + re.escape(rel) + r'(?:\?[^"\']*)?(["\'])',
            lambda m: m[1] + "/" + rel + "?v=" + digest + m[2], html,
        )
        if count != 1:
            raise RuntimeError(f"Expected one asset reference for {rel}; got {count}")
    index.write_bytes(html.encode("utf-8"))
    # Invalidate game-shell caches when transport or resource guards change.
    for entry in ["index.html", "games/tablesoccer/index.html", "games/crazy8/index.html", "games/pool/index.html"]:
        shell = GAME / entry
        text = shell.read_text(encoding="utf-8")
        for rel in ["browser-runtime.js", "samidev-network.js", "profile-details.js", "profile-details.css", "player-profile-ui.js", "cosmetic-ui.js", "cosmetic-ui.css", "sticker-art.js", "chat-ui.js", "room-menu.js", "web-bridge.js", "samidev-games.js", "launcher.js"]:
            version = hashlib.sha256((GAME / rel).read_bytes()).hexdigest()[:16]
            text, count = re.subn(r'(["\'])(/?)' + re.escape(rel) + r'(?:\?[^"\']*)?(["\'])',
                                 lambda m: m[1] + m[2] + rel + "?v=" + version + m[3], text)
            if count != 1:
                raise RuntimeError(f"Expected one {rel} reference in {entry}; got {count}")
        shell.write_text(text, encoding="utf-8")
    from build_game_bootstrap import build as build_game_bootstrap
    build_game_bootstrap()
    from build_asset_cache import build as build_asset_cache
    build_asset_cache()
    files = {rel: hashlib.sha256((GAME / rel).read_bytes()).hexdigest()
             for rel in ["platform/assets/brand/app-icon.svg", "platform/assets/brand/mark-gradient.svg", "platform/assets/brand/apple-touch-icon.png", "asset-worker.js", "platform/index.html", "platform/account-deletion.html", "platform/account-deletion.js", *ASSETS, "index.html", "browser-runtime.js", "game-bootstrap.js", "game-host.html", "runtime-games.json", "web-bridge.js", "room-menu.js", "launcher.js", "match-reward-ui.js", "chat-ui.js", "chat-polish.css", "games/crazy8/uno-table.css", "samidev-network.js", "player-profile-ui.js", "crazy8-audio.js", "game-touch.css", "game-touch.js", "games/tablesoccer/index.html", "games/crazy8/index.html", "games/pool/index.html"]}
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:16]
    manifest = {"release": "V37", "buildId": "samidev-v37-" + digest,
                "games": ["carrom", "tablesoccer", "crazy8", "pool"], "files": files}
    (GAME / "platform/build.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
