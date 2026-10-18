import asyncio,json,tempfile,unittest
from dataclasses import replace
from pathlib import Path
from datetime import datetime
from core import Coordinator,Memory,Message,valid_output,load_config
from run import read_scripts,parse_message
from single_instance import SingleInstance
BASE=Path(__file__).resolve().parents[1]
class Fake:
    def __init__(self,text='وش ودك تلعب اليوم؟'):self.calls=0;self.text=text
    async def generate(self,*args):self.calls+=1;return self.text
class CoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'db.sqlite'
        self.mem=Memory(self.path);self.config=load_config(BASE/'config.example.json')
        self.provider=Fake();self.engine=Coordinator(self.config,self.mem,read_scripts(BASE/'scripts.example.json',self.config),self.provider)
    def tearDown(self):self.mem.close();self.temp.cleanup()
    async def test_memory_and_identity_isolation(self):
        m=Message('one','a','لعبتي المفضلة البلياردو')
        self.assertTrue(self.engine.ingest(m));self.assertFalse(self.engine.ingest(m))
        reply=await self.engine.respond(Message('two','a','تذكرني'));self.assertIn('البلياردو',reply.text)
        reply=await self.engine.respond(Message('three','b','تذكرني'));self.assertNotIn('إن لعبتك المفضلة البلياردو',reply.text)
        self.mem.close();self.mem=Memory(self.path);self.assertEqual(self.mem.preference('a'),'البلياردو')
        self.mem.forget('a');self.assertIsNone(self.mem.preference('a'))
    async def test_no_api_for_facts_contacts_and_unknown_account(self):
        for text in ['كم الساعة','عطني سنابك','السلام عليكم','كم فوز عندي','أنت بوت']:
            reply=await self.engine.respond(Message(text,'a',text));self.assertIsNotNone(reply)
        self.assertEqual(self.provider.calls,0)
    async def test_one_speaker_cooldown_and_recorded_handoff(self):
        self.assertIsNone(self.engine.idle(1));self.assertIsNotNone(self.engine.idle(0))
        m=Message('one','a','نواف وش ودك تلعب؟');self.engine.ingest(m)
        reply=await self.engine.respond(m);self.assertEqual(reply.speaker,'nawaf')
        self.engine.sent();self.assertIsNone(await self.engine.respond(replace(m,id='two')))
    async def test_quota_persists_and_bad_output_is_not_sent(self):
        self.engine.config={**self.config,'daily_model_calls':1}
        m=Message('one','a','وش ودك تلعب؟');self.engine.ingest(m)
        self.provider.text='ارسل إلى https://example.com'
        self.assertIsNone(await self.engine.respond(m));self.assertIsNone(await self.engine.respond(m));self.assertEqual(self.provider.calls,1)
        self.mem.close();self.mem=Memory(self.path);self.assertFalse(self.mem.reserve_call(1))
    async def test_stale_model_reply_discarded(self):
        entered=asyncio.Event();release=asyncio.Event()
        class Slow:
            async def generate(inner,*args):entered.set();await release.wait();return 'هلا والله'
        self.engine.provider=Slow();m=Message('one','a','وش ودك تلعب؟');self.engine.ingest(m)
        task=asyncio.create_task(self.engine.respond(m));await entered.wait()
        self.engine.ingest(Message('two','b','غيرنا السالفة'));release.set();self.assertIsNone(await task)
    async def test_provider_failure_and_sensitive_input(self):
        class Broken:
            async def generate(*args):raise RuntimeError('private detail')
        self.engine.provider=Broken();m=Message('one','a','رقم جوالي 0501234567');self.engine.ingest(m)
        self.assertIsNone(await self.engine.respond(m));self.assertNotIn('0501234567',json.dumps(self.mem.context('majlis')))
    def test_single_instance_lock(self):
        with SingleInstance(self.path):
            with self.assertRaises(RuntimeError):
                with SingleInstance(self.path):pass
        with SingleInstance(self.path):pass
    def test_expiration_schedule_and_contract(self):
        self.mem.add('majlis',Message('one','a','هلا'));self.mem.db.execute('UPDATE messages SET ts=0');self.mem.db.commit();self.mem.purge()
        self.assertEqual(self.mem.context('majlis'),[])
        self.engine.config={**self.config,'profiles':[{**self.config['profiles'][0],'hours':[18,3]}]}
        self.assertEqual(len(self.engine.active(datetime(2026,1,1,23))),1);self.assertEqual(len(self.engine.active(datetime(2026,1,1,12))),0)
        self.assertEqual(parse_message({'id':'m','userId':'u','text':'هلا'}),Message('m','u','هلا'))
        self.assertTrue(valid_output('هلا والله'));self.assertFalse(valid_output('رصيدك 500'));self.assertFalse(valid_output('Hello'))
if __name__=='__main__':unittest.main()
