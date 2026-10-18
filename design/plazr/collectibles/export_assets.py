"""Original inanimate Plazr badges. Export independent transparent PNGs for both clients.

SVGs are the editable originals; the old atlas is regenerated only for historical
message compatibility. This does not crop or redistribute reference screenshots.
"""
from pathlib import Path
import json
import subprocess

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OUT = ROOT / 'SamiDev_Platform/game/platform/assets/stickers'
DEFS = '''<defs>
<linearGradient id="ice" x2=".8" y2="1"><stop stop-color="#edfeff"/><stop offset=".45" stop-color="#a1edff"/><stop offset="1" stop-color="#5794df"/></linearGradient>
<linearGradient id="opal" x2=".8" y2="1"><stop stop-color="#f2e9ff"/><stop offset=".4" stop-color="#9ee8ee"/><stop offset=".7" stop-color="#b0b0ed"/><stop offset="1" stop-color="#5c91b9"/></linearGradient>
<linearGradient id="gold" x2=".8" y2="1"><stop stop-color="#fff2ae"/><stop offset=".5" stop-color="#f2bd58"/><stop offset="1" stop-color="#b97631"/></linearGradient>
<linearGradient id="violet" x2=".8" y2="1"><stop stop-color="#eedbff"/><stop offset=".5" stop-color="#b79be9"/><stop offset="1" stop-color="#735bc5"/></linearGradient>
<linearGradient id="aqua" x2=".7" y2="1"><stop stop-color="#d5fff1"/><stop offset=".45" stop-color="#40d7cc"/><stop offset="1" stop-color="#158fa7"/></linearGradient>
<linearGradient id="coral" x2=".8" y2="1"><stop stop-color="#ffd29e"/><stop offset=".55" stop-color="#ff826f"/><stop offset="1" stop-color="#d34462"/></linearGradient>
<linearGradient id="silver" x2=".8" y2="1"><stop stop-color="#fcfdff"/><stop offset=".5" stop-color="#cfdfec"/><stop offset="1" stop-color="#8697c2"/></linearGradient>
</defs>'''

SNOW = ''.join(f'<g transform="rotate({angle} 64 64)"><path d="M64 64V18M64 37 51 26M64 37 77 26M64 52 49 41M64 52 79 41"/></g>' for angle in range(0,360,60))
BADGES = [
 ('badge_crown','أوبال الضوء','قطرة أوبال بلمعة لؤلؤية هادئة.',
  '<path d="M64 14C55 32 29 51 29 78a35 35 0 0 0 70 0C99 51 73 32 64 14Z" fill="url(#opal)" stroke="#749db6" stroke-width="3"/><path d="M61 32C47 48 38 64 39 79c1 9 7 18 14 20" fill="none" stroke="#f6ffff" stroke-width="6" stroke-linecap="round" opacity=".8"/><path d="M73 49c14 20 17 38 5 48M53 58c-10 14-3 28 10 29" fill="none" stroke="#d3bde9" stroke-width="5" stroke-linecap="round"/><path d="m99 25 2 6 6 2-6 2-2 6-2-6-6-2 6-2Z" fill="#b5ebf1"/>'),
 ('badge_orbit','هلال الفضة','هلال فضي ولمعة بنفسجية صغيرة.',
  '<path d="M86 19a45 45 0 1 0 23 65A38 38 0 0 1 86 19Z" fill="url(#silver)" stroke="#899bc0" stroke-width="3"/><path d="M44 28C21 50 24 83 44 98" fill="none" stroke="#f7fbff" stroke-width="4" stroke-linecap="round"/><path d="m91 33 4 10 11 3-11 4-4 11-4-11-10-4 10-3Z" fill="url(#violet)" stroke="#8b79b4" stroke-width="2"/>'),
 ('badge_shell','ندفة الجليد','ستة أذرع بلورية، بحضور خفيف وواضح.',
  '<g fill="none" stroke="#376e94" stroke-width="10" stroke-linecap="round" stroke-linejoin="round">'+SNOW+'</g><g fill="none" stroke="url(#ice)" stroke-width="5" stroke-linecap="round" stroke-linejoin="round">'+SNOW+'</g><path d="m64 51 12 13-12 13-12-13Z" fill="#ebffff" stroke="#5fa2c3" stroke-width="2"/>'),
 ('badge_fox','مؤشر الطيف','مؤشر فيروزي بلمسات رقمية متقطعة.',
  '<path d="m32 19 68 61-32 2-14 29Z" fill="#55405e"/><path d="m30 14 68 61-32 2-14 29Z" fill="#17c8db" stroke="#e0ffff" stroke-width="2.5"/><path d="m62 78 16 26 9-6-15-25" fill="#18c8d9" stroke="#d7ffff" stroke-width="2"/><path d="M24 37h15m-11 13h10m43 4h17M25 78h15m51 12h12" stroke="#a3f3d4" stroke-width="5"/><path d="M28 27h8m12 28h12m-16 12h8m26 21h9" stroke="#594060" stroke-width="4"/>'),
 ('badge_fire','فانوس العنبر','ضوء ذهبي داخل فانوس هندسي بسيط.',
  '<path d="M53 26v-7a11 11 0 0 1 22 0v7" fill="none" stroke="#b78240" stroke-width="5"/><path d="m39 36 13-12h24l13 12-8 61H47Z" fill="url(#gold)" stroke="#a2743b" stroke-width="3"/><path d="M49 43h30l-5 45H54Z" fill="#ffe8a1" stroke="#c69345" stroke-width="2"/><path d="M64 43v45M43 36h42M42 99h44l4 9H38Z" fill="url(#gold)" stroke="#ac7b3d" stroke-width="3"/><path d="M58 52v24" stroke="#fff8db" stroke-width="4" stroke-linecap="round"/>'),
 ('badge_crystal','بلورة البنفسج','حجر بنفسجي بأوجه لؤلؤية متوازنة.',
  '<path d="m64 13 31 26 9 42-40 34-40-34 9-42Z" fill="url(#violet)" stroke="#8062b0" stroke-width="3"/><path d="m64 13-15 33 15 48 15-48Z" fill="#e7d5fc"/><path d="M33 39 49 46 24 81l40 13 40-13-25-35 16-7M64 94v21" fill="none" stroke="#9775cf" stroke-width="2.5"/><path d="m49 46 15-5 15 5-15 48Z" fill="#bb9de6"/><path d="m64 13-15 33 15-5Z" fill="#f9eeff"/>'),
 ('badge_leopard','حرف الفوز','حرف W أحمر بلمسة فرشاة حيوية.',
  '<path d="m17 29 14 68 17 5 17-41 7 41 18-4 25-75-16 3-18 48-7-45-16-1-19 47-9-52Z" fill="#c92943"/><path d="m20 20 11 70 14 6 20-48 9 46 13-5 23-68-12 4-16 48-10-50-15 2-18 48-7-56Z" fill="#f3444d"/><path d="m26 28 7 46m32-45 5 31m31-27-14 43" fill="none" stroke="#ff8c79" stroke-width="3" stroke-linecap="round"/><path d="m19 17 2 10m21 71-2 9m49-22 4-12M109 15l-3 10" stroke="#aa203c" stroke-width="2"/>'),
 ('badge_jellyfish','مدار النيون','حلقة فيروزية تدور حول بلورة بنفسجية.',
  '<path d="m64 30 22 33-22 35-22-35Z" fill="url(#violet)" stroke="#8b70b7" stroke-width="2"/><ellipse cx="64" cy="64" rx="48" ry="19" transform="rotate(-28 64 64)" fill="none" stroke="#329cac" stroke-width="7"/><ellipse cx="64" cy="62" rx="48" ry="19" transform="rotate(-28 64 62)" fill="none" stroke="#90f3e0" stroke-width="4"/><circle cx="103" cy="38" r="7" fill="#d5fcf1" stroke="#54bfbd" stroke-width="2"/>'),
 ('badge_shard','شظية البرق','برق فيروزي بحدود واضحة بجانب اسمك.',
  '<path d="m72 12-47 58h31l-5 44 52-64H72l10-38Z" fill="url(#aqua)" stroke="#24899c" stroke-width="3" stroke-linejoin="round"/><path d="M72 20 39 62h24l-3 29 30-35H65Z" fill="#b4fff0" opacity=".7"/>'),
 ('badge_ember','وهج المرجان','شعلة مرجانية صغيرة بدون ملامح.',
  '<path d="M68 11c5 28 31 31 31 60a35 35 0 0 1-70 0c0-16 9-29 20-40-1 16 5 21 10 25 9-13 2-27 9-45Z" fill="url(#coral)" stroke="#cc6a68" stroke-width="3"/><path d="M67 62c2 13 14 17 14 30a17 17 0 0 1-34 0c0-8 5-15 10-21 0 9 5 12 8 15 4-8-1-16 2-24Z" fill="#ffe3b5"/>'),
 ('badge_moonstone','حجر السحاب','ماسة سماوية بتفاصيل فضية ناعمة.',
  '<path d="m64 12 40 43-40 61-40-61Z" fill="url(#ice)" stroke="#7298ba" stroke-width="3"/><path d="m64 12 13 43-13 61-13-61Z" fill="#d9edfb"/><path d="M24 55h80L64 71Z" fill="#a2b9e6"/><path d="M64 12 51 55 24 55Z" fill="#eaffff"/><path d="m64 71 13-16-13 61Z" fill="#96c3d7"/>'),
 ('badge_steward','بوصلة المجلس','بوصلة هندسية خاصة بمشرفي المساحات.',
  '<circle cx="64" cy="64" r="43" fill="url(#aqua)" stroke="#318f89" stroke-width="3"/><circle cx="64" cy="64" r="33" fill="#d8f6e7" stroke="#71b8a4" stroke-width="2"/><path d="m80 41-10 29-23 17 10-29Z" fill="#259e9d"/><path d="m80 41-23 17 13 12Z" fill="#faf3c8"/><path d="M64 25v7m0 64v7M25 64h7m64 0h7" stroke="#347f7d" stroke-width="3" stroke-linecap="round"/>'),
]

def svg(art):
    return f'<svg xmlns="http://www.w3.org/2000/svg" width="256" height="256" viewBox="0 0 128 128">{DEFS}{art}</svg>\n'

def build():
    OUT.mkdir(parents=True,exist_ok=True)
    commands=[]
    records=[]
    for key,name,description,art in BADGES:
        source=HERE/(key+'.svg');source.write_text(svg(art),encoding='utf-8')
        dest=OUT/(key+'-v2.png')
        commands.append(f'file-open:{source};export-filename:{dest};export-do;file-close')
        records.append(dict(id=key,name=name,description=description,asset='/platform/assets/stickers/'+dest.name))
    # Compatibility atlas now contains the same inanimate drawings, never the old creatures.
    cells=''.join(f'<svg x="{i%3*128}" y="{i//3*128}" width="128" height="128" viewBox="0 0 128 128">{art}</svg>' for i,(_,_,_,art) in enumerate(BADGES[:8]))
    atlas=HERE/'compatibility-atlas.svg';atlas.write_text(f'<svg xmlns="http://www.w3.org/2000/svg" width="768" height="768" viewBox="0 0 384 384">{DEFS}{cells}</svg>',encoding='utf-8')
    subprocess.run(['inkscape','--export-type=png','--actions='+';'.join(commands)],check=True)
    subprocess.run(['inkscape',str(atlas),'--export-type=png',f'--export-filename={OUT / "samidev-stickers.png"}'],check=True)
    (OUT/'collection.json').write_text(json.dumps({'version':2,'items':records},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (OUT/'atlas.json').write_text(json.dumps({'layout':{'columns':3,'rows':3},'image':'samidev-stickers.png','source':'Original Plazr inanimate vector artwork, 2026-10-18. Compatibility only; use independent PNGs.','cells':[row[1] for row in BADGES[:8]]+['']},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print('Exported 12 independent transparent badges and compatibility atlas')

if __name__=='__main__':
    build()
