"""Check shipped runtime branding without rewriting source or legal notices.

Policy names below are intentional audit data, outside game/ and the APK assets.
This check is not a license, provenance or visual-similarity certification.
"""
from pathlib import Path
import argparse
import hashlib
import html
import json
import re
import unicodedata
from urllib.parse import unquote

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / 'game'
# Stable engine/translation keys (e.g. deadred/booblue) are not display labels.
MARKERS = ('plato', 'ocho', 'بلاتو', 'أوتشو', 'اوتشو', 'dead red', 'boo blue', 'rouge mort', 'rojo muerto', 'أحمر ميت', 'بو بلو', 'デッドレッド', 'ブーブルー')
RETIRED_MEDIA = {
    'aaf5d8a652df8b557f6ee5a3ae04f6a5a846d1bd346331e5e41e31e23d762013': 'retired P currency icon',
}
ESCAPES = re.compile(r'\\u\{([0-9a-fA-F]{1,6})\}|\\u([0-9a-fA-F]{4})|\\x([0-9a-fA-F]{2})')


def normalized(text):
    def decode(match):
        number = int(next(value for value in match.groups() if value is not None), 16)
        return chr(number) if number <= 0x10FFFF else match.group(0)
    text = ESCAPES.sub(decode, text)
    text = html.unescape(unquote(text))
    text = unicodedata.normalize('NFKC', text).casefold()
    return ''.join(c for c in text if c != 'ـ' and unicodedata.category(c) not in ('Cf', 'Mn'))


def audit(root):
    root = Path(root)
    if not root.is_dir() or not (root / 'samidev-games.js').is_file():
        raise ValueError('Expected the complete game/ directory or synchronized runtime bundle')
    findings, count = [], 0
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.suffix.lower() in ('.apk', '.zip'):
            continue
        count += 1
        relative = path.relative_to(root).as_posix()
        data = path.read_bytes()
        digest = hashlib.sha256(data).hexdigest()
        if digest in RETIRED_MEDIA:
            findings.append({'file': relative, 'kind': 'retired-media', 'detail': RETIRED_MEDIA[digest]})
        values = [normalized(relative)]
        for encoding in ('utf-8', 'utf-16le', 'utf-16be'):
            try:
                values.append(normalized(data.decode(encoding)))
            except UnicodeError:
                pass
        matches = sorted({marker for marker in MARKERS if
            any(marker in value for value in values) or
            any(marker.encode(encoding).lower() in data.lower() for encoding in ('utf-8', 'utf-16le', 'utf-16be'))})
        if matches:
            findings.append({'file': relative, 'kind': 'retired-name', 'markers': matches})
    return {'ok': not findings, 'filesScanned': count, 'findings': findings}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    args = parser.parse_args()
    result = audit(args.root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result['ok'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
