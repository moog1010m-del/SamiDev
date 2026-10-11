"""Idempotent, exact-scope edits to the existing carrom sound mixer only."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
path=ROOT/'game/main.js'
text=path.read_text()
edits=[
 ('let n=[.5,.6,.8];no.default.play(i,{volume:t,rate:n[Math.floor(Math.random()*n.length)]})',
  'let n=[.97,1,1.03];no.default.play(i,{volume:t,rate:n[Math.floor(Math.random()*n.length)]})'),
 ('playCollBallRail(e){let t,i;i=HU,t=.25*e,no.default.play(i,{volume:t,rate:1.85})}',
  'playCollBallRail(e){let t,i;i=HU,t=.65*Math.sqrt(Math.max(0,Math.min(1,e))),no.default.play(i,{volume:t,rate:1})}'),
 ('no.default.play(KU,{volume:.2,rate:1})','no.default.play(KU,{volume:.55,rate:1})'),
 ('playSunkQueen(e){no.default.play("cast",{volume:.15})}',
  'playSunkQueen(e){no.default.play("cast",{volume:.5})}'),
 ('let e=Math.max(.01,.1-this._playingDrag*.025)*.125;no.default.play("striker_slide",{volume:e,rate:1})',
  'let e=.09/(1+this._playingDrag*.35);no.default.play("striker_slide",{volume:e,rate:1})'),
]
changed=0
for old,new in edits:
 if new in text:continue
 assert text.count(old)==1,'Audio mixer source changed; review before applying'
 text=text.replace(old,new);changed+=1
path.write_text(text)
print(f'Applied {changed} carrom sound-mixer edits; no physics or game rules changed')
