"""Explicit opt-in sidecar; default demo never opens a network connection."""
import argparse,asyncio,json,os,signal,time,uuid
from contextlib import AsyncExitStack
from pathlib import Path
from urllib.parse import urlsplit
import aiohttp
from core import Coordinator,Memory,Message,load_config
from gemini import Gemini
from single_instance import SingleInstance
BASE=Path(__file__).resolve().parent

def read_scripts(path,config):
    scripts=json.loads(Path(path).read_text(encoding='utf-8'))
    ids={p['id'] for p in config['profiles']}
    if not isinstance(scripts,list):raise ValueError('Scripts must be an array')
    for segment in scripts:
        if not isinstance(segment,list) or not segment:raise ValueError('Empty script')
        for line in segment:
            if line['speaker'] not in ids or not isinstance(line['text'],str) or not 1<=len(line['text'])<=280:raise ValueError('Invalid script line')
    return scripts

async def demo(config,memory,scripts):
    engine=Coordinator(config,memory,scripts)
    # Demo uses actual local rules, no model and no platform credentials.
    for i,text in enumerate(['السلام عليكم','لعبتي المفضلة البلياردو','تذكرني','كم الساعة','عطني سنابك']):
        message=Message('demo-'+uuid.uuid4().hex,'demo-user',text)
        engine.ingest(message)
        reply=await engine.respond(message)
        print(json.dumps({'input':text,'reply':reply.text if reply else None,'speaker':reply.speaker if reply else None},ensure_ascii=False))
    print('DEMO_OK: local only; no API calls and no room messages')

class Client:
    def __init__(self,session,base):self.session=session;self.base=base;self.uid=''
    async def request(self,method,path,body=None):
        async with self.session.request(method,self.base+path,json=body,allow_redirects=False) as response:
            if response.status!=200:raise RuntimeError('Platform request denied: '+str(response.status))
            data=await response.json()
            if data.get('ok') is not True:raise RuntimeError('Platform request rejected')
            return data

async def live(args,config,memory,scripts):
    base=args.base_url.rstrip('/');parsed=urlsplit(base)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path or not parsed.hostname:raise ValueError('Expected an origin URL')
    if parsed.scheme!='https' and not(parsed.scheme=='http' and parsed.hostname in ('127.0.0.1','localhost','::1')):raise ValueError('HTTPS required outside localhost')
    if not args.enable_live:raise ValueError('Use --enable-live to explicitly allow room participation')
    active_count=len(Coordinator(config,memory,scripts).active())
    if active_count<2:raise ValueError('At least two active test profiles required')
    # First experiment intentionally limits live sessions; broad roster is a later stage.
    if len(config['profiles'])>4:raise ValueError('Live pilot supports two to four profiles; split shifts into separate configs')
    stop=asyncio.Event()
    loop=asyncio.get_running_loop()
    for sig in (signal.SIGINT,signal.SIGTERM):
        try:loop.add_signal_handler(sig,stop.set)
        except (NotImplementedError,RuntimeError):pass
    async with AsyncExitStack() as stack:
        clients={}
        for profile in config['profiles']:
            token=os.environ.get(profile['session_env'],'')
            if not token:raise ValueError('Missing session environment: '+profile['session_env'])
            session=await stack.enter_async_context(aiohttp.ClientSession(headers={'Origin':base},cookies={'samidev_session':token},timeout=aiohttp.ClientTimeout(total=10)))
            client=Client(session,base);user=(await client.request('GET','/api/me'))['user'];client.uid=user['id']
            if not any(marker in (user.get('displayName','')+' '+user.get('username','')) for marker in ('بوت','آلي','Bot','bot')):raise ValueError('Test accounts must visibly identify automated participation')
            if user.get('role') in ('admin','moderator'):raise ValueError('Use ordinary accounts, never an administrator')
            clients[profile['id']]=client
        if len({c.uid for c in clients.values()})!=len(clients):raise ValueError('Each profile requires its own account')
        model=None
        if args.use_gemini:
            session=await stack.enter_async_context(aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15)))
            model=Gemini(session,os.environ.get('GEMINI_API_KEY',''),os.environ.get('GEMINI_MODEL',''))
        engine=Coordinator(config,memory,scripts,model);pending=asyncio.Queue(maxsize=1)
        bot_ids={c.uid for c in clients.values()};members=None;joined=set();last_human=time.monotonic();last_idle=0
        room='/api/communities/'+config['room']
        async def presence():
            nonlocal members,last_human
            while not stop.is_set():
                active={p['id'] for p in engine.active()}
                if not active:stop.set();return
                for pid,client in clients.items():
                    if pid in active:
                        await client.request('POST','/api/heartbeat',{})
                        if pid not in joined:await client.request('POST',room+'/enter',{});joined.add(pid)
                    elif pid in joined:
                        await client.request('POST',room+'/leave',{});joined.remove(pid)
                observer=clients[next(iter(active))]
                state=await observer.request('GET',room+'?chat=0')
                next_members={u['id'] for u in state['members']} - bot_ids
                if next_members!=members:engine.revision+=1
                if next_members:last_human=time.monotonic()
                members=next_members
                memory.purge()
                try:await asyncio.wait_for(stop.wait(),5)
                except TimeoutError:pass
        async def receive():
            # Reconnect snapshots are baselines, never replayed as new prompts.
            observer=next(iter(clients.values()))
            while not stop.is_set():
                async with observer.session.ws_connect(base+'/ws/community/'+config['room'],heartbeat=15,max_msg_size=262144) as socket:
                    async for frame in socket:
                        if frame.type!=aiohttp.WSMsgType.TEXT:break
                        data=json.loads(frame.data)
                        if data.get('type') in ('access_denied','closed'):raise RuntimeError('Room access denied')
                        if data.get('type')=='snapshot':
                            print(json.dumps({'event':'snapshot_ready'}),flush=True)
                            for row in data.get('messages',[]):
                                msg=parse_message(row)
                                if msg and msg.user_id not in bot_ids:memory.add(config['room'],msg)
                            continue
                        row=data.get('message')
                        msg=parse_message(row) if isinstance(row,dict) else None
                        if msg and msg.user_id not in bot_ids and engine.ingest(msg):
                            if pending.full():pending.get_nowait()
                            pending.put_nowait(msg)
                if not stop.is_set():
                    try:await asyncio.wait_for(stop.wait(),5)
                    except TimeoutError:pass
        async def publish(reply,revision):
            if stop.is_set() or revision!=engine.revision or reply.speaker not in {p['id'] for p in engine.active()}:return
            client=clients[reply.speaker]
            # Final membership read closes most presence races before a recorded line.
            state=await client.request('GET',room+'?chat=0')
            humans={u['id'] for u in state['members']}-bot_ids
            if reply.reason=='recorded' and humans:return
            if reply.reason!='recorded' and not humans:return
            if revision!=engine.revision:return
            result=await client.request('POST',room+'/chat',{'text':reply.text,'clientMessageId':'bot_'+uuid.uuid4().hex})
            memory.add(config['room'],Message(result['message']['id'],client.uid,reply.text))
            engine.sent()
            print(json.dumps({'event':'sent','speaker':reply.speaker,'reason':reply.reason},ensure_ascii=False),flush=True)
        async def work():
            nonlocal last_idle
            while not stop.is_set():
                try:message=await asyncio.wait_for(pending.get(),1)
                except TimeoutError:
                    now=time.monotonic()
                    if members==set() and now-last_human>=config['idle_seconds'] and now-last_idle>=config['idle_seconds']:
                        revision=engine.revision;reply=engine.idle(0)
                        if reply:
                            await publish(reply,revision);last_idle=now
                    continue
                revision=engine.revision
                await asyncio.sleep(config['reply_delay_seconds'])
                if revision!=engine.revision or not pending.empty():continue
                reply=await engine.respond(message)
                if reply:await publish(reply,revision)
        tasks=[asyncio.create_task(fn()) for fn in (presence,receive,work)]
        stopper=asyncio.create_task(stop.wait())
        try:
            done,_=await asyncio.wait([*tasks,stopper],return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                if task is not stopper:task.result()
        finally:
            stop.set()
            for task in [*tasks,stopper]:task.cancel()
            await asyncio.gather(*tasks,stopper,return_exceptions=True)
            for pid in list(joined):
                try:await clients[pid].request('POST',room+'/leave',{})
                except Exception:pass

def parse_message(row):
    uid=row.get('userId') or row.get('user',{}).get('id')
    if not uid or not row.get('id') or not isinstance(row.get('text'),str):return None
    return Message(str(row['id']),str(uid),row['text'][:600])

async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode',choices=['demo','live'],nargs='?',default='demo')
    parser.add_argument('--config',default=str(BASE/'config.example.json'))
    parser.add_argument('--scripts',default=str(BASE/'scripts.example.json'))
    parser.add_argument('--state',default=str(BASE/'state/memory.sqlite'))
    parser.add_argument('--base-url',default='http://127.0.0.1:56648')
    parser.add_argument('--enable-live',action='store_true');parser.add_argument('--use-gemini',action='store_true')
    args=parser.parse_args();config=load_config(args.config);scripts=read_scripts(args.scripts,config)
    memory=Memory(args.state,config['memory_days'])
    try:
        if args.mode=='demo':await demo(config,memory,scripts)
        else:
            with SingleInstance(args.state):await live(args,config,memory,scripts)
    finally:memory.close()
if __name__=='__main__':
    try:asyncio.run(main())
    except KeyboardInterrupt:pass
    except Exception as error:
        # Deliberately avoid logging request URLs, session values or response bodies.
        print('BOT_SIDECAR_STOPPED: '+type(error).__name__)
        raise SystemExit(1)
