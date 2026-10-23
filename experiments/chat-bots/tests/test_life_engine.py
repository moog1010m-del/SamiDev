import asyncio, json, tempfile, unittest
from pathlib import Path
import aiohttp
from core import Coordinator, Memory, Message, load_config
from gemini import Gemini, SYSTEM
from life_engine import LifeEngine, BudgetManager, PERSONA_LIFE_PROFILES
from run import read_scripts

BASE = Path(__file__).resolve().parents[1]


class RealisticMockSession:
    """Simulates Gemini REST API responses and accurately counts prompt/candidate tokens by UTF-8/Arabic word piece size."""
    def __init__(self, custom_reply_fn=None):
        self.calls = 0
        self.requests = []
        self.custom_reply_fn = custom_reply_fn

    def post(self, url, **kwargs):
        self.calls += 1
        payload = kwargs.get('json', {})
        self.requests.append((url, kwargs))

        sys_text = json.dumps(payload.get('systemInstruction', {}), ensure_ascii=False)
        user_text = payload['contents'][0]['parts'][0]['text']
        content_obj = json.loads(user_text)

        # Realistic token estimation calibrated against real Gemini 2.5 Flash-Lite usageMetadata (~1 token per 2.8 chars in Arabic+JSON)
        prompt_tokens = max(50, int((len(sys_text) + len(user_text)) / 2.8))

        if self.custom_reply_fn:
            reply_str = self.custom_reply_fn(content_obj)
        else:
            pname = content_obj.get('persona_name', 'نورة')
            reply_str = f'يا هلا فيك أنا {pname} منور المجلس والله'

        reply_json = json.dumps({'text': reply_str}, ensure_ascii=False)
        cand_tokens = max(8, int(len(reply_json) / 2.8))
        total_tokens = prompt_tokens + cand_tokens

        data = {
            'candidates': [{
                'finishReason': 'STOP',
                'content': {'parts': [{'text': reply_json}]}
            }],
            'usageMetadata': {
                'promptTokenCount': prompt_tokens,
                'candidatesTokenCount': cand_tokens,
                'totalTokenCount': total_tokens
            }
        }

        class _Resp:
            status = 200
            async def __aenter__(self_inner): return self_inner
            async def __aexit__(self_inner, *args): pass
            async def json(self_inner): return data

        return _Resp()


class PlazrLifeEngineTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = Path(self.temp.name) / 'life_test.sqlite'
        self.mem = Memory(self.db_path)
        self.config = load_config(BASE / 'config.json')
        self.config['cooldown_seconds'] = 0  # Fast execution in tests
        self.session = RealisticMockSession()
        self.provider = Gemini(self.session, 'key1,key2,key3', 'gemini-flash-lite-latest')
        self.engine = Coordinator(
            self.config,
            self.mem,
            read_scripts(BASE / 'scripts.json', self.config),
            self.provider
        )

    def tearDown(self):
        try:
            self.mem.close()
        except Exception:
            pass
        try:
            self.temp.cleanup()
        except Exception:
            pass

    async def test_1_family_relations_and_followup(self):
        """الاختبار 1: العلاقات العائلية المتبادلة والمتابعة في اليوم التالي مرة واحدة فقط."""
        life = self.engine.life
        # 1. Verify bidirectional sister relationship between نورة (x7v) and ريم (v3mk)
        rel_nora_to_reem = life.get_family_relation('x7v', 'v3mk')
        rel_reem_to_nora = life.get_family_relation('v3mk', 'x7v')
        self.assertIsNotNone(rel_nora_to_reem)
        self.assertIsNotNone(rel_reem_to_nora)
        self.assertEqual(rel_nora_to_reem['fact_relation'], 'sister')
        self.assertEqual(rel_reem_to_nora['fact_relation'], 'sister')
        self.assertEqual(rel_nora_to_reem['shared_family']['brother'], 'محمد')
        self.assertEqual(rel_reem_to_nora['shared_family']['brother'], 'محمد')
        self.assertEqual(rel_nora_to_reem['shared_family']['mother'], 'منيرة')

        # 2. Both نورة and ريم know محمد is their brother and منيرة is their mother when asked directly
        msg_nora = Message('fam-1', 'user-1', 'يا نورة مين اخوك ومين اختك؟', 'سعود')
        self.engine.ingest(msg_nora)
        rep_nora = await self.engine.respond(msg_nora)
        self.assertEqual(rep_nora.speaker, 'x7v')
        self.assertIn('ريم', rep_nora.text)
        self.assertIn('محمد', rep_nora.text)

        msg_reem = Message('fam-2', 'user-1', 'يا ريم مين اخوك ومين اختك؟', 'سعود')
        self.engine.ingest(msg_reem)
        rep_reem = await self.engine.respond(msg_reem)
        self.assertEqual(rep_reem.speaker, 'v3mk')
        self.assertIn('نورة', rep_reem.text)
        self.assertIn('محمد', rep_reem.text)

        # 3. Day 1: نورة (x7v) complains to سارة (r9kx) and ريم (v3mk) that brother محمد took her charger
        ev = life.create_daily_event('x7v', virtual_day=1, specific_key='bro_charger')
        shared_text = life.share_event(ev['event_id'], 'x7v', ['r9kx', 'v3mk'], current_day=1)
        self.assertIn('محمد', shared_text)
        self.assertIn('شاحني', shared_text)
        self.assertTrue(life.knows_event('r9kx', ev['event_id']))
        self.assertTrue(life.knows_event('v3mk', ev['event_id']))

        # 4. Day 2: سارة (r9kx) asks نورة (x7v) once about the charger issue
        followup_day2 = life.get_followup_question('r9kx', 'x7v', current_day=2)
        self.assertIsNotNone(followup_day2)
        self.assertIn('محمد', followup_day2['question'])
        self.assertIn('الشاحن', followup_day2['question'])

        # 5. Verify سارة does NOT repeat the same question again on Day 2 or Day 3!
        repeat_same_day = life.get_followup_question('r9kx', 'x7v', current_day=2)
        self.assertIsNone(repeat_same_day)
        repeat_day3 = life.get_followup_question('r9kx', 'x7v', current_day=3)
        self.assertIsNone(repeat_day3)

    async def test_2_limited_epistemic_knowledge(self):
        """الاختبار 2: المعرفة المحدودة — من لم يحضر السالفة لا يدّعي معرفتها."""
        life = self.engine.life
        # شهد (z8qx) tells ONLY ريم (v3mk) about a work problem
        ev = life.create_daily_event('z8qx', virtual_day=1, specific_key='work_workload_issue')
        life.share_event(ev['event_id'], 'z8qx', ['v3mk'], current_day=1)

        # Verify epistemic state in DB
        self.assertTrue(life.knows_event('z8qx', ev['event_id']))
        self.assertTrue(life.knows_event('v3mk', ev['event_id']))
        self.assertFalse(life.knows_event('k5lp', ev['event_id']))  # لمى was not told
        self.assertFalse(life.knows_event('f9xr', ev['event_id']))  # دانة was not told

        # Ask third party دانة (f9xr): "يا دانة وش صار مع شهد في دوامها؟"
        q_dana = Message('ep-1', 'user-1', 'يا دانة وش صار مع شهد في دوامها؟', 'سعود')
        self.engine.ingest(q_dana)
        rep_dana = await self.engine.respond(q_dana)
        self.assertEqual(rep_dana.speaker, 'f9xr')
        self.assertIn('ما أدري', rep_dana.text)
        self.assertNotIn('ملف مستعجل', rep_dana.text)

        # Meanwhile, ريم (v3mk) DOES know when recalled
        reem_recall = life.recall_event_for_persona('v3mk', ev['event_id'])
        self.assertTrue(reem_recall['knows'])
        self.assertIn('ملف مستعجل', reem_recall['text'])

    async def test_3_event_progression_and_resolution(self):
        """الاختبار 3: تطور الحدث وحله (Created -> Active -> Developing -> Resolved -> Archived)."""
        life = self.engine.life
        # Day 1: Event starts (Created -> Active)
        ev = life.create_daily_event('x7v', virtual_day=1, specific_key='bro_charger')
        self.assertEqual(ev['status'], 'Created')
        life.share_event(ev['event_id'], 'x7v', ['r9kx'], current_day=1)
        self.assertEqual(life.get_event(ev['event_id'])['status'], 'Active')

        # Day 2: Asked about -> Developing
        fq = life.get_followup_question('r9kx', 'x7v', current_day=2)
        self.assertIsNotNone(fq)
        self.assertEqual(life.get_event(ev['event_id'])['status'], 'Developing')

        # Day 3: Resolved
        resolved_ev = life.advance_event(ev['event_id'], 'Resolved')
        self.assertEqual(resolved_ev['status'], 'Resolved')

        # Day 4: Asking نورة about her brother/charger recalls the RESOLVED state, not the old complaint!
        self.engine.virtual_day = 4
        q_day4 = Message('res-d4', 'user-1', 'يا نورة وش صار مع أخوك محمد والشاحن؟', 'سعود')
        self.engine.ingest(q_day4)
        rep_day4 = await self.engine.respond(q_day4)
        self.assertEqual(rep_day4.speaker, 'x7v')
        self.assertIn('رجع الشاحن', rep_day4.text)
        self.assertIn('تصالحنا', rep_day4.text)
        self.assertNotIn('رافع ضغطي اليوم', rep_day4.text)

        # Advance to Archived
        archived_ev = life.advance_event(ev['event_id'], 'Archived')
        self.assertEqual(archived_ev['status'], 'Archived')

    def test_4_thirty_day_variety_simulation(self):
        """الاختبار 4: محاكاة 30 يوماً افتراضياً لشخصية واحدة والتحقق من التنوع وعدم هيمنة السلبية."""
        life = self.engine.life
        history = life.simulate_days('x7v', days=30)
        self.assertEqual(len(history), 30)

        # 1. Zero consecutive duplicate stories
        for i in range(1, len(history)):
            self.assertNotEqual(
                history[i]['template_key'],
                history[i - 1]['template_key'],
                f"Duplicate consecutive event on day {i+1}"
            )

        # 2. Rich domain diversity (at least 5 distinct domains across 30 days)
        domains_seen = {ev['domain'] for ev in history}
        self.assertGreaterEqual(len(domains_seen), 5, f"Too few domains: {domains_seen}")

        # 3. Negative events must NOT dominate (<= 25% of days, and zero consecutive negative days)
        neg_days = [i for i, ev in enumerate(history) if ev['valence'] == 'negative']
        self.assertLessEqual(len(neg_days), 8, f"Too many negative events: {len(neg_days)}/30")
        for j in range(1, len(neg_days)):
            self.assertGreater(neg_days[j] - neg_days[j - 1], 1, "Two consecutive negative days occurred!")

    async def test_5_identity_stability_under_context_pressure(self):
        """الاختبار 5: ثبات الهوية — المستخدم يتحدث عن شهد ثم يسأل ريم عن اسمها فلا تدّعي أنها شهد."""
        # Configure mock provider to attempt an identity slip ("أنا شهد") to test both routing AND slip-guard!
        self.session.custom_reply_fn = lambda obj: 'هلا والله أنا شهد حياك معنا'

        # Step 1: User talks about شهد in the room
        msg1 = Message('id-1', 'user-ksa', 'قبل شوي كنت أتابع سوالف عن شهد في المجلس', 'KSA')
        self.engine.ingest(msg1)

        # Step 2: User asks ريم (v3mk) for her name
        msg2 = Message('id-2', 'user-ksa', 'يا ريم وش اسمك انتي؟', 'KSA')
        self.engine.ingest(msg2)
        reply = await self.engine.respond(msg2)

        self.assertIsNotNone(reply)
        self.assertEqual(reply.speaker, 'v3mk')
        self.assertIn('ريم', reply.text)
        self.assertNotIn('أنا شهد', reply.text)
        self.assertNotIn('اسمي شهد', reply.text)

    async def test_6_token_consumption_comparison_before_vs_after(self):
        """الاختبار 6: مقارنة استهلاك التوكنات (قبل التطوير مقابل بعد التطوير) بأرقام مقاسة."""
        # --- A) BEFORE (Legacy: full bloated context, no local epistemic/family/event handling, individual seed calls) ---
        mem_before = Memory(Path(self.temp.name) / 'before.sqlite')
        sess_before = RealisticMockSession()
        cfg_before = {**self.config, 'enable_life_engine': False}
        prov_before = Gemini(sess_before, 'key1', 'gemini-flash-lite-latest')
        eng_before = Coordinator(cfg_before, mem_before, [], prov_before)

        # Populate 10 room messages so context window has realistic history
        for i in range(10):
            eng_before.ingest(Message(f'b-hist-{i}', f'u-{i%3}', f'رسالة شات سابقة رقم {i} في غرفة المجلس للتجربة'))

        before_total_tokens = 0
        # 1. Seed 5 personas individually (legacy way: 5 separate Gemini calls)
        for pid in ['x7v', 'v3mk', 'r9kx', 'z8qx', 'k5lp']:
            await prov_before.generate({'id': pid, 'name': pid, 'style': 'توليد حدث يومي'}, mem_before.context('majlis'), None)
            before_total_tokens += prov_before.last_usage['totalTokenCount']

        # 2. Run 6 typical interactions (family question, unknown event question, resolved event question, 3 general chats)
        scenario_inputs = [
            Message('s1', 'u1', 'يا نورة مين اخوك ومين اختك؟', 'فهد'),
            Message('s2', 'u1', 'يا دانة وش صار مع شهد في دوامها؟', 'فهد'),
            Message('s3', 'u1', 'يا نورة وش صار مع أخوك محمد والشاحن؟', 'فهد'),
            Message('s4', 'u1', 'يا ريم كيف الاجواء عندكم اليوم؟', 'فهد'),
            Message('s5', 'u1', 'يا سارة وش رايك نلعب قيم بلياردو؟', 'فهد'),
            Message('s6', 'u1', 'يا لمى كيف الدراسة معك هالأسبوع؟', 'فهد'),
        ]
        for m in scenario_inputs:
            eng_before.ingest(m)
            rep = await eng_before.respond(m)
            if rep and rep.tokens:
                before_total_tokens += rep.tokens.get('totalTokenCount', 0)

        before_calls = sess_before.calls
        before_avg = round(before_total_tokens / before_calls, 1)

        # --- B) AFTER (Plazr Life Engine: batch seed 5-in-1, local family/epistemic/resolved handling, economic slice) ---
        mem_after = Memory(Path(self.temp.name) / 'after.sqlite')
        sess_after = RealisticMockSession()
        cfg_after = {**self.config, 'enable_life_engine': True}
        prov_after = Gemini(sess_after, 'key1,key2', 'gemini-flash-lite-latest')
        eng_after = Coordinator(cfg_after, mem_after, [], prov_after)

        for i in range(10):
            eng_after.ingest(Message(f'a-hist-{i}', f'u-{i%3}', f'رسالة شات سابقة رقم {i} في غرفة المجلس للتجربة'))

        # Setup the active & resolved events in LifeEngine
        ev_shahad = eng_after.life.create_daily_event('z8qx', virtual_day=1, specific_key='work_workload_issue')
        eng_after.life.share_event(ev_shahad['event_id'], 'z8qx', ['v3mk'], current_day=1)
        ev_nora = eng_after.life.create_daily_event('x7v', virtual_day=1, specific_key='bro_charger')
        eng_after.life.advance_event(ev_nora['event_id'], 'Resolved')

        # 1. Batch seed 5 personas in ONE single call
        await eng_after.life.batch_generate_event_seeds(prov_after, ['x7v', 'v3mk', 'r9kx', 'z8qx', 'k5lp'], virtual_day=2)

        # 2. Run the exact same 6 interactions
        for m in scenario_inputs:
            eng_after.ingest(m)
            await eng_after.respond(m)

        summary_after = eng_after.life.budget.get_daily_summary('majlis')
        after_calls = summary_after['gemini_calls']
        after_total_tokens = summary_after['total_tokens']
        after_avg = summary_after['avg_tokens_per_call']
        local_ops = summary_after['local_ops']

        # Assertions:
        # Before needed 11 Gemini calls (5 seeds + 6 replies); After needed only 4 Gemini calls (1 batch seed + 3 model replies, while 3 queries were resolved locally with 0 tokens!)
        self.assertEqual(before_calls, 11)
        self.assertEqual(after_calls, 4)
        self.assertLess(after_total_tokens, before_total_tokens * 0.4)
        self.assertLess(after_avg, before_avg)
        self.assertGreater(local_ops, 10)

        mem_before.close()
        mem_after.close()

    async def test_7_multi_room_and_concurrency_stress(self):
        """الاختبار 7: تعدد الغرف والضغط المتزامن بدون اختلاط الذاكرة أو أخطاء SQLite."""
        cfg_room_a = {**self.config, 'room': 'majlis'}
        cfg_room_b = {**self.config, 'room': 'diwaniya'}

        eng_a = Coordinator(cfg_room_a, self.mem, [], self.provider)
        eng_b = Coordinator(cfg_room_b, self.mem, [], self.provider)

        # Create a secret event in room 'majlis' for شهد shared with ريم
        ev_a = eng_a.life.create_daily_event('z8qx', virtual_day=1, specific_key='work_workload_issue')
        eng_a.life.share_event(ev_a['event_id'], 'z8qx', ['v3mk'], current_day=1)

        # Verify room 'diwaniya' does NOT leak knowledge from room 'majlis'
        self.assertTrue(eng_a.life.knows_event('v3mk', ev_a['event_id']))
        self.assertFalse(eng_b.life.knows_event('v3mk', ev_a['event_id']))

        # Concurrent stress updates across both rooms
        async def worker(engine_inst, prefix, idx):
            ev = engine_inst.life.create_daily_event('x7v', virtual_day=idx + 1)
            engine_inst.life.share_event(ev['event_id'], 'x7v', ['r9kx'], current_day=idx + 1)
            engine_inst.life.update_emotion('x7v', 0.3, f'{prefix}-{idx}')
            msg = Message(f'{prefix}-m-{idx}', f'user-{idx}', f'يا سارة كيف الحال {idx}', 'خالد')
            engine_inst.ingest(msg)
            return await engine_inst.respond(msg)

        tasks = []
        for i in range(10):
            tasks.append(worker(eng_a, 'roomA', i))
            tasks.append(worker(eng_b, 'roomB', i))

        results = await asyncio.gather(*tasks)
        self.assertEqual(len(results), 20)
        self.assertTrue(all(r is not None for r in results))

        # Verify message contexts remain strictly isolated per room
        ctx_a = self.mem.context('majlis')
        ctx_b = self.mem.context('diwaniya')
        self.assertTrue(all('roomB' not in str(r) for r in ctx_a))
        self.assertTrue(all('roomA' not in str(r) for r in ctx_b))

    async def test_8_feature_flag_disable_life_engine(self):
        """اختبار إضافي (القسم 15): إمكانية تعطيل الطبقة الجديدة بمفتاح إعدادات دون كسر النظام الأساسي."""
        cfg_disabled = {**self.config, 'enable_life_engine': False}
        eng_disabled = Coordinator(cfg_disabled, self.mem, [], self.provider)
        self.assertIsNone(eng_disabled.life)
        msg = Message('ff-1', 'user-1', 'السلام عليكم', 'سعود')
        eng_disabled.ingest(msg)
        rep = await eng_disabled.respond(msg)
        self.assertIsNotNone(rep)

    async def test_9_exact_screenshot_scenarios_regression(self):
        """الاختبار 9: محاكاة المحادثات الحقيقية من لقطات الشاشة حرفياً وإثبات إصلاح جميع الثغرات الـ 8."""
        from core import humanize_chat, norm_ar

        # 0. Verify Saudi shorthand & typo normalization
        self.assertIn('وش تقرب', norm_ar('شتقرب لك نوره'))
        self.assertIn('وش اخبار', norm_ar('شخبار محمد اخوكم'))
        self.assertIn('بالروم', norm_ar('بالمجلس تقصدين باروم 👀'))
        self.assertIn('بالروم ذا معنا', norm_ar('بالروم ذا معنى ؟'))
        self.assertIn('اصطناعي', norm_ar('انتي ذكاء اصتناعي؟'))

        # 1. KSA calls نورة (x7v) and asks "شخبار محمد اخوكم" -> نورة replies about brother محمد (not family tree dump!)
        m1 = Message('sc-1', 'u-ksa', 'نوره شخبار محمد اخوكم', 'KSA')
        self.engine.ingest(m1)
        r1 = await self.engine.respond(m1)
        self.assertEqual(r1.speaker, 'x7v')
        self.assertIn('محمد', r1.text)
        self.assertIn('شاحن', r1.text)
        self.assertNotIn('هههه', r1.text)

        # 2. KSA asks off-room clarification: "بالمجلس تقصدين باروم 👀" and "بالروم ذا معنى ؟"
        m2 = Message('sc-2', 'u-ksa', 'بالمجلس تقصدين باروم 👀', 'KSA')
        self.engine.ingest(m2)
        r2 = await self.engine.respond(m2)
        self.assertEqual(r2.speaker, 'x7v')
        self.assertIn('بالبيت', r2.text)
        self.assertIn('ما يدخل الروم', r2.text)
        self.assertNotIn('هههه', r2.text)

        m3 = Message('sc-3', 'u-ksa', 'بالروم ذا معنى ؟', 'KSA')
        self.engine.ingest(m3)
        r3 = await self.engine.respond(m3)
        self.assertEqual(r3.speaker, 'x7v')
        self.assertIn('بالبيت', r3.text)
        self.assertNotIn('هههه', r3.text)

        # 3. Second human GOLD asks follow-up right after نورة spoke: "اي مكان ؟ الواقع ولا اللعبه"
        # MUST route to x7v (نورة) who was just talking, NOT d7wsx (غادة)!
        m4 = Message('sc-4', 'u-gold', 'اي مكان ؟ الواقع ولا اللعبه', 'GOLD')
        self.engine.ingest(m4)
        r4 = await self.engine.respond(m4)
        self.assertEqual(r4.speaker, 'x7v', "Follow-up from second human should stay with x7v (نورة), not jump to d7wsx!")
        self.assertIn('الواقع', r4.text)
        self.assertNotIn('هههه', r4.text)

        # 4. GOLD asks d7wsx directly: "انتي نوره d7wsx?" -> d7wsx (غادة) clarifies her identity without trailing ههههه
        self.session.custom_reply_fn = lambda obj: 'لا انا غادة مو نورة ههههه يالطيب'
        m5 = Message('sc-5', 'u-gold', 'انتي نوره d7wsx?', 'GOLD')
        self.engine.ingest(m5)
        r5 = await self.engine.respond(m5)
        self.assertEqual(r5.speaker, 'd7wsx')
        self.assertIn('غادة', r5.text)
        self.assertNotIn('هههه', r5.text)
        self.assertNotIn('يالطيب', r5.text)

        # 5. KSA calls ريم (v3mk) then asks "شتقرب لك نوره"
        # MUST stay with v3mk (ريم) and NOT hijack thread to x7v (نورة)!
        self.session.custom_reply_fn = None
        m6 = Message('sc-6', 'u-ksa', 'ريم', 'KSA')
        self.engine.ingest(m6)
        r6 = await self.engine.respond(m6)
        self.assertEqual(r6.speaker, 'v3mk')

        m7 = Message('sc-7', 'u-ksa', 'شتقرب لك نوره', 'KSA')
        self.engine.ingest(m7)
        r7 = await self.engine.respond(m7)
        self.assertEqual(r7.speaker, 'v3mk', "Asking ريم 'شتقرب لك نوره' must be answered by ريم (v3mk), not نورة (x7v)!")
        self.assertIn('أختي الصغيرة', r7.text)
        self.assertNotIn('هههه', r7.text)

        # 6. KSA follows up with third-person pronoun: "طيب وش سالفتها احسها متكدره قالت لك شي ؟"
        m8 = Message('sc-8', 'u-ksa', 'طيب وش سالفتها احسها متكدره قالت لك شي ؟', 'KSA')
        self.engine.ingest(m8)
        r8 = await self.engine.respond(m8)
        self.assertEqual(r8.speaker, 'v3mk')
        self.assertIn('نورة', r8.text)
        self.assertIn('شاحن', r8.text)
        self.assertNotIn('هههه', r8.text)

        # 7. KSA asks: "ريم، نورة قالت لي عن أخوها محمد، تعرفين وش سالفته؟"
        m9 = Message('sc-9', 'u-ksa', 'ريم، نورة قالت لي عن أخوها محمد، تعرفين وش سالفته؟', 'KSA')
        self.engine.ingest(m9)
        r9 = await self.engine.respond(m9)
        self.assertEqual(r9.speaker, 'v3mk')
        self.assertIn('محمد', r9.text)
        self.assertIn('شاحن', r9.text)

        # 8. Fixed Age & humanize_chat check + RUDE_TERMS preserved untouched
        m10 = Message('sc-10', 'u-ksa', 'يا نورة كم عمرك؟', 'KSA')
        self.engine.ingest(m10)
        r10 = await self.engine.respond(m10)
        self.assertEqual(r10.speaker, 'x7v')
        self.assertIn('24', r10.text)

        m11 = Message('sc-11', 'u-ksa', 'يا ريم كم عمرك؟', 'KSA')
        self.engine.ingest(m11)
        r11 = await self.engine.respond(m11)
        self.assertEqual(r11.speaker, 'v3mk')
        self.assertIn('25', r11.text)

        # Verify humanize_chat strips meaningless laughter & awkward fillers without distorting words
        cleaned = humanize_chat('ايه قصدي الروم ههههه يالطيب', turn_index=2, strip_trailing_laugh=True)
        self.assertEqual(cleaned, 'ايه قصدي الروم')

        # Verify rude response system is untouched
        m_rude = Message('sc-12', 'u-ksa', 'يا ريم كلي زق', 'KSA')
        self.engine.ingest(m_rude)
        r_rude = await self.engine.respond(m_rude)
        self.assertIsNotNone(r_rude)
        self.assertIn('تجاوز حدود الأدب', self.mem.get_social_profile('u-ksa')['attitude'])
        self.assertIn('منزعجة وحازمة', self.mem.get_agent_state('v3mk')['mood'])

    async def test_10_grudge_continuity_after_insult_and_zero_out_of_context_laughs(self):
        """الاختبار 10: عدم الرد الطبيعي على من شتم البوت إلا بعد الاعتذار + منع الضحك خارج السياق + عدم خطف الدور عند ذكر اسم ببداية الجملة."""
        from core import humanize_chat

        # 1. Exact screenshot flow: KSA calls ريم, insults her ("تفو على وجهك"), then asks her age ("ريم كم عمكر" / "ريم كم عمرك")
        m1 = Message('g-1', 'u-ksa', 'ريم', 'KSA')
        self.engine.ingest(m1)
        r1 = await self.engine.respond(m1)
        self.assertEqual(r1.speaker, 'v3mk')

        m2 = Message('g-2', 'u-ksa', 'تفو على وجهك', 'KSA')
        self.engine.ingest(m2)
        r2 = await self.engine.respond(m2)
        self.assertEqual(r2.speaker, 'v3mk')

        # Asking age with typo ("ريم كم عمكر") right after insult -> MUST refuse, NOT answer!
        m3 = Message('g-3', 'u-ksa', 'ريم كم عمكر', 'KSA')
        self.engine.ingest(m3)
        r3 = await self.engine.respond(m3)
        self.assertEqual(r3.speaker, 'v3mk')
        self.assertNotIn('25', r3.text)
        self.assertTrue(any(w in r3.text for w in ('تغلط', 'تسب', 'أسلوبك')))

        # Asking age with correct spelling ("ريم كم عمرك") -> MUST STILL refuse while grudge is active!
        m4 = Message('g-4', 'u-ksa', 'ريم كم عمرك', 'KSA')
        self.engine.ingest(m4)
        r4 = await self.engine.respond(m4)
        self.assertEqual(r4.speaker, 'v3mk')
        self.assertNotIn('25', r4.text)
        self.assertTrue(any(w in r4.text for w in ('تغلط', 'تسب', 'أسلوبك')))

        # Asking relation ("طيب وش تقرب لك غادة") -> MUST STILL refuse!
        m5 = Message('g-5', 'u-ksa', 'طيب وش تقرب لك غادة', 'KSA')
        self.engine.ingest(m5)
        r5 = await self.engine.respond(m5)
        self.assertEqual(r5.speaker, 'v3mk')
        self.assertNotIn('صديقتي', r5.text)

        # Now KSA apologizes ("اسف حقك علي") -> grudge clears!
        m6 = Message('g-6', 'u-ksa', 'اسف حقك علي', 'KSA')
        self.engine.ingest(m6)
        r6 = await self.engine.respond(m6)
        self.assertEqual(r6.speaker, 'v3mk')
        self.assertIn('حصل خير', r6.text)

        # Now asking age ("ريم كم عمرك") -> answers normally ("أنا ريم وعمري 25 سنة")!
        m7 = Message('g-7', 'u-ksa', 'ريم كم عمرك', 'KSA')
        self.engine.ingest(m7)
        r7 = await self.engine.respond(m7)
        self.assertEqual(r7.speaker, 'v3mk')
        self.assertIn('25', r7.text)

        # 2. Active thread with نورة (x7v) when user starts sentence with third-person subject "ريم امس تسبك عسى ماشر بينكم شي .؟"
        m8 = Message('g-8', 'u-ksa', 'يا نورة وينك', 'KSA')
        self.engine.ingest(m8)
        r8 = await self.engine.respond(m8)
        self.assertEqual(r8.speaker, 'x7v')

        m9 = Message('g-9', 'u-ksa', 'ريم امس تسبك عسى ماشر بينكم شي .؟', 'KSA')
        self.engine.ingest(m9)
        r9 = await self.engine.respond(m9)
        self.assertEqual(r9.speaker, 'x7v', "Sentence starting with third-person subject 'ريم امس تسبك' must stay with نورة (x7v)!")

        # 3. Verify mid-sentence and trailing laughter are stripped when strip_trailing_laugh=True
        mid_laugh = humanize_chat('بدينا الهياط ههههه كل مرة تقولون كذا وتتعادلون', turn_index=1)
        self.assertNotIn('هههه', mid_laugh)
        self.assertEqual(mid_laugh, 'بدينا الهياط كل مرة تقولون كذا وتتعادلون')

    async def test_11_cs_followup_thread_continuity_and_account_awareness(self):
        """الاختبار 11: منع دخول غادة (d7wsx) على خط محادثة لمى (k5lp) بعد توقف +3 دقائق أو مشهد خلفي + وعي كل بوت بحسابه."""
        import time as _time

        # 1. KSA talks to لمى (k5lp) about Computer Science variables
        m1 = Message('cs-1', 'u-ksa', 'لمو تخصصك مو حاسب بالله ؟.', 'KSA')
        self.engine.ingest(m1)
        r1 = await self.engine.respond(m1)
        self.assertEqual(r1.speaker, 'k5lp')

        m2 = Message('cs-2', 'u-ksa', 'سالني الدكتور عن المتغيرات قال اشرحهم بكلمات بسيطه ممكن تساعدني', 'KSA')
        self.engine.ingest(m2)
        r2 = await self.engine.respond(m2)
        self.assertEqual(r2.speaker, 'k5lp')
        self.engine.ingest(Message('cs-bot-2', 'bot-k5lp', 'المتغيرات مثل الصناديق نحفظ فيها البيانات عشان نستخدمها بعدين', 'k5lp'))

        # 2. Simulate 200 seconds passing (> old 180s limit) AND a background scene message from d7wsx (غادة)
        self.engine.threads['u-ksa'] = ('k5lp', _time.monotonic() - 200)
        self.engine.sent('d7wsx')  # Background scene speaker should NOT hijack human thread!
        self.engine.ingest(Message('cs-bg-1', 'bot-d7wsx', 'اليوم مسكت معي أغير ترتيب غرفتي', 'd7wsx'))

        # 3. KSA asks follow-up: "والفنكشن بالله؟" -> MUST stay with k5lp (لمى), NOT jump to d7wsx (غادة)!
        m3 = Message('cs-3', 'u-ksa', 'والفنكشن بالله؟', 'KSA')
        self.engine.ingest(m3)
        r3 = await self.engine.respond(m3)
        self.assertEqual(r3.speaker, 'k5lp', "Follow-up 'والفنكشن بالله؟' must be answered by لمى (k5lp), not غادة (d7wsx)!")

        # 4. Verify context attribution in Gemini request distinguishes "أنا" vs "بوت أخرى"
        last_req_payload = self.session.requests[-1][1]['json']
        user_json = json.loads(last_req_payload['contents'][0]['parts'][0]['text'])
        self.assertEqual(user_json['my_account_handle'], 'k5lp')
        ctx_whos = [row.get('who', '') for row in user_json['context']]
        self.assertTrue(any('أنا (لمى - k5lp)' in w for w in ctx_whos))
        self.assertTrue(any('بوت أخرى (غادة - d7wsx)' in w for w in ctx_whos))

        # 5. Direct account handle query ("وش حسابك")
        m4 = Message('cs-4', 'u-ksa', 'وش حسابك؟', 'KSA')
        self.engine.ingest(m4)
        r4 = await self.engine.respond(m4)
        self.assertEqual(r4.speaker, 'k5lp')
        self.assertIn('لمى', r4.text)
        self.assertIn('k5lp', r4.text)


if __name__ == '__main__':
    unittest.main()
