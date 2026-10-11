"""Complete the V29 -> V30 text patch with the reviewed existing currency image.

The full V30 ZIP already contains the new image; running this there is a no-op.
No download, resizing, atlas edits or engine changes are performed.
"""
from pathlib import Path
import hashlib

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT/'game/scene-ui/ShopWidget/shop_widget_coin.webp'
TARGET = ROOT/'game/games/pool/scene-ui/ShopWidget/shop_widget_coin.webp'
PREVIOUS = 'aaf5d8a652df8b557f6ee5a3ae04f6a5a846d1bd346331e5e41e31e23d762013'


def main():
    import json
    entry = json.loads((ROOT/'POOL_ORIGINAL_ASSETS.json').read_text())['brandReplacements'][0]
    data = SOURCE.read_bytes()
    expected = entry['sha256']
    if hashlib.sha256(data).hexdigest() != expected:
        raise SystemExit('Source asset differs from the reviewed V30 image; no files changed.')
    current = hashlib.sha256(TARGET.read_bytes()).hexdigest()
    if current == expected:
        print('V30 currency artwork already applied.')
        return
    if current != PREVIOUS:
        raise SystemExit('Target has custom changes; no files changed. Review this image manually.')
    TARGET.write_bytes(data)
    print('V30 currency artwork applied. Run Flutter tool/sync_assets.py before building the app.')


if __name__ == '__main__':
    main()
