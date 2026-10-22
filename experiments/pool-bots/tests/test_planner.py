import math,random,statistics,unittest
from planner import plan,legal_targets,candidates,placement,segment_distance
from worker import eligible_room,origin
POCKETS=[[49,47],[785,47],[21,758],[813,758],[49,1469],[785,1469]]
def view():
 return {'balls':[[0,420,1200,0],[1,200,400,0],[2,600,900,0],[8,420,700,0],[9,500,350,0]],'pockets':POCKETS,'solids':0,'ballInHand':0,'breaking':False,'turn':[0],'sequence':[0,0]}
class PlannerTests(unittest.TestCase):
 def test_legal_group_and_eight(self):
  v=view();self.assertEqual([b[0] for b in legal_targets(v,0)],[1,2]);self.assertEqual([b[0] for b in legal_targets(v,1)],[9])
  v['balls']=[b for b in v['balls'] if b[0] not in (1,2)];self.assertEqual([b[0] for b in legal_targets(v,0)],[8])
  v['solids']=-1;self.assertEqual([b[0] for b in legal_targets(v,0)],[9])
 def test_noninstant_thinking_and_valid_actions(self):
  for skill in ('beginner','medium','expert'):
   p=plan(view(),0,skill,rng=random.Random(3));self.assertTrue(2.3<=p['thinkSeconds']<=5)
   self.assertEqual([s['move']['a'] for s in p['steps']],[3,3,3,3,3,3,4,1]);self.assertAlmostEqual(sum(s['delay'] for s in p['steps']),p['thinkSeconds'])
   self.assertTrue(all(s['delay']>0 for s in p['steps']))
   for s in p['steps']:
    m=s['move'];self.assertLessEqual(abs(m.get('an',0)),2*math.pi);self.assertTrue(0<=m.get('st',.5)<=1)
 def test_difficulty_and_level_change_errors_not_results(self):
  errors={skill:statistics.mean(abs(plan(view(),0,skill,rng=random.Random(i))['angularError']) for i in range(150)) for skill in ('beginner','medium','expert')}
  self.assertGreater(errors['beginner'],errors['medium']);self.assertGreater(errors['medium'],errors['expert'])
  a=plan(view(),0,'medium',1,random.Random(123));b=plan(view(),0,'medium',100,random.Random(123));self.assertLess(abs(b['angularError']),abs(a['angularError']))
 def test_ball_in_hand_is_legal(self):
  v=view();v['ballInHand']=-1;v['balls'][0][3]=1;p=plan(v,0,'expert',rng=random.Random(2));x,y=p['placement']
  self.assertGreaterEqual(y,1119);self.assertTrue(70<=x<=764 and 70<=y<=1446)
  self.assertTrue(all(math.hypot(x-b[1],y-b[2])>=41 for b in v['balls'] if b[0] and not b[3]))
 def test_other_games_and_unsupported_modes_are_untouched(self):
  room={'roomId':'test','settings':{'gameId':'pool','gameType':0},'occupied':1,'capacity':2,'started':False,'createdAt':1000}
  self.assertTrue(eligible_room(room,10,now=12));self.assertFalse(eligible_room(room,10,now=5))
  for mode in (1,2,3,4,5,6):self.assertFalse(eligible_room({**room,'settings':{'gameId':'pool','gameType':mode}},0,now=12))
  self.assertFalse(eligible_room({**room,'started':True},0,now=12))
  self.assertTrue(eligible_room({**room,'settings':{'gameId':'carrom'}},0,now=12))
  self.assertTrue(eligible_room({**room,'settings':{'gameId':'crazy8'}},0,now=12))
  self.assertFalse(eligible_room({**room,'settings':{'gameId':'tablesoccer'}},0,now=12))
  for value in ('http://external.test','https://user:pass@example.com','https://example.com/path'):
   with self.assertRaises(ValueError):origin(value)
 def test_blocked_shot_is_not_called_clear(self):
  v=view();v['balls']=[[0,200,200,0],[1,400,400,0],[9,300,300,0],[8,700,1000,0]]
  self.assertTrue(all(not(c.target==1 and c.pocket==5) for c in candidates(v,0)))
if __name__=='__main__':unittest.main()
