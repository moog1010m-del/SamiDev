from pathlib import Path
import math,random,hashlib,json,subprocess,wave,array,tempfile
ROOT=Path(__file__).resolve().parents[1];GAME=ROOT/'game';TMP=ROOT/'design/original-assets'
rename={
'251573114_nw_prev.m4a':'disc-hit-soft.m4a',
'251573127_nw_prev.m4a':'disc-hit-bright.m4a',
'251573134_nw_prev.m4a':'disc-hit-deep.m4a',
'falling-stonesrocks-stone-impact10-sound-effect-220005327_nw_prev.m4a':'pocket-drop-soft.m4a',
'falling-stonesrocks-stone-impact57-sound-effect-220005383_nw_prev.m4a':'pocket-drop-deep.m4a',
'067738089-fail-game-lose-level-31.m4a':'round-loss.m4a',
'247498187-oriental-win-03-prize-winner-a.m4a':'round-win.m4a',
'dragging-stool-05-loop-sound-effect-010766441_nw_prev.m4a':'striker-slide.m4a',
'magic-poof-pop-sound-effect-197679100_nw_prev.m4a':'pocket-soft-pop.m4a',
'pebbles-tap-sound-d-sound-effect-241981446_nw_prev.m4a':'disc-rail-tap.m4a',
}
paths=list(GAME.rglob('*.m4a'))
records=[];sample_rate=44100
for src in sorted(paths):
    p=src.with_name(rename.get(src.name,src.name));name=p.stem
    seed=int(hashlib.sha256(str(p.relative_to(GAME)).encode()).hexdigest()[:8],16);rng=random.Random(seed)
    whoosh=any(k in name for k in ('woosh','whoosh','slide'))
    music='bg-music' in name
    melody=any(k in name for k in ('win','won','loss','lose','bells','turn_audio','favorite'))
    whistle='whistle' in name
    duration=8.0 if music else .35 if whistle else .45 if whoosh else .85 if melody else .12 if 'hit' in name or 'tap' in name else .22
    data=array.array('h');low=0.0
    for n in range(int(duration*sample_rate)):
        t=n/sample_rate;u=t/duration;noise=rng.uniform(-1,1);low=.82*low+.18*noise
        if music:
            chord=[130.81,164.81,196.0,261.63]
            env=min(1,t*2,(duration-t)*2)
            value=env*sum(.025*math.sin(2*math.pi*f*t)*(0.7+0.3*math.sin(2*math.pi*.25*t+k)) for k,f in enumerate(chord))
        elif whistle:
            env=math.sin(math.pi*u)**.65
            value=.13*env*(math.sin(2*math.pi*1850*t+1.1*math.sin(2*math.pi*13*t))+.2*math.sin(2*math.pi*3700*t))
        elif whoosh:
            env=math.sin(math.pi*u)**1.5
            value=.65*env*low+.04*env*math.sin(2*math.pi*(180*t+220*t*t))
        elif melody:
            notes=[523.25,659.25,783.99] if 'loss' not in name and 'lose' not in name else [523.25,440,349.23]
            value=0
            for k,f in enumerate(notes):
                dt=t-k*.13
                if dt>=0:value+=.16*math.sin(2*math.pi*f*dt)*math.exp(-7*dt)*min(1,dt*200)
        else:
            f=190+seed%240
            env=math.exp(-u*12)*min(1,t*1200)
            value=env*(.25*math.sin(2*math.pi*f*t)+.20*low+.07*math.sin(2*math.pi*f*2.7*t))
        data.append(round(max(-.8,min(.8,value))*32767))
    with tempfile.NamedTemporaryFile(suffix='.wav',dir=TMP,delete=False) as f:wav=Path(f.name)
    with wave.open(str(wav),'wb') as out:out.setnchannels(1);out.setsampwidth(2);out.setframerate(sample_rate);out.writeframes(data.tobytes())
    subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-i',str(wav),'-map_metadata','-1','-c:a','aac','-b:a','96k',str(p)],check=True)
    wav.unlink()
    if src!=p:src.unlink()
    records.append({'path':str(p.relative_to(ROOT)),'source':'new procedural synthesis; no input recording','seed':seed,'duration':duration,'previousPath':str(src.relative_to(ROOT))})
for p in GAME.rglob('*'):
    if p.is_file() and p.suffix in ('.js','.json','.html'):
        s=p.read_text();changed=s
        for old,new in rename.items():changed=changed.replace(old,new)
        if changed!=s:p.write_text(changed)
(TMP/'audio-records.json').write_text(json.dumps(records,indent=2)+'\n')
print(json.dumps({'newSynthesizedAudio':len(records),'renamedStockFileNames':len(rename)}))
