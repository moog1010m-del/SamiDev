"""Build a short listening reel and a source-linked local listening sheet."""
from pathlib import Path
import json, subprocess, html
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
SR=44100
groups=[
 ('البلياردو', [('ضربة العصا','games/pool/sounds/cue_hard1.m4a'),('تصادم قوي','games/pool/sounds/ball1.m4a'),('تصادم خفيف','games/pool/sounds/ball_soft1.m4a'),('حافة الطاولة','games/pool/sounds/rail1.m4a'),('دخول الجيب','games/pool/sounds/pocket1.m4a')]),
 ('الكيرم', [('تصادم القطع','sounds/disc-hit-deep.m4a'),('ضربة خشبية','sounds/disc-hit-bright.m4a'),('انزلاق المضرب','sounds/striker_short.m4a'),('دخول القرص','sounds/pocket-drop-deep.m4a')]),
 ('كرة الطاولة', [('ركلة قصيرة','games/tablesoccer/sounds/ball_short1.m4a'),('ركلة قوية','games/tablesoccer/sounds/ball_long1.m4a'),('المرمى','games/tablesoccer/sounds/goal1.m4a'),('الصفارة','games/tablesoccer/sounds/whistle1.m4a')]),
 ('كريزي 8', [('سحب ورقة','games/crazy8/sounds/card-draw.m4a'),('وضع ورقة','games/crazy8/sounds/card-place.m4a'),('ورقة خاصة','games/crazy8/sounds/card-special.m4a'),('خلط الأوراق','games/crazy8/sounds/card-shuffle.m4a'),('تنبيه الحماية','games/crazy8/sounds/card-warning.m4a')]),
 ('الواجهة والنتيجة', [('زر','sounds/tap.m4a'),('بدء الدور','scene-avatars/turn_audio.m4a'),('فوز','sounds/round-win.m4a'),('خسارة','sounds/round-loss.m4a')]),
]
parts=[np.zeros(round(.25*SR),dtype='<f4')];frames=len(parts[0]);timeline=[]
body=[]
for group,items in groups:
    body.append(f'<section><h2>{group}</h2>')
    for label,rel in items:
        raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(ROOT/'game'/rel),'-ac','1','-ar',str(SR),'-f','f32le','pipe:1'])
        x=np.frombuffer(raw,dtype='<f4')
        timeline.append(dict(group=group,label=label,startSeconds=round(frames/SR,3),durationSeconds=round(len(x)/SR,3),file='game/'+rel))
        gap=np.zeros(round(.5*SR),dtype='<f4');parts.extend([x,gap]);frames+=len(x)+len(gap)
        body.append(f'<article><strong>{label}</strong><audio controls preload="none" src="game/{html.escape(rel)}"></audio></article>')
    gap=np.zeros(round(.6*SR),dtype='<f4');parts.append(gap);frames+=len(gap)
    body.append('</section>')
out=ROOT/'AUDIO_PREVIEW_V37.mp3'
subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','1','-i','pipe:0','-c:a','libmp3lame','-b:a','192k',str(out)],input=np.concatenate(parts).astype('<f4').tobytes(),check=True)
(ROOT/'AUDIO_PREVIEW_TIMELINE_V37.json').write_text(json.dumps(timeline,ensure_ascii=False,indent=2)+'\n')
page='''<!doctype html><html lang="ar" dir="rtl"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>معاينة أصوات SamiDev V37</title><style>body{background:#101b26;color:#eaf1f5;font:17px/1.6 system-ui,sans-serif;max-width:1050px;margin:40px auto;padding:0 24px}header{border-bottom:1px solid #314656;padding-bottom:22px}h1{font-size:32px}h2{color:#8de1d2}section{margin:28px 0}article{display:flex;align-items:center;justify-content:space-between;gap:20px;background:#1a2c3b;padding:14px 20px;margin:8px 0;border-radius:12px}audio{max-width:70%}a{color:#8de1d2}small{color:#b5c7d4}</style><header><h1>أصوات اللعب · V37</h1><p>معاينة تسجيلات البلياردو والكيرم والكرة والأوراق. اضغط تشغيل لسماع كل مؤثر منفردًا.</p><small>المعاينة تعرض الملفات بمستواها الأساسي؛ مستوى الصوت داخل المباراة يتغير بحسب قوة الضربة وإعدادات الكتم. المصادر والتراخيص في <a href="AUDIO_CREDITS.md">ملف الحقوق</a>.</small></header>'''+''.join(body)+'</html>'
(ROOT/'AUDIO_PREVIEW_V37.html').write_text(page)
print(json.dumps({'clips':len(timeline),'seconds':round(frames/SR,2),'previewBytes':out.stat().st_size}))
