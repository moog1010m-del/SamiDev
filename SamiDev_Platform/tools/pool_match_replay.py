"""Replay captured pool inputs with real accounts on isolated LOCAL services.

500 accounts means 250 simultaneous two-player rooms. Clients use authenticated
HTTP/WebSockets, fresh command IDs and current sequence numbers. Only the local
fixture service key installs the captured starting board before players join;
players cannot submit snapshots or outcomes. Subsequent results come exclusively
from the normal gateway and physics engine. Browser rendering is not simulated.
"""
import argparse
import asyncio
from collections import Counter, defaultdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import secrets
import sys
import time

import aiohttp

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tests'))
from realtime_cluster_fixture import Cluster


def require(value,message):
    if not value:raise AssertionError(message)


def load_recording(file):
    require(file.stat().st_size<=65*1024*1024,'recording exceeds size limit')
    with file.open(encoding='utf8') as stream:
        rows=[json.loads(line) for line in stream if line.strip()]
    require(2<=len(rows)<=250002,'recording is empty or exceeds event limit')
    header,end=rows[0],rows[-1]
    require(header.get('format')=='samidev.pool-recording' and header.get('version')==1,'unsupported recording format')
    require(header.get('type')=='header' and end.get('type')=='end' and end.get('complete') is True,'recording is truncated/incomplete')
    require(header.get('capacity')==2 and header.get('settings',{}).get('gameId')=='pool','requires a two-player pool recording')
    require(header['settings'].get('gameType') in {0,3,7},'recording is not a supported 1v1 mode')
    require(re.fullmatch(r'[a-f0-9]{64}',header.get('engineSha256','')) is not None,'missing engine fingerprint')
    snapshot=header.get('initialSnapshot',{});require(len(snapshot.get('d',{}).get('p',[])) in {10,16},'invalid initial board')
    require(len(snapshot.get('n',[]))==2 and snapshot.get('g')==0,'invalid starting sequence or finished game')
    previous=0
    for ordinal,event in enumerate(rows[1:-1],1):
        require(event.get('ordinal')==ordinal,'event missing or out of order')
        at=event.get('atMs');require(isinstance(at,(int,float)) and math.isfinite(at) and previous<=at<=21600000,'invalid event timing')
        previous=at
        require(event.get('type') in {'command','alarm','checkpoint','begin','rejected'},'unsupported event')
        if event['type']=='command':
            require(event.get('seat') in {0,1} and isinstance(event.get('input'),dict),'invalid command')
            require(event['input'].get('__ready')==1 or event['input'].get('a') in {0,1,2,3,4,8},'server-only/unknown input in recording')
            require(isinstance(event.get('state'),dict),'command missing authoritative result')
    require(end.get('events')==len(rows)-2,'recording event count mismatch')
    require(isinstance(end.get('atMs'),(int,float)) and math.isfinite(end['atMs']) and end['atMs']>=previous,'invalid end timing')
    require(any(e['type']=='command' for e in rows[1:-1]),'recording has no accepted player inputs')
    return header,rows[1:-1],end


def public_state(message):
    if message.get('type')=='resync_state':
        # A durable fallback does not carry the optional live authority fields.
        # Derive them from the native snapshot, just as the real client does.
        snapshot=message.get('snapshot',{})
        return {'turn':message.get('turn',snapshot.get('t')),
            'sequence':message.get('sequence',snapshot.get('n')),
            'gameOver':message.get('gameOver',snapshot.get('g')==1),
            **({'pool':snapshot['pool']} if 'pool' in snapshot else {})}
    state=message.get('authority',message)
    result={k:state[k] for k in ('turn','sequence','gameOver','pool') if k in state}
    return result


def percentiles(values):
    values=sorted(values)
    if not values:return {'count':0}
    def at(p):return round(values[min(len(values)-1,int(len(values)*p))],3)
    return {'count':len(values),'p50':at(.5),'p95':at(.95),'p99':at(.99),'max':round(values[-1],3)}


class Actor:
    def __init__(self,run,index):
        self.run=run;self.index=index;self.url=run.cluster.urls[index%len(run.cluster.urls)]
        self.username=run.name+'_'+str(index);self.password=secrets.token_urlsafe(24)
        self.cookie=None;self.ws=None;self.reader=None;self.assignment=None;self.start=None;self.begun=False
        self.condition=asyncio.Condition();self.moves={};self.alarms={};self.state=None;self.syncs=0;self.rewards={};self.fatal=None

    def headers(self):
        result={**self.run.cluster.base_headers,'X-Real-IP':f'10.45.{self.index//256}.{self.index%256}'}
        if self.cookie:result['Cookie']='samidev_session='+self.cookie
        return result

    async def http(self,method,path,body=None,attempt=0):
        began=time.perf_counter()
        async with self.run.session.request(method,self.url+path,json=body,headers=self.headers()) as response:
            data=await response.json();self.run.latencies[path].append((time.perf_counter()-began)*1000)
            if response.status==503 and data.get('error')=='AUTH_BUSY' and attempt<3:
                self.run.counts['authBusyRetries']+=1;await asyncio.sleep(.25*2**attempt);return await self.http(method,path,body,attempt+1)
            require(response.status==200,f'{method} {path}: HTTP {response.status} {data.get("error","")}')
            if path in {'/api/auth/register','/api/auth/login'}:
                cookie=response.cookies.get('samidev_session');require(cookie and cookie['secure'] and cookie['httponly'],'session cookie security flags')
                self.cookie=cookie.value
            return data

    async def account(self):
        async with self.run.account_sem:
            await self.http('POST','/api/auth/register',{'username':self.username,'password':self.password})
            await self.http('POST','/api/auth/logout',{});self.cookie=None
            await self.http('POST','/api/auth/login',{'username':self.username,'password':self.password})
            self.run.counts['registeredLoggedOutLoggedIn']+=1

    async def connect(self):
        self.ws=await self.run.session.ws_connect(self.url+'/ws',headers=self.headers(),max_msg_size=2**20)
        self.reader=asyncio.create_task(self.read())

    async def read(self):
        try:
            async for frame in self.ws:
                if frame.type!=aiohttp.WSMsgType.TEXT:continue
                msg=json.loads(frame.data);self.run.counts['receivedBytes']+=len(frame.data.encode())
                kind=msg['type']
                if kind in {'created','joined'}:self.assignment=msg
                elif kind=='start':self.start=msg
                elif kind=='begin_match':self.begun=True
                elif kind=='move':
                    self.moves[msg['packet']['i']]=msg;self.state=public_state(msg)
                elif kind=='authority_alarm':self.alarms[msg['alarmId']]=msg;self.state=public_state(msg)
                elif kind=='authority_state':self.state=public_state(msg)
                elif kind=='resync_state':
                    self.syncs+=1
                    self.state=public_state(msg)
                    if 'authorityEpoch' not in msg:self.run.counts['durableResyncFallbacks']+=1
                elif kind=='match_reward':
                    require(msg['roomId'] not in self.rewards,'duplicate match reward notification');self.rewards[msg['roomId']]=msg
                elif kind in {'error','desync'}:self.fatal=RuntimeError('protocol '+str(msg.get('code') or kind))
                elif kind=='sync_required':self.fatal=RuntimeError('event stream interrupted during exact replay')
                async with self.condition:self.condition.notify_all()
        except asyncio.CancelledError:raise
        except Exception as exc:self.fatal=exc
        finally:
            async with self.condition:self.condition.notify_all()

    async def wait(self,predicate,timeout=45):
        async with asyncio.timeout(timeout):
            async with self.condition:
                while not predicate():
                    if self.fatal:raise self.fatal
                    if self.ws.closed:raise RuntimeError('socket closed')
                    await self.condition.wait()
                if self.fatal:raise self.fatal

    async def synchronize(self):
        before=self.syncs;await self.ws.send_json({'type':'resync'});await self.wait(lambda:self.syncs>before)

    async def close(self):
        if self.ws:await self.ws.close()
        if self.reader:
            try:await asyncio.wait_for(self.reader,3)
            except TimeoutError:self.reader.cancel();await asyncio.gather(self.reader,return_exceptions=True)


class Replay:
    def __init__(self,args):
        self.args=args;self.header,self.events,self.end=load_recording(args.recording)
        self.cluster=Cluster(gateways=args.gateways,hosts=args.hosts)
        self.name='pr'+secrets.token_hex(4);self.actors=[Actor(self,i) for i in range(args.players)]
        self.account_sem=asyncio.Semaphore(args.account_concurrency);self.room_sem=asyncio.Semaphore(args.room_concurrency)
        self.latencies=defaultdict(list);self.counts=Counter();self.failures=[];self.scheduling_late=[];self.results=[];self.phase='initializing'
        self.active=0;self.peak_active=0
        self.output=args.output;self.output.mkdir(parents=True,exist_ok=True)

    async def internal(self,host,path,body):
        async with self.session.post(host+path,json=body,headers={'X-SamiDev-Service-Key':self.cluster.secret}) as response:
            data=await response.json();require(response.status==200,'local initial-board setup failed: '+str(data.get('code')));return data

    async def prepare_pair(self,index):
        async with self.room_sem:
            pair=self.actors[2*index:2*index+2]
            await asyncio.gather(*(a.connect() for a in pair))
            await pair[0].ws.send_json({'type':'create_room','settings':self.header['settings']})
            await pair[0].wait(lambda:pair[0].assignment is not None)
            created=pair[0].assignment;rid=created['roomId']
            host=max(self.cluster.hosts,key=lambda u:hashlib.sha256(f'{rid}|{u}'.encode()).digest())
            snapshot=json.loads(json.dumps(self.header['initialSnapshot']))
            if snapshot.get('p')==1:
                remaining=snapshot.get('_samidev_alarm',{}).get('remaining',snapshot.get('x',0))
                duration=snapshot.get('_samidev_alarm',{}).get('duration',snapshot.get('z',remaining))
                snapshot['_samidev_alarm']={'id':snapshot['a'],'paused':True,'remaining':remaining,'duration':duration,'expiresAt':int(time.time()*1000)+remaining}
            # The trusted fixture seeds the engine before the second seat joins.
            # The real gateway claims epoch 1 and persists this state normally.
            await self.internal(host,'/v1/room/init',{'roomId':rid,'settings':created['settings'],'capacity':2,'authorityEpoch':1,'connectionEpochs':[1,1],'snapshot':snapshot,'begun':False})
            await pair[1].ws.send_json({'type':'join_room','roomId':rid})
            await asyncio.gather(*(a.wait(lambda a=a:a.start is not None) for a in pair))
            for a in pair:
                require(a.start['snapshot']['d']['p']==snapshot['d']['p'],'starting positions changed')
                require(a.start['snapshot']['n']==snapshot['n'],'starting sequence changed')
            return pair,rid

    async def begin_pair(self,pair):
        await asyncio.gather(*(a.ws.send_json({'type':'runtime_ready'}) for a in pair))
        await asyncio.gather(*(a.wait(lambda a=a:a.begun) for a in pair))
        await asyncio.gather(*(a.synchronize() for a in pair))
        for a in pair:require(a.state==self.header['initialState'],'initial authoritative state mismatch')

    async def play(self,index,pair,rid,origin):
        began=time.monotonic();commands=alarms=0
        try:
            for event in self.events:
                if event['type'] in {'begin','rejected'}:continue
                deadline=origin+event['atMs']/1000
                await asyncio.sleep(max(0,deadline-time.monotonic()))
                self.scheduling_late.append(max(0,(time.monotonic()-deadline)*1000))
                expected=event['state']
                if event['type']=='command':
                    seat=event['seat'];actor=pair[seat]
                    require(actor.state['sequence'][seat]==event['sequenceBefore'],'sequence differs before recorded input')
                    packet_id=f'replay-{index}-{event["ordinal"]}'
                    packet={'i':packet_id,'n':actor.state['sequence'][seat],'m':event['input']}
                    started=time.perf_counter();await actor.ws.send_json({'type':'move','packet':packet})
                    await asyncio.gather(*(a.wait(lambda a=a:packet_id in a.moves) for a in pair))
                    self.latencies['moveFanout'].append((time.perf_counter()-started)*1000)
                    for a in pair:require(public_state(a.moves.pop(packet_id))==expected,f'authoritative result differs at event {event["ordinal"]}')
                    commands+=1
                    self.counts['matchedCommands']+=1
                elif event['type']=='alarm':
                    alarm_id=event['alarmId'];await asyncio.gather(*(a.wait(lambda a=a:alarm_id in a.alarms) for a in pair))
                    for a in pair:require(public_state(a.alarms.pop(alarm_id))==expected,f'auto-turn result differs at event {event["ordinal"]}')
                    alarms+=1
                    self.counts['matchedAlarms']+=1
                elif event['type']=='checkpoint':
                    await asyncio.gather(*(a.wait(lambda a=a:a.state==expected) for a in pair))
            await asyncio.sleep(max(0,origin+self.end['atMs']/1000-time.monotonic()))
            await asyncio.gather(*(a.synchronize() for a in pair))
            expected=self.end.get('state') or next((e['state'] for e in reversed(self.events) if 'state' in e),self.header['initialState'])
            for a in pair:
                diff=[k for k in set(expected)|set(a.state) if expected.get(k)!=a.state.get(k)]
                require(not diff,'final restored state differs: '+','.join(sorted(diff)))
            if expected.get('gameOver'):
                await asyncio.gather(*(a.wait(lambda a=a:rid in a.rewards) for a in pair))
                for a in pair:
                    store=await a.http('GET','/api/store')
                    require(sum(x['type']=='daily_match_reward' for x in store['ledger'])==1,'reward ledger missing/duplicated')
                self.counts['completedMatches']+=1
            return {'pair':index,'ok':True,'commands':commands,'alarms':alarms,'seconds':round(time.monotonic()-began,3)}
        except Exception as exc:
            failure={'pair':index,'ok':False,'error':str(exc) or type(exc).__name__,'commands':commands,'alarms':alarms}
            self.failures.append(failure);return failure

    async def start_and_play(self,index,pair,rid,barrier):
        offset=self.args.spread_seconds*index/max(1,self.args.players//2-1)
        await asyncio.sleep(max(0,barrier+offset-time.monotonic()))
        try:
            await self.begin_pair(pair)
        except Exception as exc:
            failure={'pair':index,'ok':False,'phase':'runtime_ready','error':str(exc) or type(exc).__name__}
            self.failures.append(failure);return failure
        self.active+=1;self.peak_active=max(self.peak_active,self.active)
        begin_ms=next((e['atMs'] for e in self.events if e['type']=='begin'),0)
        try:return await self.play(index,pair,rid,time.monotonic()-begin_ms/1000)
        finally:self.active-=1

    async def progress(self):
        while True:
            await asyncio.sleep(15)
            print(json.dumps({'phase':self.phase,'accountsReady':self.counts['registeredLoggedOutLoggedIn'],'matchedCommands':self.counts['matchedCommands'],'failures':len(self.failures)}),flush=True)

    async def execute(self):
        began=time.monotonic();progress=asyncio.create_task(self.progress());self.actual_hash=None;self.peak=0
        try:
            await self.cluster.start()
            async with aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar(),connector=aiohttp.TCPConnector(limit=0),timeout=aiohttp.ClientTimeout(total=45)) as session:
                self.session=session
                async with session.get(self.cluster.urls[0]+'/client-config.js') as response:
                    require(response.status==200,'public client configuration unavailable')
                    config_text=(await response.text()).strip();prefix='window.__SAMIDEV_CLIENT_CONFIG='
                    require(config_text.startswith(prefix),'unexpected client configuration format')
                    config=json.loads(config_text[len(prefix):].removesuffix(';'))
                    self.actual_hash=config['games']['pool']['mainJsSha256']
                require(self.args.allow_engine_change or self.actual_hash==self.header['engineSha256'],'recorded/current engine fingerprints differ; review then use --allow-engine-change')
                self.phase='register_logout_login';await asyncio.gather(*(a.account() for a in self.actors))
                self.phase='create_join_initial_board';pairs=await asyncio.gather(*(self.prepare_pair(i) for i in range(self.args.players//2)))
                for url in self.cluster.urls:
                    async with session.get(url+'/metrics') as response:text=await response.text()
                    self.peak+=int(next(line.split()[1] for line in text.splitlines() if line.startswith('samidev_connections ')))
                require(self.peak==self.args.players,'simultaneous connection barrier not reached')
                self.phase='ready_and_replay';barrier=time.monotonic()
                self.results=await asyncio.gather(*(self.start_and_play(i,pair,rid,barrier) for i,(pair,rid) in enumerate(pairs)))
                self.host_metrics=[]
                for host in self.cluster.hosts:
                    async with session.get(host+'/v1/metrics',headers={'X-SamiDev-Service-Key':self.cluster.secret}) as response:self.host_metrics.append(await response.json())
        except Exception as exc:self.failures.append({'phase':self.phase,'error':str(exc) or type(exc).__name__})
        finally:
            progress.cancel();await asyncio.gather(progress,return_exceptions=True)
            await asyncio.gather(*(a.close() for a in self.actors),return_exceptions=True)
            await self.cluster.close()
        lat=percentiles(self.latencies['moveFanout']);late=percentiles(self.scheduling_late)
        functional=not self.failures and len(self.results)==self.args.players//2
        responsive=lat.get('p95',float('inf'))<=self.args.max_p95_ms and late.get('p95',float('inf'))<=self.args.max_lateness_ms
        report={'version':1,'requestedPlayers':self.args.players,'simultaneousConnections':self.peak,'matches':self.args.players//2,
            'maxActiveMatches':self.peak_active,
            'gateways':self.args.gateways,'hosts':self.args.hosts,'seconds':round(time.monotonic()-began,3),'counts':dict(self.counts),
            'recordedEngineSha256':self.header['engineSha256'],'currentEngineSha256':self.actual_hash,'sourceEndedNormally':self.end['reason']=='game_over',
            'sourceRejectedEvents':sum(e['type']=='rejected' for e in self.events),'spreadSeconds':self.args.spread_seconds,
            'moveFanoutMs':lat,'schedulingLatenessMs':late,'latenciesMs':{k:percentiles(v) for k,v in self.latencies.items()},
            'thresholds':{'moveP95Ms':self.args.max_p95_ms,'latenessP95Ms':self.args.max_lateness_ms},
            'functionalPass':functional,'latencyPass':responsive,'verdict':'PASS_RECORDED_SCENARIO' if functional and responsive else 'NO_GO',
            'failures':self.failures,'pairs':self.results,'hostMetrics':getattr(self,'host_metrics',[]),'fixtureLogs':str(self.cluster.folder),
            'productionCertified':False,'scope':'authenticated local accounts and replay of accepted pool inputs; native physics/results and both client responses compared; starting board installed only by private fixture; closed-loop timing with lateness reported; no browser/Flutter/WAN/transport disconnect recreation'}
        self.output.joinpath('report.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:report[k] for k in ['verdict','functionalPass','latencyPass','simultaneousConnections','matches','moveFanoutMs','schedulingLatenessMs','failures']}),flush=True)
        print('Report: '+str(self.output/'report.json'),flush=True)
        return 0 if functional and responsive else 2


def cli():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('recording',type=Path);parser.add_argument('--players',type=int,default=500)
    parser.add_argument('--gateways',type=int,default=3);parser.add_argument('--hosts',type=int,default=3)
    parser.add_argument('--account-concurrency',type=int,default=12);parser.add_argument('--room-concurrency',type=int,default=32)
    parser.add_argument('--spread-seconds',type=float,default=0,help='0 = synchronized burst; >0 = staggered human scenario starts')
    parser.add_argument('--max-p95-ms',type=float,default=250);parser.add_argument('--max-lateness-ms',type=float,default=1000)
    parser.add_argument('--allow-engine-change',action='store_true');parser.add_argument('--output',type=Path,default=Path('/tmp/samidev-pool-replay'))
    args=parser.parse_args()
    if args.players<2 or args.players>10000 or args.players%2:parser.error('players must be even, 2..10000')
    if min(args.gateways,args.hosts,args.account_concurrency,args.room_concurrency)<1:parser.error('positive worker counts required')
    if not all(math.isfinite(n) and n>=0 for n in [args.spread_seconds,args.max_p95_ms,args.max_lateness_ms]):parser.error('timing values must be finite and nonnegative')
    raise SystemExit(asyncio.run(Replay(args).execute()))


if __name__=='__main__':cli()
