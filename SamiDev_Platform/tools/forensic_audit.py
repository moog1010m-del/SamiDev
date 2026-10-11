#!/usr/bin/env python3
from __future__ import annotations

import csv
import hashlib
import json
import re
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FILES = [
    'game/browser-runtime.js',
    'game/samidev-network.js',
    'game/chat-ui.js',
    'backend/app.py',
    'backend/store.py',
    'backend/gamehost_client.py',
    'gamehost/runtime.js',
    'gamehost/server.js',
    'game/main.js',
    'deploy/nginx/nginx.conf',
]
TERMS = [
    'turn', 'sequence', 'authority', 'revision', 'resync', 'snapshot',
    'surfaceChanged', '_syncCalledFlag', 'resize', 'ResizeObserver',
    'requestAnimationFrame', 'setTimeout', 'setInterval', 'alarm',
    'WebSocket', 'EventSource', '/events', 'fanout', 'publish', 'catch', 'except', 'return',
]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def newline_kind(raw_line: bytes) -> str:
    if raw_line.endswith(b'\r\n'):
        return 'CRLF'
    if raw_line.endswith(b'\n'):
        return 'LF'
    if raw_line.endswith(b'\r'):
        return 'CR'
    return 'NONE'


def text_without_newline(raw_line: bytes) -> str:
    core = raw_line.rstrip(b'\r\n')
    return core.decode('utf-8', 'replace')


def flags_for(text: str) -> str:
    low = text.lower()
    found = []
    for term in TERMS:
        if term.lower() in low:
            found.append(term)
    return ';'.join(found)


def main() -> None:
    ledger_path = ROOT / 'FORENSIC_LINE_LEDGER.csv'
    manifest_path = ROOT / 'FORENSIC_FILE_MANIFEST.json'
    cross_path = ROOT / 'FORENSIC_CROSS_REFERENCE.txt'
    main_zone_path = ROOT / 'FORENSIC_MAINJS_ZONE.txt'

    manifest = {'root': str(ROOT), 'files': [], 'totals': {}}
    total_bytes = 0
    total_lines = 0
    cross_lines = []

    with ledger_path.open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow([
            'file','line','byte_start','byte_end_exclusive','raw_bytes','newline',
            'sha256_raw_line','flags','preview'
        ])
        for rel in FILES:
            p = ROOT / rel
            data = p.read_bytes()
            raw_lines = data.splitlines(keepends=True)
            # splitlines() returns [] for empty file; preserve an exact zero-line count.
            byte_offset = 0
            lf = crlf = cr = none = 0
            controls = []
            cf_chars = []
            decoded = data.decode('utf-8', 'replace')
            for idx, raw in enumerate(raw_lines, 1):
                nk = newline_kind(raw)
                lf += nk == 'LF'; crlf += nk == 'CRLF'; cr += nk == 'CR'; none += nk == 'NONE'
                text = text_without_newline(raw)
                preview = text.replace('\t', '\\t')[:180]
                w.writerow([
                    rel, idx, byte_offset, byte_offset + len(raw), len(raw), nk,
                    sha(raw), flags_for(text), preview
                ])
                for term in TERMS:
                    if term.lower() in text.lower():
                        cross_lines.append(f'{rel}:{idx}: [{term}] {preview}')
                byte_offset += len(raw)
            for i, ch in enumerate(decoded):
                cat = unicodedata.category(ch)
                if cat == 'Cf':
                    cf_chars.append({'char_index': i, 'codepoint': f'U+{ord(ch):04X}', 'name': unicodedata.name(ch, '?')})
                if ord(ch) < 32 and ch not in '\n\r\t':
                    controls.append({'char_index': i, 'codepoint': ord(ch)})
            entry = {
                'file': rel,
                'bytes': len(data),
                'lines': len(raw_lines),
                'sha256': sha(data),
                'bom_utf8': data.startswith(b'\xef\xbb\xbf'),
                'nul_bytes': data.count(b'\x00'),
                'newlines': {'LF': lf, 'CRLF': crlf, 'CR': cr, 'NONE': none},
                'unexpected_ascii_controls': controls,
                'unicode_format_chars': cf_chars,
            }
            manifest['files'].append(entry)
            total_bytes += len(data)
            total_lines += len(raw_lines)

    manifest['totals'] = {
        'files': len(FILES),
        'bytes': total_bytes,
        'lines': total_lines,
        'ledger_rows': total_lines,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    cross_path.write_text('\n'.join(cross_lines) + '\n', encoding='utf-8')

    # main.js is generated/minified. Record exact offsets + local context for every mechanism
    # used by the diagnosed turn race while the complete file is still covered by the byte ledger.
    main_js = (ROOT / 'game/main.js').read_text(encoding='utf-8', errors='replace')
    needles = [
        'surfaceChange=function',
        'this._syncCalledFlag=!1',
        'this.onSync=t=>',
        'animationCompleted(t=!1)',
        'SamiDev.setTimer(()=>{this._syncCalledFlag',
        'nextTurnAfterShotCompleted',
    ]
    zone = [
        'SamiDev main.js forensic zone',
        'whole_file_sha256=' + sha((ROOT / 'game/main.js').read_bytes()),
        '',
    ]
    for needle in needles:
        start = 0
        hits = []
        while True:
            i = main_js.find(needle, start)
            if i < 0:
                break
            hits.append(i)
            start = i + 1
        zone.append(f'NEEDLE {needle!r} HITS {hits}')
        for i in hits:
            a = max(0, i - 280)
            b = min(len(main_js), i + len(needle) + 650)
            snippet = main_js[a:b]
            zone.append(f'  OFFSET {i} RANGE {a}:{b} SHA256 {hashlib.sha256(snippet.encode()).hexdigest()}')
            zone.append('  ' + snippet.replace('\n', '\\n'))
        zone.append('')
    main_zone_path.write_text('\n'.join(zone), encoding='utf-8')

    print(json.dumps(manifest['totals'], indent=2))
    print(ledger_path)
    print(manifest_path)
    print(cross_path)
    print(main_zone_path)


if __name__ == '__main__':
    main()
