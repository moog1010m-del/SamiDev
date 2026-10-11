"""Generate 100 original, scalable SamiDev compass-star rank badges."""
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / 'game/platform/assets/ranks'
PALETTES = [('#69848b','#e7f2f3'),('#957358','#f5d2ac'),('#389083','#b0ecd2'),
            ('#37799a','#acdff5'),('#6c62a2','#e4ccff'),('#a16b8b','#ffd3e4'),
            ('#b78b38','#fff0a9'),('#bc644d','#ffdbc0'),('#419597','#c9ffff'),('#ae8738','#fff8d4')]
NAMES = ['بداية','وميض','شعاع','نجم','مدار','شهاب','مجرة','سديم','قطب','قمة']


def badge(level):
    tier, step = (level - 1) // 10, (level - 1) % 10 + 1
    dark, light = PALETTES[tier]
    rays = [5, 5, 6, 6, 8, 8, 9, 9, 10, 10][tier]
    points = []
    for i in range(rays * 2):
        angle = -math.pi / 2 + i * math.pi / rays
        radius = 56 if i % 2 == 0 else 30 + step / 3
        points.append(f'{80 + math.cos(angle) * radius:.2f},{78 + math.sin(angle) * radius:.2f}')
    marks = []
    for i in range(step):
        angle = math.pi * (0.18 + i * 0.064)
        x, y = 80 + 61 * math.cos(angle), 78 + 61 * math.sin(angle)
        marks.append(f'<circle cx="{x:.2f}" cy="{y:.2f}" r="2.5" fill="{light}"/>')
    ornaments = ''.join(f'<path d="M {x} 74 l -10 -12 l 10 -12" fill="none" stroke="{light}" stroke-width="2" opacity=".8"/>' for x in ([22,138] if tier >= 5 else []))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="160" height="160" viewBox="0 0 160 160" role="img" aria-labelledby="title-{level}">
<title id="title-{level}">SamiDev · {NAMES[tier]} · المستوى {level}</title>
<defs><linearGradient id="metal-{level}" x2=".7" y2="1"><stop stop-color="{light}"/><stop offset=".48" stop-color="{dark}"/><stop offset="1" stop-color="{light}"/></linearGradient><radialGradient id="core-{level}"><stop stop-color="#224349"/><stop offset="1" stop-color="#08181f"/></radialGradient></defs>
<path d="M80 10 L137 45 L146 104 L80 148 L14 104 L23 45Z" fill="#08191e" stroke="{dark}" stroke-width="2"/>
<path d="M80 17 L130 48 L139 100 L80 140 L21 100 L30 48Z" fill="none" stroke="{light}" opacity=".32"/>
{ornaments}<polygon points="{' '.join(points)}" fill="url(#metal-{level})" stroke="{light}" stroke-width="1.7"/>
<path d="M80 28 L83 53 L80 48 L77 53Z" fill="white" opacity=".65"/>
<circle cx="80" cy="78" r="28" fill="url(#core-{level})" stroke="{light}" stroke-width="2"/>
<circle cx="80" cy="78" r="23" fill="none" stroke="{dark}" opacity=".65"/>
<text x="80" y="88" text-anchor="middle" font-family="system-ui,sans-serif" font-size="{28 if level < 100 else 23}" font-weight="850" fill="{light}">{level}</text>
{''.join(marks)}<path d="M74 134 L80 126 L86 134 L80 140Z" fill="{light}"/>
</svg>'''


def main():
    ROOT.mkdir(parents=True, exist_ok=True)
    for level in range(1, 101):
        (ROOT / f'level-{level:03}.svg').write_text(badge(level), encoding='utf-8')
    gallery = '''<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>نجوم SamiDev · 1–100</title><style>body{background:#08181f;color:#eef5ef;font:16px system-ui;margin:24px}h1{margin-bottom:6px}p{color:#a7c6c3}.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(100px,1fr));gap:12px;max-width:1200px;margin:auto}.grid img{width:100%;height:auto;background:#10282e;border-radius:18px}header{max-width:1200px;margin:0 auto 24px}</style><header><h1>نجوم SamiDev</h1><p>100 تصميم أصلي · عشرة مسارات لونية · الرتبة تُكتسب بالفوز</p></header><main class="grid">'''
    gallery += ''.join(f'<img src="assets/ranks/level-{i:03}.svg" alt="المستوى {i}" loading="lazy">' for i in range(1, 101))
    (ROOT.parent.parent / 'ranks.html').write_text(gallery + '</main></html>', encoding='utf-8')


if __name__ == '__main__': main()
