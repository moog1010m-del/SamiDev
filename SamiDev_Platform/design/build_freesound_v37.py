"""Build local AAC effects from documented CC0 recordings. Requires numpy/scipy/ffmpeg.

Source MP3s are public HQ previews, not the original lossless recordings.
No synthesizer or runtime network requests are used. Source metadata stays in
design/freesound-v37; every trim and processing decision is in the output manifest.
"""
from pathlib import Path
from fractions import Fraction
import hashlib, json, subprocess
import numpy as np
from scipy.signal import butter, sosfilt, resample_poly

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / 'game'
SOURCES = ROOT / 'design/freesound-v37'
SR = 44100
cache = {}
recipes = {}

def piece(source, start, duration, rate=1, highpass=65, lowpass=12000):
    return dict(source=source, startSeconds=start, durationSeconds=duration,
                playbackRate=rate, highpassHz=highpass, lowpassHz=lowpass)

def add(path, source, start, duration, peak=-6, rate=1, highpass=65, lowpass=12000, role=''):
    recipes[path] = {'layers': [dict(**piece(source,start,duration,rate,highpass,lowpass), offsetSeconds=0)],
                     'peakDbFS': peak, 'role': role}

def sequence(path, source, start, duration, offsets, rates, peak=-9, role=''):
    recipes[path] = {'layers': [dict(**piece(source,start,duration,rate), offsetSeconds=offset)
                               for offset,rate in zip(offsets,rates)], 'peakDbFS':peak, 'role':role}

# Pool: recorded resin impacts and actual table/pocket resonances. Cushion
# effects are intentionally filtered Foley adaptations of the pool recordings.
pool='games/pool/sounds/'
for i,rate in enumerate([.97,1,1.04],1):
    add(pool+f'ball{i}.m4a','pool_clack',0,.239,-5,rate,role='pool ball collision')
    add(pool+f'ball_soft{i}.m4a','pool_clack',0,.18,-10,rate,lowpass=7500,role='soft ball collision')
    add(pool+f'rail{i}.m4a','pool_clack',0,.22,-8,rate*.88,lowpass=1700,role='cushion Foley adapted from pool impact')
    add(pool+f'rail_soft{i}.m4a','pool_clack',0,.18,-13,rate*.9,lowpass=1400,role='soft cushion Foley')
    start=[4.72,8.02,10.97][i-1]
    add(pool+f'pocket{i}.m4a','pool_inside',start,.30,-6,role='ball pocket entry')
    add(pool+f'sunk{i}.m4a','pool_inside',start+.30,.58,-9,role='ball rolling inside pocket')
for name,rate,peak in [('cue_soft1',1.03,-10),('cue_hard1',1,-5),('cue_hard2',.96,-4.5)]:
    add(pool+name+'.m4a','pool_cue',4.825,.14,peak,rate,highpass=90,role='cue striking ball')
sequence(pool+'rack.m4a','pool_clack',0,.239,[0,.07,.145,.25,.39],[1,.98,1.04,.95,1.02],-7,'recorded balls arranged as rack rattle')

# Carrom: small wooden pieces provide the tactile click and sliding sound.
for name,start,duration,peak in [('disc-hit-soft',65.89,.20,-10),('disc-hit-deep',66.16,.22,-6),('disc-hit-bright',68.52,.23,-5),('disc-rail-tap',71.17,.20,-8),('pocket-drop-soft',73.55,.30,-7),('pocket-drop-deep',74.52,.30,-5.5),('pocket-soft-pop',73.36,.24,-6.5)]:
    add('sounds/'+name+'.m4a','board_pieces',start,duration,peak,role='wooden board-piece Foley for carrom')
add('sounds/striker-slide.m4a','board_pieces',80.04,.46,-10,highpass=180,role='wooden piece sliding')
add('sounds/striker_short.m4a','board_pieces',81.27,.20,-8,highpass=180,role='short striker movement')

# Table soccer: football kicks, net rustle, wooden token sounds and real whistle.
soccer='games/tablesoccer/sounds/'
for i,start in enumerate([1.915,3.61,4.93],1):
    add(soccer+f'ball_long{i}.m4a','soccer_bounces',start,.38,-5,role='football impact')
for i,rate in enumerate([1,1.045],1):
    add(soccer+f'ball_short{i}.m4a','soccer_kick',.02,.32,-7,rate,role='short football kick')
for i,start in enumerate([65.89,66.16,68.52],1):
    add(soccer+f'token_hit{i}.m4a','board_pieces',start,.24,-6,role='table token impact')
for i,start in enumerate([80.04,81.27],1):
    add(soccer+f'token_slide{i}.m4a','board_pieces',start,.30,-11,highpass=180,role='table token slide')
add(soccer+'post1.m4a','foosball_goal',.63,.17,-6,role='table football impact used for post')
add(soccer+'goal1.m4a','soccer_net',1.32,.62,-7,highpass=90,role='ball/net goal sound')
add(soccer+'whistle1.m4a','whistle',0,.536,-10,highpass=180,lowpass=9500,role='referee whistle')

# Cards stay acoustic, with tighter onset and cleaner endings than V36.
cards='games/crazy8/sounds/'
add(cards+'card-draw.m4a','cards',.655,.21,-9,highpass=180,role='draw card')
add(cards+'card-place.m4a','cards',12.0,.31,-7.5,highpass=160,role='place card')
add(cards+'card-special.m4a','card_special',2.36,.28,-7,highpass=180,role='special card flip')
add(cards+'card-shuffle.m4a','card_shuffle',.24,1.09,-10,highpass=180,role='shuffle cards')
sequence(cards+'card-warning.m4a','bell',.015,.30,[0,.13],[1,1.25],-16,'quiet recorded-bell stacking alert')

# Existing shared paths keep their native event bindings. Music and the four
# existing human reaction clips are deliberately left in place.
for f in sorted(GAME.rglob('*.m4a')):
    rel=f.relative_to(GAME).as_posix()
    if rel in recipes: continue
    stem=f.stem
    if stem=='bg-music-standard' or stem.startswith('ahem'):continue
    if stem in ['round-win','you_won1']:
        sequence(rel,'bell',.015,.70,[0,.17,.36],[1,1.25,1.5],-9,'win cue made from recorded bell')
    elif stem in ['round-loss','you_lose1']:
        sequence(rel,'bell',.015,.52,[0,.20],[.9,.72],-13,'loss cue made from recorded bell')
    elif stem in ['bells','shop_widget_favorite']:
        sequence(rel,'bell',.015,.56,[0,.14],[1,1.25],-12,'positive feedback from recorded bell')
    elif stem=='turn_audio':
        add(rel,'bell',.015,.50,-15,role='turn notification from recorded bell')
    elif 'woosh' in stem or 'whoosh' in stem:
        add(rel,'whoosh',0,.315,-12,rate=.95 if ('2' in stem or 'close' in stem) else 1.05,role='recorded air swish')
    elif stem in ['tap_disabled','shop_widget_error']:
        sequence(rel,'wood_tap',.13,.12,[0,.085],[.82,.74],-15,'muted double wooden click')
    elif stem in ['tap','select','switch_on','switch_off','shop_widget_tap','iap_button_tap']:
        add(rel,'wood_tap',.13,.13,-14,rate=.9 if stem=='switch_off' else 1,role='short tactile UI click')
    else:raise ValueError('Unmapped audio file: '+rel)

def decoded(key):
    if key not in cache:
        p=SOURCES/(key+'.mp3');meta=json.loads((SOURCES/(key+'.json')).read_text())
        assert meta['license']=='CC0-1.0'
        assert hashlib.sha256(p.read_bytes()).hexdigest()==meta['sha256']
        data=subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-ar',str(SR),'-ac','1','-f','f32le','pipe:1'])
        cache[key]=np.frombuffer(data,dtype='<f4').astype(np.float64)
    return cache[key]

def render_piece(p):
    x=decoded(p['source'])[round(p['startSeconds']*SR):round((p['startSeconds']+p['durationSeconds'])*SR)].copy()
    assert len(x)>200
    x-=np.mean(x)
    x=sosfilt(butter(2,p['highpassHz'],fs=SR,btype='highpass',output='sos'),x)
    x=sosfilt(butter(2,p['lowpassHz'],fs=SR,btype='lowpass',output='sos'),x)
    rate=Fraction(1/p['playbackRate']).limit_denominator(1000)
    x=resample_poly(x,rate.numerator,rate.denominator)
    # Cut pre-roll to 4 ms. Keep the full attack, even for quiet physical sounds.
    audible=np.flatnonzero(np.abs(x)>np.max(np.abs(x))*.035)
    if len(audible): x=x[max(0,int(audible[0]) - round(.004*SR)):]
    nf=min(round(.009*SR),len(x)//5);ni=min(round(.0015*SR),nf)
    x[:ni]*=np.linspace(0,1,ni);x[-nf:]*=np.linspace(1,0,nf)
    return x

def build():
    old_path=ROOT/'FREESOUND_AUDIO.json'
    previous={x['file']:x for x in json.loads(old_path.read_text())} if old_path.exists() else {}
    manifest=[]
    for rel,recipe in recipes.items():
        layers=[(round(p['offsetSeconds']*SR),render_piece(p)) for p in recipe['layers']]
        x=np.zeros(max(offset+len(a) for offset,a in layers))
        for offset,a in layers:x[offset:offset+len(a)]+=a
        peak=np.max(np.abs(x));assert peak>1e-6
        x*=10**(recipe['peakDbFS']/20)/peak
        target=GAME/rel;target.parent.mkdir(parents=True,exist_ok=True)
        before=hashlib.sha256(target.read_bytes()).hexdigest() if target.exists() else None
        before=previous.get('game/'+rel,{}).get('replacedSha256',before)
        subprocess.run(['ffmpeg','-v','error','-y','-f','f32le','-ar',str(SR),'-ac','1','-i','pipe:0','-map_metadata','-1','-c:a','aac','-b:a','128k','-movflags','+faststart',str(target)],input=x.astype('<f4').tobytes(),check=True)
        sources=[json.loads((SOURCES/(key+'.json')).read_text()) for key in sorted({p['source'] for p in recipe['layers']})]
        manifest.append(dict(file='game/'+rel,license='CC0-1.0',sources=sources,recipe=recipe,
                             renderedDurationSeconds=round(len(x)/SR,6),replacedSha256=before,
                             sha256=hashlib.sha256(target.read_bytes()).hexdigest()))
    old_path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    used={p['source'] for recipe in recipes.values() for p in recipe['layers']}
    lines=['# Freesound audio credits — V37','',
           '104 existing effects replaced; one recorded-bell Crazy8 alert added. All listed source recordings are CC0 1.0.',
           'Public high-quality MP3 previews were used, not original lossless WAV downloads. Sources were verified on 2026-10-11.',
           'Edits: short trims, rumble filtering, gentle high-frequency filtering, onset alignment, edge fades, peak normalization, AAC encoding. Some variations use subtle resampling. Win/loss/alert cues sequence recorded bell samples.',
           'Carrom wooden-piece and pool cushion sounds are Foley adaptations; they are not claimed to be direct recordings of those exact events.',
           'The existing music and four ahem reaction clips are unchanged and are NOT covered by this new CC0 source inventory.',
           'No remote audio is loaded at runtime. Full per-file processing recipes and checksums are in FREESOUND_AUDIO.json.','',
           'License: https://creativecommons.org/publicdomain/zero/1.0/','']
    for key in sorted(used):
        m=json.loads((SOURCES/(key+'.json')).read_text())
        lines.append(f"- **{m['title']}** — {m['author']}; {m['source']}; CC0-1.0.")
    (ROOT/'AUDIO_CREDITS.md').write_text('\n'.join(lines)+'\n')
    print(json.dumps({'effects':len(manifest),'sourceRecordings':len(used),'bytes':sum((ROOT/x['file']).stat().st_size for x in manifest)},indent=2))

if __name__=='__main__':build()
