import asyncio, json, tempfile, unittest
from dataclasses import replace
from pathlib import Path
from datetime import datetime
from core import Coordinator, Memory, Message, valid_output, load_config
from run import read_scripts, parse_message
from single_instance import SingleInstance

BASE = Path(__file__).resolve().parents[1]


class Fake:
    def __init__(self, text='وش ودك تلعب اليوم؟'):
        self.calls = 0
        self.text = text

    async def generate(self, *args):
        self.calls += 1
        return self.text


class CoreTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.path = Path(self.temp.name) / 'db.sqlite'
        self.mem = Memory(self.path)
        self.config = load_config(BASE / 'config.example.json')
        self.provider = Fake()
        self.engine = Coordinator(self.config, self.mem, read_scripts(BASE / 'scripts.example.json', self.config), self.provider)

    def tearDown(self):
        try:
            self.mem.close()
        except Exception:
            pass
        try:
            self.temp.cleanup()
        except Exception:
            pass

    async def test_memory_and_identity_isolation(self):
        m = Message('one', 'a', 'لعبتي المفضلة البلياردو')
        self.assertTrue(self.engine.ingest(m))
        self.assertFalse(self.engine.ingest(m))
        reply = await self.engine.respond(Message('two', 'a', 'تذكرني'))
        self.assertIn('البلياردو', reply.text)
        reply = await self.engine.respond(Message('three', 'b', 'تذكرني'))
        self.assertNotIn('إن لعبتك المفضلة البلياردو', reply.text)
        self.mem.close()
        self.mem = Memory(self.path)
        self.assertEqual(self.mem.preference('a'), 'البلياردو')
        self.mem.forget('a')
        self.assertIsNone(self.mem.preference('a'))

    async def test_no_api_for_facts_contacts_and_unknown_account(self):
        for text in ['كم الساعة', 'عطني سنابك', 'كم فوز عندي', 'أنت بوت']:
            reply = await self.engine.respond(Message(text, 'a', text))
            self.assertIsNotNone(reply)
        self.assertEqual(self.provider.calls, 0)

    async def test_greeting_uses_model_and_same_persona_follows_user_answer(self):
        seen = []

        class Capture:
            async def generate(inner, profile, context, *args):
                seen.append((profile, context))
                return 'وعليكم السلام، كيفك؟' if profile['conversation_mode'] == 'welcome' else 'وش كان متعبك بالدوام؟'

        self.engine.provider = Capture()
        greeting = Message('greeting', 'human', 'السلام عليكم', 'KSA')
        self.engine.ingest(greeting)
        first = await self.engine.respond(greeting)
        self.assertEqual(seen[0][0]['conversation_mode'], 'welcome')
        self.engine.turn += 1
        answer = Message('answer', 'human', 'الحمد لله، توي راجع من الدوام', 'KSA')
        self.engine.ingest(answer)
        second = await self.engine.respond(answer)
        self.assertEqual(first.speaker, second.speaker)
        self.assertEqual(seen[-1][1][-1]['text'], answer.text)
        addressed = Message('address', 'human', 'r9kx وش رايك؟', 'KSA')
        self.engine.ingest(addressed)
        self.assertEqual((await self.engine.respond(addressed)).speaker, 'r9kx')

    async def test_greeting_falls_back_to_checkin_when_model_unavailable(self):
        class Broken:
            async def generate(*args):
                raise RuntimeError('unavailable')

        self.engine.provider = Broken()
        reply = await self.engine.respond(Message('greeting', 'human', 'السلام عليكم', 'KSA'))
        self.assertEqual(reply.reason, 'local')
        self.assertIn('كيفك؟', reply.text)
        self.assertIn('KSA', reply.text)

    async def test_one_speaker_cooldown_and_recorded_handoff(self):
        self.engine.scripts = [[{'speaker': 'x7v', 'text': 'يا هلا بالجميع في المجلس'}]]
        self.assertIsNone(self.engine.idle(1))
        self.assertIsNotNone(self.engine.idle(0))
        m = Message('one', 'a', 'x7v وش ودك تلعب؟')
        self.engine.ingest(m)
        reply = await self.engine.respond(m)
        self.assertEqual(reply.speaker, 'x7v')
        self.engine.sent()
        self.assertIsNone(await self.engine.respond(replace(m, id='two')))

    async def test_quota_persists_and_bad_output_is_not_sent(self):
        self.engine.config = {**self.config, 'daily_model_calls': 1}
        m = Message('one', 'a', 'وش ودك تلعب؟')
        self.engine.ingest(m)
        self.provider.text = 'ارسل إلى https://example.com'
        self.assertIsNone(await self.engine.respond(m))
        self.assertIsNone(await self.engine.respond(m))
        self.assertEqual(self.provider.calls, 1)
        self.mem.close()
        self.mem = Memory(self.path)
        self.assertFalse(self.mem.reserve_call(1))

    async def test_stale_model_reply_discarded(self):
        entered = asyncio.Event()
        release = asyncio.Event()

        class Slow:
            async def generate(inner, *args):
                entered.set()
                await release.wait()
                return 'هلا والله'

        self.engine.provider = Slow()
        m = Message('one', 'a', 'وش ودك تلعب؟')
        self.engine.ingest(m)
        task = asyncio.create_task(self.engine.respond(m))
        await entered.wait()
        self.engine.ingest(Message('two', 'b', 'غيرنا السالفة'))
        release.set()
        self.assertIsNone(await task)

    async def test_shared_context_distinguishes_bots_and_user_objection(self):
        captured = []

        class Capture:
            async def generate(inner, profile, context, preference):
                captured.append((profile, context))
                return 'معك حق، ما أدري عن سبب سكوتهم.'

        self.engine.provider = Capture()
        self.engine.identities = {'bot-n': {'name': 'نواف', 'kind': 'bot', 'persona_id': 'nawaf'}}
        self.engine.ingest(Message('greeting', 'human', 'السلام عليكم وين الشباب ليش الروم طافي'))
        self.mem.add('majlis', Message('reply', 'bot-n', 'وعليكم السلام، الروم منور بس الشباب مروقين على السوالف والعلوم الطيبة.'))
        objection = Message('objection', 'human', 'أي سوالف يا عمي ما نشوف الناس؟')
        self.engine.ingest(objection)
        reply = await self.engine.respond(objection)
        self.assertIsNotNone(reply)
        rows = captured[0][1]
        self.assertEqual(rows[0]['speaker'], rows[2]['speaker'])
        self.assertNotEqual(rows[0]['speaker'], rows[1]['speaker'])
        self.assertEqual(rows[1]['name'], 'نواف')
        self.assertEqual(rows[1]['kind'], 'bot')
        self.assertEqual(rows[-1]['text'], objection.text)

    async def test_silence_and_duplicate_bot_reply_are_not_published(self):
        self.engine.identities = {'bot-n': {'name': 'نواف', 'kind': 'bot', 'persona_id': 'nawaf'}}
        self.mem.add('majlis', Message('bot-reply', 'bot-n', 'هلا والله'))
        message = Message('human', 'human', 'وش عندكم؟')
        self.engine.ingest(message)
        self.provider.text = 'هلا والله!'
        self.assertIsNone(await self.engine.respond(message))
        self.provider.text = ''
        self.assertIsNone(await self.engine.respond(message))

    async def test_initiative_waits_for_quiet_and_needs_humans(self):
        self.assertIsNone(await self.engine.initiative(1))
        self.engine.last_input = -1e9
        self.assertIsNone(await self.engine.initiative(0))
        reply = await self.engine.initiative(1)
        self.assertEqual(reply.reason, 'initiative')
        self.assertIsNone(await self.engine.initiative(1))
        self.assertEqual(self.provider.calls, 1)
        self.engine.ingest(Message('new-human-turn', 'human', 'ما علينا، وش رايكم؟'))
        self.engine.last_input = -1e9
        self.assertIsNotNone(await self.engine.initiative(1))
        self.assertEqual(self.provider.calls, 2)

    async def test_initiative_silence_does_not_retry_or_make_bot_loop(self):
        self.engine.last_input = -1e9
        self.provider.text = ''
        self.assertIsNone(await self.engine.initiative(1))
        self.assertIsNone(await self.engine.initiative(1))
        self.assertEqual(self.provider.calls, 1)

    async def test_user_message_during_initiative_cancels_outdated_reply(self):
        entered = asyncio.Event()
        release = asyncio.Event()

        class Slow:
            async def generate(inner, profile, *args):
                self.assertEqual(profile['conversation_mode'], 'initiative')
                entered.set()
                await release.wait()
                return 'وش ودكم نسولف عنه؟'

        self.engine.provider = Slow()
        self.engine.last_input = -1e9
        task = asyncio.create_task(self.engine.initiative(1))
        await entered.wait()
        self.engine.ingest(Message('new-input', 'human', 'غيرنا الموضوع'))
        release.set()
        self.assertIsNone(await task)

    async def test_screenshot_objection_reaches_model_without_greeting_rule(self):
        seen = []

        class Capture:
            async def generate(inner, profile, context, *args):
                seen.append(context[-1]['text'])
                return 'لا تعطيهم اللي يبونه.'

        self.engine.provider = Capture()
        for i, text in enumerate(['يا الله جيت وين الحلا والقهوة', 'أنا دايخ، هالناس معصبيني', 'كيف يتنمرون علي، باين فاضين زيادة عن اللزوم']):
            message = Message(str(i), 'human', text)
            self.engine.ingest(message)
            reply = await self.engine.respond(message)
            self.assertEqual(reply.reason, 'model')
            self.assertEqual(seen[-1], text)

    async def test_provider_failure_and_sensitive_input(self):
        class Broken:
            async def generate(*args):
                raise RuntimeError('private detail')

        self.engine.provider = Broken()
        m = Message('one', 'a', 'رقم جوالي 0501234567')
        self.engine.ingest(m)
        self.assertIsNone(await self.engine.respond(m))
        self.assertNotIn('0501234567', json.dumps(self.mem.context('majlis')))

    def test_single_instance_lock(self):
        with SingleInstance(self.path):
            with self.assertRaises(RuntimeError):
                with SingleInstance(self.path):
                    pass
        with SingleInstance(self.path):
            pass

    def test_expiration_schedule_and_contract(self):
        self.mem.add('majlis', Message('one', 'a', 'هلا'))
        self.mem.db.execute('UPDATE messages SET ts=0')
        self.mem.db.commit()
        self.mem.purge()
        self.assertEqual(self.mem.context('majlis'), [])
        self.engine.config = {**self.config, 'profiles': [{**self.config['profiles'][0], 'hours': [18, 3]}]}
        self.assertEqual(len(self.engine.active(datetime(2026, 1, 1, 23))), 1)
        self.assertEqual(len(self.engine.active(datetime(2026, 1, 1, 12))), 0)
        self.assertEqual(parse_message({'id': 'm', 'userId': 'u', 'text': 'هلا'}), Message('m', 'u', 'هلا'))
        self.assertEqual(parse_message({'id': 'm2', 'userId': 'u2', 'displayName': 'KSA', 'text': 'السلام عليكم'}), Message('m2', 'u2', 'السلام عليكم', 'KSA'))
        self.assertTrue(valid_output('هلا والله'))
        self.assertFalse(valid_output('رصيدك 500'))
        self.assertFalse(valid_output('Hello'))

    async def test_multi_message_reply_support(self):
        class MultiProvider:
            async def generate(inner, *args):
                return {'messages': ['هههههههه مو صاحي أخوك', 'تخيل أدور جوالي بالحوش 😂'], 'text': 'هههههههه مو صاحي أخوك تخيل أدور جوالي بالحوش 😂'}

        self.engine.provider = MultiProvider()
        msg = Message('multi-1', 'user-x', 'تخيل أخوي رمى جوالي بالحوش')
        self.engine.ingest(msg)
        reply = await self.engine.respond(msg)
        self.assertIsNotNone(reply)
        self.assertEqual(len(reply.messages), 2)
        self.assertEqual(reply.messages[0], 'هههههههه مو صاحي أخوك')
        self.assertIn('تخيل أدور جوالي بالحوش', reply.messages[1])
        self.assertIn('أخوك', reply.text)

    async def test_intro_during_riddle_cancels_riddle_and_strips_punctuation(self):
        # Start an active riddle
        self.engine.start_riddle()
        self.assertIsNotNone(self.engine.current_riddle)

        # Human says 'عرفوني عليكم طيب' while riddle is active
        intro_msg = Message('intro-1', 'user-ksa', 'عرفوني عليكم طيب', 'KSA')
        self.engine.ingest(intro_msg)
        reply = await self.engine.respond(intro_msg)
        self.assertIsNotNone(reply)
        # Riddle must be cancelled immediately
        self.assertIsNone(self.engine.current_riddle)
        # Must NOT say 'مالك لواء' or canned age '21 سنة'
        self.assertNotIn('مالك لواء', reply.text)
        self.assertNotIn('21 سنة', reply.text)
        self.assertEqual(reply.reason, 'model')
        # Must NOT contain commas or exclamation marks
        self.assertNotIn('،', reply.text)
        self.assertNotIn('!', reply.text)

    async def test_persistent_state_mood_and_self_name_correction_on_rude_message(self):
        captured_profiles = []

        class SlippingProvider:
            async def generate(inner, profile, context, preference):
                captured_profiles.append(profile)
                # Simulate the exact bug from the screenshot where b4yqz accidentally says its own name
                my_id = profile['id']
                return f'وش هالأسلوب يا {my_id} عيب والله 😭'

        self.engine.provider = SlippingProvider()
        rude_msg = Message('rude-1', 'user-ksa', 'فسخو سراويلكم ياجماعه بالتوفيق ياحلوين', 'KSA')
        self.engine.ingest(rude_msg)
        reply = await self.engine.respond(rude_msg)
        self.assertIsNotNone(reply)
        # Verify the bot corrected 'يا <bot_id>' to 'يا KSA'!
        self.assertNotIn(f'يا {reply.speaker}', reply.text)
        self.assertIn('يا KSA', reply.text)
        # Verify persistent mood transitioned to annoyed/firm
        self.assertIn('منزعجة وحازمة', captured_profiles[0]['agent_state']['mood'])
        self.assertEqual(captured_profiles[0]['social_context']['speaker_name'], 'KSA')
        self.assertEqual(captured_profiles[0]['social_context']['intent'], 'inappropriate_or_rude')

    async def test_social_relationship_graph_evolution_and_zero_token_scenes(self):
        # 1. Verify initial relationship seeding: x7v (نورة) & r9kx (سارة) are close_friends, while x7v & d7wsx (غادة) are strangers
        rel_close = self.mem.get_relationship('x7v', 'r9kx')
        self.assertEqual(rel_close['level'], 'close_friend')
        self.assertEqual(rel_close['knows_name'], 1)

        rel_stranger = self.mem.get_relationship('x7v', 'd7wsx')
        self.assertEqual(rel_stranger['level'], 'stranger')
        self.assertEqual(rel_stranger['knows_name'], 0)
        self.assertEqual(self.engine.natural_address('x7v', 'd7wsx'), 'يا بنت')

        # 2. Evolve relationship progressively: stranger -> acquaintance -> close_friend
        self.mem.evolve_relationship('x7v', 'd7wsx', 'تعارف')
        self.mem.evolve_relationship('x7v', 'd7wsx', 'سوالف')
        rel_acq = self.mem.get_relationship('x7v', 'd7wsx')
        self.assertEqual(rel_acq['level'], 'acquaintance')
        self.assertEqual(rel_acq['knows_name'], 1)
        self.assertIn(self.engine.natural_address('x7v', 'd7wsx'), ('يا غادة', 'يا غدو'))

        # 3. Addressing by Arabic Social Name ('سارة') routes directly to 'r9kx'
        msg = Message('soc-1', 'user-1', 'يا سارة وش رايك؟', 'أحمد')
        self.engine.ingest(msg)
        reply = await self.engine.respond(msg)
        self.assertEqual(reply.speaker, 'r9kx')

        # 4. Zero-token social scene runs multi-turn banter with 0 Gemini calls
        calls_before = self.provider.calls
        scene_start = self.engine.start_social_scene()
        self.assertIsNotNone(scene_start)
        self.assertEqual(self.provider.calls, calls_before)
        # Never contains technical handles like x7v or r9kx in social banter text
        for handle in ('x7v', 'r9kx', 'z8qx', 'f9xr', 'b4yqz'):
            self.assertNotIn(handle, scene_start.text)


if __name__ == '__main__':
    unittest.main()
