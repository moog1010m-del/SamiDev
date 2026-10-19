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
        for text in ['كم الساعة','عطني سنابك','كم فوز عندي','أنت بوت']:
            reply=await self.engine.respond(Message(text,'a',text));self.assertIsNotNone(reply)
        self.assertEqual(self.provider.calls,0)
    async def test_greeting_uses_model_and_same_persona_follows_user_answer(self):
        seen=[]
        class Capture:
            async def generate(inner,profile,context,*args):
                seen.append((profile,context));return 'وعليكم السلام، كيفك؟' if profile['conversation_mode']=='welcome' else 'وش كان متعبك بالدوام؟'
        self.engine.provider=Capture()
        greeting=Message('greeting','human','السلام عليكم');self.engine.ingest(greeting)
        first=await self.engine.respond(greeting)
        self.assertEqual(seen[0][0]['conversation_mode'],'welcome')
        self.engine.turn+=1
        answer=Message('answer','human','الحمد لله، توي راجع من الدوام');self.engine.ingest(answer)
        second=await self.engine.respond(answer)
        self.assertEqual(first.speaker,second.speaker)
        self.assertEqual(seen[-1][1][-1]['text'],answer.text)
        addressed=Message('address','human','فهد وش رايك؟');self.engine.ingest(addressed)
        self.assertEqual((await self.engine.respond(addressed)).speaker,'fahad')
    async def test_greeting_falls_back_to_checkin_when_model_unavailable(self):
        class Broken:
            async def generate(*args):raise RuntimeError('unavailable')
        self.engine.provider=Broken()
        reply=await self.engine.respond(Message('greeting','human','السلام عليكم'))
        self.assertEqual(reply.reason,'local');self.assertIn('كيفك؟',reply.text)
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
    async def test_shared_context_distinguishes_bots_and_user_objection(self):
        captured=[]
        class Capture:
            async def generate(inner,profile,context,preference):
                captured.append((profile,context));return 'معك حق، ما أدري عن سبب سكوتهم.'
        self.engine.provider=Capture()
        self.engine.identities={'bot-n':{'name':'نواف','kind':'bot','persona_id':'nawaf'}}
        self.engine.ingest(Message('greeting','human','السلام عليكم وين الشباب ليش الروم طافي'))
        self.mem.add('majlis',Message('reply','bot-n','وعليكم السلام، الروم منور بس الشباب مروقين على السوالف والعلوم الطيبة.'))
        objection=Message('objection','human','أي سوالف يا عمي ما نشوف الناس؟')
        self.engine.ingest(objection)
        reply=await self.engine.respond(objection)
        self.assertIsNotNone(reply)
        rows=captured[0][1]
        self.assertEqual(rows[0]['speaker'],rows[2]['speaker'])
        self.assertNotEqual(rows[0]['speaker'],rows[1]['speaker'])
        self.assertEqual(rows[1]['name'],'نواف')
        self.assertEqual(rows[1]['kind'],'bot')
        self.assertEqual(rows[-1]['text'],objection.text)
    async def test_silence_and_duplicate_bot_reply_are_not_published(self):
        self.engine.identities={'bot-n':{'name':'نواف','kind':'bot','persona_id':'nawaf'}}
        self.mem.add('majlis',Message('bot-reply','bot-n','هلا والله'))
        message=Message('human','human','وش عندكم؟');self.engine.ingest(message)
        self.provider.text='هلا والله!'
        self.assertIsNone(await self.engine.respond(message))
        self.provider.text=''
        self.assertIsNone(await self.engine.respond(message))
    async def test_initiative_waits_for_quiet_and_needs_humans(self):
        self.assertIsNone(await self.engine.initiative(1))
        self.engine.last_input=-1e9
        self.assertIsNone(await self.engine.initiative(0))
        reply=await self.engine.initiative(1)
        self.assertEqual(reply.reason,'initiative')
        self.assertIsNone(await self.engine.initiative(1))
        self.assertEqual(self.provider.calls,1)
        self.engine.ingest(Message('new-human-turn','human','ما علينا، وش رايكم؟'))
        self.engine.last_input=-1e9
        self.assertIsNotNone(await self.engine.initiative(1))
        self.assertEqual(self.provider.calls,2)
    async def test_initiative_silence_does_not_retry_or_make_bot_loop(self):
        self.engine.last_input=-1e9;self.provider.text=''
        self.assertIsNone(await self.engine.initiative(1))
        self.assertIsNone(await self.engine.initiative(1))
        self.assertEqual(self.provider.calls,1)
    async def test_user_message_during_initiative_cancels_outdated_reply(self):
        entered=asyncio.Event();release=asyncio.Event()
        class Slow:
            async def generate(inner,profile,*args):
                self.assertEqual(profile['conversation_mode'],'initiative')
                entered.set();await release.wait();return 'وش ودكم نسولف عنه؟'
        self.engine.provider=Slow();self.engine.last_input=-1e9
        task=asyncio.create_task(self.engine.initiative(1));await entered.wait()
        self.engine.ingest(Message('new-input','human','غيرنا الموضوع'));release.set()
        self.assertIsNone(await task)
    async def test_screenshot_objection_reaches_model_without_greeting_rule(self):
        seen=[]
        class Capture:
            async def generate(inner,profile,context,*args):
                seen.append(context[-1]['text']);return 'لا تعطيهم اللي يبونه.'
        self.engine.provider=Capture()
        for i,text in enumerate(['يا الله جيت وين الحلا والقهوة','أنا دايخ، هالناس معصبيني','كيف يتنمرون علي، باين فاضين زيادة عن اللزوم']):
            message=Message(str(i),'human',text);self.engine.ingest(message)
            reply=await self.engine.respond(message)
            self.assertEqual(reply.reason,'model');self.assertEqual(seen[-1],text)
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
