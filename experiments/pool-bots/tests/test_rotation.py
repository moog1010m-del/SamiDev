import unittest
from rotation import Rotation

class RotationTests(unittest.TestCase):
    def setUp(self):
        self.bots=[dict(id=str(i).zfill(2),room='majlis',enabled=True,poolPlayed=0) for i in range(50)]
        self.rotation=Rotation();self.jobs={};self.kinds={}
    def fill(self):
        while True:
            free=[b for b in self.bots if b['id'] not in self.jobs]
            pair=self.rotation.pair(free,self.bots,self.jobs,self.kinds,'majlis')
            if not pair:return free
            for bot in pair:
                self.jobs[bot['id']]=True;self.kinds[bot['id']]='selfplay';self.rotation.selected(bot)
    def test_forty_play_ten_reserved_and_all_rotate_after_actual_results(self):
        spare=self.fill();self.assertEqual(len(self.jobs),40);self.assertEqual(len(spare),10)
        previous=set(self.jobs)
        for bot in self.bots:
            if bot['id'] in previous:bot['poolPlayed']+=1
        self.jobs.clear();self.kinds.clear();self.fill()
        self.assertTrue({b['id'] for b in spare}<=set(self.jobs))
        self.assertEqual(len(previous|set(self.jobs)),50)
    def test_human_matches_use_reserve_without_exceeding_selfplay_target(self):
        self.fill()
        for b in self.bots[40:]:self.jobs[b['id']]=True;self.kinds[b['id']]='human'
        self.assertEqual(len(self.jobs),50)
        del self.jobs['00'];del self.jobs['01']
        self.fill();self.assertEqual(sum(self.kinds[u]=='selfplay' for u in self.jobs),40)
    def test_cooling_or_disabled_accounts_are_not_used_to_fill_reserve(self):
        self.assertIsNone(self.rotation.pair(self.bots[:11],self.bots,{}, {},'majlis'))
        self.assertIsNone(self.rotation.pair(self.bots,self.bots,{}, {},'other'))
        self.bots[0]['enabled']=False
        active=self.bots[1:];self.assertEqual(len(self.rotation.pair(active,self.bots,{}, {},'majlis')),2)
    def test_fewer_matches_win_over_recent_assignment(self):
        self.bots[0]['poolPlayed']=10
        self.assertNotEqual(self.rotation.order(self.bots)[0]['id'],'00')
