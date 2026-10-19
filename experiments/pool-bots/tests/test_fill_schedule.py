import unittest
from fill_schedule import FillSchedule,MULTI_DELAYS
from planner import legal_targets


def room(mode=1,capacity=4,occupied=1):
    return {'roomId':'multi','settings':{'gameId':'pool','gameType':mode},'capacity':capacity,'occupied':occupied,'createdAt':1000,'started':False}


class FillTests(unittest.TestCase):
    def test_multiplayer_waits_for_confirmed_joins_not_poll_count(self):
        schedule=FillSchedule();table=room()
        self.assertFalse(schedule.eligible(table,10,60.99));self.assertTrue(schedule.eligible(table,10,61))
        schedule.confirmed('multi',62);table['occupied']=2
        self.assertFalse(schedule.eligible(table,10,91.99));self.assertTrue(schedule.eligible(table,10,92))
        schedule.confirmed('multi',93);table['occupied']=3
        self.assertFalse(schedule.eligible(table,10,107.99));self.assertTrue(schedule.eligible(table,10,108))
        table['occupied']=4;self.assertFalse(schedule.eligible(table,10,1000))
        self.assertEqual(MULTI_DELAYS,(60,30,15,10))
    def test_late_start_does_not_skip_intervals_and_humans_can_fill_seats(self):
        schedule=FillSchedule();table=room(6,3)
        self.assertTrue(schedule.eligible(table,10,300))
        schedule.confirmed('multi',300);table['occupied']=2
        self.assertFalse(schedule.eligible(table,10,329.99))
        self.assertTrue(schedule.eligible(table,10,330))
        table['occupied']=3;self.assertFalse(schedule.eligible(table,10,400))
        table.update(occupied=2,started=True);self.assertFalse(schedule.eligible(table,10,400))
    def test_two_player_timing_is_preserved_and_stale_tables_pruned(self):
        schedule=FillSchedule();table=room(0,2)
        self.assertFalse(schedule.eligible(table,10,10.99));self.assertTrue(schedule.eligible(table,10,11))
        schedule.confirmed('multi',11);schedule.prune([{**table,'started':True}]);self.assertEqual(schedule.joins,{})
    def test_native_team_assignments_and_lowest_ball_rules(self):
        view={'balls':[[0,0,0,0],[1,0,0,0],[8,0,0,0],[9,0,0,0]],'solids':0,'ruleType':0,'teams':[[0,1],[2,3]]}
        self.assertEqual([ball[0] for ball in legal_targets(view,1)],[1])
        self.assertEqual([ball[0] for ball in legal_targets(view,2)],[9])
        self.assertEqual([ball[0] for ball in legal_targets(view,3)],[9])
        for rule in (1,2):
            view['ruleType']=rule
            self.assertEqual([ball[0] for ball in legal_targets(view,2)],[1])
