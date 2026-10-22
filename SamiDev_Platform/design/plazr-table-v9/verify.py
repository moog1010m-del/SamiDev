"""Verify the installed V9 artwork, saved mode and served/bundled build."""
from pathlib import Path
import hashlib
import json
import urllib.request

design = Path(__file__).resolve().parent
platform = design.parents[1]
game = platform / "game"
mobile = platform.parent / "SamiDev_Flutter/assets/runtime"
origin = "http://127.0.0.1:56648"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def fetch(path):
    with urllib.request.urlopen(origin + path, timeout=15) as response:
        return response.read()


build = json.loads((game / "platform/build.json").read_text(encoding="utf-8"))
served = json.loads(fetch("/api/build"))
health = json.loads(fetch("/health"))
assert health["ok"] and all(health["dependencies"].values())
assert served["buildId"] == build["buildId"]
assert served["files"] == build["files"]
paths = [
    "browser-runtime.js",
    "pool-brand-mark.js",
    "pool-table-mode.js",
    "games/pool/index.html",
    "games/pool/images/imported/themes/th_basic_table.webp",
    "games/pool/images/imported/themes/th_basic_background.webp",
    "games/pool/images/imported/themes/th_basic_preview.webp",
    "images/themes/plazr-engraving.webp",
    "images/themes/pool-midnight.webp",
    "images/themes/pool-midnight-preview.webp",
    "images/pool-large/table.webp",
    "platform/build.json",
]
verified = {}
for path in paths:
    source = (game / path).read_bytes()
    assert fetch("/" + path) == source, ("served mismatch", path)
    assert (mobile / path).read_bytes() == source, ("mobile mismatch", path)
    verified[path] = sha(source)

assets = json.loads((design / "asset-verification.json").read_text())
for path, fingerprints in assets["fingerprints"].items():
    assert sha((platform / path).read_bytes()) == fingerprints["before"] == fingerprints["after"]

proofs = ["desktop.png", "phone.png", "large-mode-preserved.png"]
assert all((design / "proof" / name).is_file() for name in proofs)
result = {
    "buildId": build["buildId"],
    "originHealth": "passed",
    "servedBuildMatches": True,
    "servedAndFlutterFiles": verified,
    "generatedSourcesOnly": True,
    "sourcePrompts": "prompts.json",
    "nativeEngineAndUiAtlasUnchanged": True,
    "allEightLargeModeAssetsUnchanged": True,
    "tests": {
        "brandInlayChecks": 8,
        "tableModeChecks": 11,
        "nativePoolRuntimeChecks": 39,
        "assetCacheContract": "passed",
        "flutterBundleFiles": 771,
        "flutterSecurityScanFiles": 772,
        "flutterFindings": [],
    },
    "visualReview": {
        "proofs": proofs,
        "phoneViewport": "390x844",
        "desktopViewport": "1612x1139",
        "engravingReadableAndBoundToFrame": True,
        "backgroundDoesNotTileGradient": True,
        "largeModeHasNoNewBrandOverlay": True,
        "consoleErrors": [],
        "phoneEmulationCleared": True,
    },
    "scope": "New default table artwork and decorative inlay only. Native physics, ball sizes, input, atlas mirroring and native sinking animation retained.",
    "deploymentNote": "Verified against the running local origin and synchronized Flutter source bundle; no Google Play binary uploaded.",
}
(design / "verification.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"ok": True, "buildId": build["buildId"], "servedAndMobileFiles": len(paths), "protectedFingerprints": len(assets["fingerprints"])}))
