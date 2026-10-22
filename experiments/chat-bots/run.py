"""Explicit opt-in sidecar; default demo never opens a network connection."""
import argparse, asyncio, json, os, signal, time, uuid
from contextlib import AsyncExitStack
from pathlib import Path
from urllib.parse import urlsplit
import aiohttp
from core import Coordinator, Memory, Message, load_config
from gemini import Gemini
from single_instance import SingleInstance
from reply_queue import next_reply_message

BASE = Path(__file__).resolve().parent


def read_scripts(path, config):
    if not path or not Path(path).exists():
        return []
    scripts = json.loads(Path(path).read_text(encoding='utf-8'))
    ids = {p['id'] for p in config['profiles']}
    if not isinstance(scripts, list):
        raise ValueError('Scripts must be an array')
    for segment in scripts:
        if not isinstance(segment, list) or not segment:
            raise ValueError('Empty script')
        for line in segment:
            if line['speaker'] not in ids or not isinstance(line['text'], str) or not 1 <= len(line['text']) <= 280:
                raise ValueError('Invalid script line')
    return scripts


async def demo(config, memory, scripts):
    engine = Coordinator(config, memory, scripts)
    for i, text in enumerate(['السلام عليكم', 'لعبتي المفضلة البلياردو', 'تذكرني', 'كم الساعة', 'عطني سنابك']):
        message = Message('demo-' + uuid.uuid4().hex, 'demo-user', text, 'أحمد')
        engine.ingest(message)
        reply = await engine.respond(message)
        print(json.dumps({'input': text, 'reply': reply.text if reply else None, 'speaker': reply.speaker if reply else None}, ensure_ascii=False))
    print('DEMO_OK: local only; no API calls and no room messages')


class Client:
    def __init__(self, session, base):
        self.session = session
        self.base = base
        self.uid = ''

    async def request(self, method, path, body=None):
        async with self.session.request(method, self.base + path, json=body, allow_redirects=False) as response:
            if response.status not in (200, 201):
                if response.status in (409, 429):
                    return {'ok': False, 'status': response.status, 'error': 'transient_conflict'}
                raise RuntimeError('Platform request denied: ' + str(response.status))
            data = await response.json()
            return data


async def live(args, config, memory, scripts):
    base = args.base_url.rstrip('/')
    parsed = urlsplit(base)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path or not parsed.hostname:
        raise ValueError('Expected an origin URL')
    if parsed.scheme != 'https' and not (parsed.scheme == 'http' and parsed.hostname in ('127.0.0.1', 'localhost', '::1')):
        raise ValueError('HTTPS required outside localhost')
    if not args.enable_live:
        raise ValueError('Use --enable-live to explicitly allow room participation')
    active_count = len(Coordinator(config, memory, scripts).active())
    if active_count < 2:
        raise ValueError('At least two active test profiles required')
    if len(config['profiles']) > 16:
        raise ValueError('Live pilot supports up to 16 profiles')
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            signal.signal(sig, lambda *_: loop.call_soon_threadsafe(stop.set))
    async with AsyncExitStack() as stack:
        clients = {}
        for profile in config['profiles']:
            token = os.environ.get(profile['session_env'], '')
            if not token:
                raise ValueError('Missing session environment: ' + profile['session_env'])
            session = await stack.enter_async_context(aiohttp.ClientSession(headers={'Origin': base}, cookies={'samidev_session': token}, timeout=aiohttp.ClientTimeout(total=10)))
            client = Client(session, base)
            user = (await client.request('GET', '/api/me'))['user']
            client.uid = user['id']
            if user.get('role') in ('admin', 'moderator'):
                raise ValueError('Use ordinary accounts, never an administrator')
            clients[profile['id']] = client
        if len({c.uid for c in clients.values()}) != len(clients):
            raise ValueError('Each profile requires its own account')
        model = None
        if args.use_gemini:
            session = await stack.enter_async_context(aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)))
            model = Gemini(session, os.environ.get('GEMINI_API_KEY', ''), os.environ.get('GEMINI_MODEL', ''))
        engine = Coordinator(config, memory, scripts, model)
        pending = asyncio.Queue(maxsize=1)
        human_queued = False
        engine.identities = {
            clients[p['id']].uid: {
                'name': p['name'],
                'kind': 'bot',
                'persona_id': p['id'],
                'gender': p.get('gender', 'female')
            }
            for p in config['profiles']
        }
        print(json.dumps({
            'event': 'behavior_ready',
            'version': 'persistent-agent-state-v4',
            'model': model.model if model else None,
            'initiativeSeconds': config.get('initiative_seconds', 25)
        }), flush=True)
        bot_ids = {c.uid for c in clients.values()}
        members = None
        joined = set()
        last_human = time.monotonic()
        last_idle = 0
        room = '/api/communities/' + config['room']

        async def presence():
            nonlocal members, last_human
            while not stop.is_set():
                active = {p['id'] for p in engine.active()}
                if not active:
                    stop.set()
                    return
                for pid, client in clients.items():
                    try:
                        if pid in active:
                            await client.request('POST', '/api/heartbeat', {})
                            if pid not in joined:
                                res = await client.request('POST', room + '/enter', {})
                                if res.get('ok') is True or res.get('status') == 409:
                                    joined.add(pid)
                        elif pid in joined:
                            await client.request('POST', room + '/leave', {})
                            joined.remove(pid)
                    except Exception:
                        pass
                observer = clients[next(iter(active))]
                state = await observer.request('GET', room + '?chat=0')
                next_members = {u['id'] for u in state.get('members', []) if not u.get('isBot')} - bot_ids
                if members and not next_members:
                    engine.revision += 1
                if next_members:
                    last_human = time.monotonic()
                members = next_members
                memory.purge()
                try:
                    await asyncio.wait_for(stop.wait(), 5)
                except TimeoutError:
                    pass

        async def receive():
            nonlocal human_queued
            observer = next(iter(clients.values()))
            while not stop.is_set():
                async with observer.session.ws_connect(base + '/ws/community/' + config['room'], heartbeat=15, max_msg_size=262144) as socket:
                    async for frame in socket:
                        if frame.type != aiohttp.WSMsgType.TEXT:
                            break
                        data = json.loads(frame.data)
                        if data.get('type') in ('access_denied', 'closed'):
                            raise RuntimeError('Room access denied')
                        if data.get('type') == 'snapshot':
                            print(json.dumps({'event': 'snapshot_ready'}), flush=True)
                            for row in data.get('messages', []):
                                msg = parse_message(row)
                                if msg:
                                    memory.add(config['room'], msg)
                            continue
                        row = data.get('message')
                        msg = parse_message(row) if isinstance(row, dict) else None
                        if msg and engine.ingest(msg):
                            if msg.user_id not in bot_ids:
                                # Human spoke: ALWAYS takes priority, never dropped by bots
                                engine.bot_turns = 0
                                human_queued = True
                                if pending.full():
                                    pending.get_nowait()
                                pending.put_nowait(msg)
                if not stop.is_set():
                    try:
                        await asyncio.wait_for(stop.wait(), 5)
                    except TimeoutError:
                        pass

        async def publish(reply, revision, trigger_text='', is_human_reply=False):
            if stop.is_set() or reply.speaker not in {p['id'] for p in engine.active()}:
                return
            client = clients[reply.speaker]
            msg = reply.text.strip()
            if not msg:
                return

            # Fast response to humans (2.5-4s), relaxed pace for bot-to-bot (4-7s)
            if is_human_reply:
                typing_delay = 2.2 + min(2.0, len(msg) * 0.04)
            else:
                typing_delay = 4.0 + min(3.5, len(msg) * 0.05)

            try:
                await asyncio.wait_for(stop.wait(), typing_delay)
                return
            except TimeoutError:
                pass
            if stop.is_set():
                return

            # If a human spoke while a bot was about to send a pre-scripted riddle/banter message, yield to the human!
            if not is_human_reply and human_queued:
                return

            state = await client.request('GET', room + '?chat=0')
            humans = {u['id'] for u in state.get('members', []) if not u.get('isBot')} - bot_ids
            if reply.reason == 'recorded' and humans:
                return
            try:
                res = await client.request('POST', room + '/chat', {'text': msg, 'clientMessageId': 'bot_' + uuid.uuid4().hex})
                if not res or res.get('ok') is not True:
                    return
            except Exception:
                return

            engine.sent(reply.speaker)

            log_entry = {'event': 'sent', 'speaker': reply.speaker, 'reason': reply.reason, 'text': msg[:60]}
            if reply.tokens:
                tokens_info = {
                    'prompt': reply.tokens.get('promptTokenCount', 0),
                    'reply': reply.tokens.get('candidatesTokenCount', 0),
                    'total': reply.tokens.get('totalTokenCount', 0)
                }
                log_entry['tokens'] = tokens_info
                token_file = BASE / 'state' / 'token_usage.jsonl'
                try:
                    record = {
                        'time': time.strftime('%Y-%m-%d %H:%M:%S'),
                        'speaker': reply.speaker,
                        'user_prompt': trigger_text or '',
                        'bot_reply': reply.text,
                        'prompt_tokens': tokens_info['prompt'],
                        'reply_tokens': tokens_info['reply'],
                        'total_tokens': tokens_info['total']
                    }
                    token_file.parent.mkdir(parents=True, exist_ok=True)
                    with open(token_file, 'a', encoding='utf-8') as f:
                        f.write(json.dumps(record, ensure_ascii=False) + '\n')
                except Exception:
                    pass
            print(json.dumps(log_entry, ensure_ascii=False), flush=True)

        async def work():
            nonlocal last_idle, human_queued
            while not stop.is_set():
                # 1. HIGHEST PRIORITY: Process human messages or queued banter
                if not pending.empty():
                    message, revision = await next_reply_message(pending, engine, config['reply_delay_seconds'])
                    is_from_human = (message.user_id not in bot_ids)
                    if is_from_human and pending.empty():
                        human_queued = False
                    reply = await engine.respond(message)
                    if reply:
                        await publish(reply, revision, message.text, is_human_reply=is_from_human)
                    continue

                # 2. Process scheduled turns (e.g. secondary praise after human solves)
                if engine.turn_queue and engine.ready():
                    reply = engine.turn_queue.pop(0)
                    await publish(reply, engine.revision, is_human_reply=True)
                    continue

                # 3. Advance active riddle when due
                if engine.current_riddle and not engine.current_riddle['solved']:
                    if time.monotonic() >= engine.current_riddle['next_stage_time'] and engine.ready():
                        reply = engine.riddle_tick()
                        if reply:
                            await publish(reply, engine.revision, is_human_reply=False)
                            continue

                # 4. Spontaneous initiative (riddle launch or general conversation)
                now = time.monotonic()
                revision = engine.revision
                reply = await engine.initiative(len(members) if members else 0)
                if reply:
                    await publish(reply, revision, is_human_reply=False)
                    continue

                # 5. Idle fallback
                if (not members or members == set()) and now - last_human >= config['idle_seconds'] and now - last_idle >= config['idle_seconds']:
                    revision = engine.revision
                    reply = engine.idle(0)
                    if reply:
                        await publish(reply, revision, is_human_reply=False)
                        last_idle = now
                        continue

                try:
                    await asyncio.wait_for(stop.wait(), .5)
                except TimeoutError:
                    pass

        tasks = [asyncio.create_task(fn()) for fn in (presence, receive, work)]
        stopper = asyncio.create_task(stop.wait())
        try:
            done, _ = await asyncio.wait([*tasks, stopper], return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if task is not stopper:
                    task.result()
        finally:
            stop.set()
            for task in [*tasks, stopper]:
                task.cancel()
            await asyncio.gather(*tasks, stopper, return_exceptions=True)
            for pid in list(joined):
                try:
                    await clients[pid].request('POST', room + '/leave', {})
                except Exception:
                    pass


def parse_message(row):
    uid = row.get('userId') or row.get('user', {}).get('id')
    if not uid or not row.get('id') or not isinstance(row.get('text'), str):
        return None
    user_obj = row.get('user') or {}
    sender_name = (
        row.get('displayName')
        or row.get('username')
        or user_obj.get('displayName')
        or user_obj.get('username')
        or user_obj.get('name')
        or ''
    ).strip()
    return Message(str(row['id']), str(uid), row['text'][:600], sender_name)


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['demo', 'live'], nargs='?', default='demo')
    parser.add_argument('--config', default=str(BASE / 'config.example.json'))
    parser.add_argument('--scripts', default=str(BASE / 'scripts.example.json'))
    parser.add_argument('--state', default=str(BASE / 'state/memory.sqlite'))
    parser.add_argument('--base-url', default='http://127.0.0.1:56648')
    parser.add_argument('--enable-live', action='store_true')
    parser.add_argument('--use-gemini', action='store_true')
    args = parser.parse_args()
    config = load_config(args.config)
    scripts = read_scripts(args.scripts, config)
    memory = Memory(args.state, config['memory_days'])
    try:
        if args.mode == 'demo':
            await demo(config, memory, scripts)
        else:
            with SingleInstance(args.state):
                await live(args, config, memory, scripts)
    finally:
        memory.close()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
    except Exception as error:
        print('BOT_SIDECAR_STOPPED: ' + type(error).__name__ + ': ' + str(error))
        raise SystemExit(1)
