"""Version the platform assets and record the exact files the launcher must serve."""
from pathlib import Path
import hashlib
import json
import re

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "game"
ASSETS = ["platform/platform.css", "platform/platform.js", "samidev-games.js"]


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
    files = {rel: hashlib.sha256((GAME / rel).read_bytes()).hexdigest()
             for rel in ["platform/index.html", *ASSETS, "index.html", "browser-runtime.js", "crazy8-audio.js", "game-touch.css", "game-touch.js", "games/tablesoccer/index.html", "games/crazy8/index.html", "games/pool/index.html"]}
    digest = hashlib.sha256(json.dumps(files, sort_keys=True).encode()).hexdigest()[:16]
    manifest = {"release": "V37", "buildId": "samidev-v37-" + digest,
                "games": ["carrom", "tablesoccer", "crazy8", "pool"], "files": files}
    (GAME / "platform/build.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), indent=2))
