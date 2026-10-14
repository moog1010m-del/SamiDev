"""Reject malformed/truncated captures instead of reporting a false load-test pass."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from pool_match_replay import load_recording,public_state


class Format(unittest.TestCase):
    def test_live_and_durable_restore_have_same_semantics(self):
        state={'turn':[],'sequence':[12,10],'gameOver':True,'pool':{'balls':[],'gameOver':True}}
        fallback={'type':'resync_state','snapshot':{'t':[],'n':[12,10],'g':1,'pool':state['pool']}}
        self.assertEqual(public_state(fallback),state)
        self.assertEqual(public_state({**fallback,**state,'authorityEpoch':1}),state)

    def test_rejects_missing_footer_gap_and_client_auto_move(self):
        snapshot=json.loads(Path(__file__).with_name('fixtures').joinpath('pool_seven_pocketed.json').read_text())
        header={'type':'header','format':'samidev.pool-recording','version':1,'capacity':2,'engineSha256':'a'*64,'settings':{'gameId':'pool','gameType':7},'initialSnapshot':snapshot}
        event={'type':'command','ordinal':1,'atMs':1,'seat':0,'input':{'a':4,'st':0},'state':{}}
        end={'type':'end','complete':True,'events':1,'atMs':2}
        with tempfile.TemporaryDirectory() as folder:
            file=Path(folder)/'record.jsonl'
            def check(rows):
                file.write_text('\n'.join(json.dumps(r) for r in rows)+'\n');return load_recording(file)
            check([header,event,end])
            for rows in [[header,event],[header,event,{**end,'complete':False}],[header,{**event,'ordinal':2},end],
                         [header,{**event,'atMs':float('nan')},end],[header,{**event,'input':{'a':5}},end],
                         [header,event,{**end,'events':2}]]:
                with self.subTest(rows=rows),self.assertRaises(AssertionError):check(rows)


if __name__=='__main__':unittest.main()
