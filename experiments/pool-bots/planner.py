"""Geometric pool agent. Receives public ball positions; never changes physics."""
import math,random
from dataclasses import dataclass,asdict
RADIUS=20.5
SKILLS={'beginner':dict(angle=.040,power=.12,choices=5),'medium':dict(angle=.011,power=.055,choices=2),'expert':dict(angle=.0075,power=.022,choices=1)}
@dataclass
class Candidate:
    angle:float
    power:float
    target:int
    pocket:int
    score:float
    distance:float
    cut:float

def distance(a,b):return math.hypot(a[0]-b[0],a[1]-b[1])
def unit(a,b):
    d=distance(a,b)
    return ((b[0]-a[0])/d,(b[1]-a[1])/d) if d>.001 else (0,0)
def segment_distance(point,a,b):
    x,y=b[0]-a[0],b[1]-a[1];d=x*x+y*y
    t=max(0,min(1,((point[0]-a[0])*x+(point[1]-a[1])*y)/d)) if d else 0
    return distance(point,(a[0]+t*x,a[1]+t*y))
def legal_targets(view,seat):
    live=[b for b in view['balls'] if b[0] and not b[3]]
    if view.get('freePool'):return live
    solids=view.get('solids',-1)
    if solids not in (0,1):return [b for b in live if b[0]!=8]
    group=[b for b in live if (1<=b[0]<=7 if solids==seat else 9<=b[0]<=15)]
    return group or [b for b in live if b[0]==8]
def candidates(view,seat,cue=None):
    balls=[b for b in view['balls'] if not b[3]]
    cue=cue or next((b[1:3] for b in balls if b[0]==0),None)
    if cue is None:return []
    result=[]
    for target in legal_targets(view,seat):
        point=target[1:3]
        for pocket_index,pocket in enumerate(view['pockets']):
            direction=unit(point,pocket);ghost=(point[0]-direction[0]*RADIUS*2,point[1]-direction[1]*RADIUS*2)
            if not(65<=ghost[0]<=769 and 65<=ghost[1]<=1451):continue
            approach=unit(cue,ghost);cut=approach[0]*direction[0]+approach[1]*direction[1]
            if cut<.22:continue
            blockers=[b[1:3] for b in balls if b[0] not in (0,target[0])]
            if any(segment_distance(b,cue,ghost)<RADIUS*2+1 or segment_distance(b,point,pocket)<RADIUS*2+1 for b in blockers):continue
            path=distance(cue,ghost)+distance(point,pocket)
            power=min(.82,max(.13,.08+math.sqrt(path/1600)*.43/max(.7,cut)))
            # Prefer short, fuller contacts; penalize likely cue-ball scratch directions.
            tangent=(approach[0]-direction[0]*cut,approach[1]-direction[1]*cut)
            tangent_end=(point[0]+tangent[0]*250,point[1]+tangent[1]*250)
            scratch=any(segment_distance(p,point,tangent_end)<45 and distance(point,p)>65 for p in view['pockets'])
            score=path/(cut*cut)+ (600 if scratch else 0)
            result.append(Candidate(math.atan2(ghost[1]-cue[1],ghost[0]-cue[0]),power,target[0],pocket_index,score,path,cut))
    return sorted(result,key=lambda candidate:candidate.score)
def placement(view,seat):
    balls=[b for b in view['balls'] if b[0] and not b[3]]
    ys=[1160,1280,1380] if view.get('ballInHand',0)<0 else [180,400,650,900,1160,1380]
    valid=[(x,y) for x in [140,280,417,550,690] for y in ys if all(distance((x,y),b[1:3])>=44 for b in balls) and all(distance((x,y),p)>=60 for p in view['pockets'])]
    if not valid:return None
    def quality(point):
        options=candidates(view,seat,point)
        return options[0].score if options else 1e6+distance(point,(417,1280))
    return min(valid,key=quality)
def plan(view,seat,skill='medium',level=1,rng=None):
    rng=rng or random.Random();settings=SKILLS[skill];cue=next(b for b in view['balls'] if b[0]==0)
    position=placement(view,seat) if view.get('ballInHand',0)!=0 or cue[3] else None
    options=candidates(view,seat,position)
    if view.get('breaking'):
        cuepoint=position or cue[1:3];targets=legal_targets(view,seat)
        target=min(targets,key=lambda b:distance(cuepoint,b[1:3]))
        chosen=Candidate(math.atan2(target[2]-cuepoint[1],target[1]-cuepoint[0]),.84,target[0],-1,0,800,1)
    elif options:chosen=rng.choice(options[:settings['choices']])
    else:
        cuepoint=position or cue[1:3];targets=legal_targets(view,seat)
        if not targets:return None
        # Seek a legal first contact instead of selecting an arbitrary angle.
        def obstruction(b):
            return sum(segment_distance(other[1:3],cuepoint,b[1:3])<42 for other in view['balls'] if not other[3] and other[0] not in (0,b[0]))
        target=min(targets,key=lambda b:(obstruction(b),distance(cuepoint,b[1:3])))
        chosen=Candidate(math.atan2(target[2]-cuepoint[1],target[1]-cuepoint[0]),.38,target[0],-1,1e6,600,.5)
    improvement=1-.20*min(99,max(0,level-1))/99
    difficulty=1+max(0,1-chosen.cut)*.7
    error=rng.gauss(0,settings['angle']*improvement*difficulty)
    angle=math.atan2(math.sin(chosen.angle+error),math.cos(chosen.angle+error))
    power=max(.07,min(1,chosen.power+rng.gauss(0,settings['power']*improvement)))
    # Deliberation shows real alternative targets where available, not noise every frame.
    alternate=next((c.angle for c in options if c.target!=chosen.target),chosen.angle+rng.choice([-1,1])*.12)
    think=rng.uniform(2.3,4.4)+(0.5 if chosen.cut<.55 else 0)
    wrap=lambda angle:math.atan2(math.sin(angle),math.cos(angle))
    delta=wrap(chosen.angle-alternate)
    previews=[{'delay':think*.28,'move':{'a':3,'an':wrap(alternate)}}]
    previews.extend({'delay':think*.25/4,'move':{'a':3,'an':wrap(alternate+delta*i/4)}} for i in range(1,5))
    previews.extend([{'delay':think*.20,'move':{'a':3,'an':angle}},
              {'delay':think*.15,'move':{'a':4,'st':power}},
              {'delay':think*.12,'move':{'a':1,'an':angle,'st':power,'sp':[0,0]}}])
    return {'placement':list(position) if position else None,'steps':previews,'target':chosen.target,'pocket':chosen.pocket,'thinkSeconds':think,'angularError':error,'ideal':asdict(chosen)}
if __name__=='__main__':
    import sys,json
    # Offline diagnostics only: one JSON request per line, no network or session data.
    for line in sys.stdin:
        data=json.loads(line);print(json.dumps(plan(data['view'],data['seat'],data.get('skill','medium'),data.get('level',1),random.Random(data.get('seed')))),flush=True)
