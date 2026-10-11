"""Decode every delivered effect, measure peak/onset, and check source/mobile integrity."""
from pathlib import Path
import hashlib,json,subprocess
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from scipy.signal import resample_poly
ROOT=Path(__file__).resolve().parents[1]
GAME=ROOT/'game'
manifest=json.loads((ROOT/'FREESOUND_AUDIO.json').read_text())
mobile=ROOT.parent/'SamiDev_Flutter/assets/runtime'
mobile_manifest=json.loads((mobile.parent/'runtime-manifest.json').read_text())
def check(item):
    p=ROOT/item['file'];data=p.read_bytes()
    assert hashlib.sha256(data).hexdigest()==item['sha256'],p
    assert item['license']=='CC0-1.0'
    for source in item['sources']:
        assert source['license']=='CC0-1.0'
        path=ROOT/'design/freesound-v37'/source['sourceFile']
        assert hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256']
    assert item['replacedSha256']!=item['sha256'],'Unchanged effect'
    rel=p.relative_to(GAME)
    assert (mobile/rel).read_bytes()==data,rel
    assert mobile_manifest['files'][rel.as_posix()]['sha256']==item['sha256']
    pcm=subprocess.check_output(['ffmpeg','-v','error','-i',str(p),'-ac','1','-ar','44100','-f','f32le','pipe:1'])
    x=np.frombuffer(pcm,dtype='<f4');assert np.all(np.isfinite(x))
    peak=float(np.max(np.abs(x)));true_peak=float(np.max(np.abs(resample_poly(x,4,1))))
    assert .025<peak<.93,(rel,peak)
    assert true_peak<.95,(rel,true_peak)
    assert .06<len(x)/44100<1.8,(rel,len(x)/44100)
    onset=float(np.flatnonzero(np.abs(x)>.05*peak)[0]/44100)
    assert onset<.035,(rel,'late onset',onset)
    return {'file':item['file'],'seconds':round(len(x)/44100,4),'peakDbFS':round(20*np.log10(peak),2),
            'truePeakDbFS4x':round(20*np.log10(true_peak),2),'onsetMs':round(onset*1000,2),'bytes':len(data)}
with ThreadPoolExecutor(max_workers=6) as pool:rows=list(pool.map(check,manifest))
all_audio={p.relative_to(ROOT).as_posix() for p in GAME.rglob('*.m4a')}
retained=sorted(all_audio-{x['file'] for x in manifest})
assert len(manifest)==105 and len(retained)==5,(len(manifest),retained)
assert all('ahem' in p or 'bg-music-standard' in p for p in retained)
for base,namespace in [(GAME,'carrom'),*( (GAME/'games'/g,g) for g in ['crazy8','pool','tablesoccer'])]:
    for key,digest in json.loads((base/'__assets.json').read_text()).items():
        p=base/key.removeprefix(namespace+'/')
        assert hashlib.sha1(p.read_bytes()).hexdigest()==digest,key
report={'passed':True,'release':'V37','effectsVerified':len(rows),'sourceRecordings':len({s['id'] for x in manifest for s in x['sources']}),
        'allDecoded':True,'flutterMatches':True,'localAssetIndexesVerified':4,'clippedEffects':0,
        'retainedFiles':retained,'effects':rows,
        'limitations':['4x oversampled peak measurement, not a listening test','No APK build or physical-phone audition performed']}
(ROOT/'AUDIO_TEST_REPORT_V37.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k!='effects'},ensure_ascii=False))
