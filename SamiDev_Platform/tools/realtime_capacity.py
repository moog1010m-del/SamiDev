"""Sustained authenticated local capacity probe, with a true all-connected barrier.

Requires isolated loopback Redis/PostgreSQL fixtures. It does not measure rendering,
login hashing, Nginx/TLS, WAN latency or pool physics. Active rooms send legal carrom
striker moves and authority heartbeats. Never report this as 10k full-game certification.
"""
import argparse
import asyncio
from collections import Counter
import json
from pathlib import Path
import sys
import time
import aiohttp
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tests'))
from realtime_cluster_fixture import Cluster, receive


def distribution(values):
    values = sorted(values)
    if not values: return {'count':0}
    return {'count':len(values),'p50':round(values[len(values)//2],2),
        'p95':round(values[min(len(values)-1,int(len(values)*.95))],2), 'max':round(values[-1],2)}


class Peer:
    def __init__(self, ws):
        self.ws = ws
        self.queue = asyncio.Queue(maxsize=128)
        self.turn = []
        self.sequence = [0,0]
        self.revision = -1
        self.error = None
        self.reader = asyncio.create_task(self.read())

    async def read(self):
        try:
            async for msg in self.ws:
                if msg.type != aiohttp.WSMsgType.TEXT: continue
                data = json.loads(msg.data)
                state = data.get('authority') if isinstance(data.get('authority'),dict) else data
                if 'sequence' in state:
                    # Two channels may interleave; don't rewind known sequence.
                    self.sequence = [max(a,b) for a,b in zip(self.sequence,state['sequence'])]
                revision=state.get('revision',state.get('authorityRevision',-1))
                if 'turn' in state and revision>=self.revision:
                    self.turn = state['turn'];self.revision=revision
                await self.queue.put(data)
        except Exception as exc: self.error = str(exc)

    async def get(self, kind, *, marker=None):
        async with asyncio.timeout(25):
            while True:
                data = await self.queue.get()
                if data['type']=='error': raise RuntimeError(data['code'])
                if data['type']=='desync': raise RuntimeError('DESYNC')
                if data['type']==kind and (marker is None or data.get('packet',{}).get('i')==marker): return data

    async def close(self):
        self.reader.cancel()
        await asyncio.gather(self.reader,return_exceptions=True)
        await self.ws.close()


async def run(args):
    cluster = Cluster(gateways=args.gateways, hosts=args.hosts)
    peers, rooms, setup_ms, ack_ms, ping_ms = [], [], [], [], []
    errors = Counter()
    report = {'requestedPlayers':args.players,'activeRoomsRequested':args.active_rooms,
        'gateways':args.gateways,'gamehosts':args.hosts,'durationSeconds':args.duration,
        'scope':'authenticated WebSockets; legal carrom striker moves; authority probes; no physics/TLS/rendering/login'}
    started = time.monotonic()
    stop_progress = asyncio.Event()
    async def progress():
        while not stop_progress.is_set():
            print(json.dumps({'progress':True,'seconds':round(time.monotonic()-started),
                'openClients':sum(not p.ws.closed for p in peers),'rooms':len(rooms),'errors':sum(errors.values())}),flush=True)
            try: await asyncio.wait_for(stop_progress.wait(),10)
            except TimeoutError: pass
    progress_task = asyncio.create_task(progress())
    try:
        await cluster.start()
        cookies = await cluster.seed(args.players)
        timeout = aiohttp.ClientTimeout(total=None,sock_connect=25,sock_read=None)
        async with aiohttp.ClientSession(timeout=timeout,connector=aiohttp.TCPConnector(limit=0)) as session:
            sem = asyncio.Semaphore(args.concurrency)
            async def setup(index):
                async with sem:
                    begin = time.monotonic()
                    try:
                        pair=[]
                        for offset, i in enumerate((index*2,index*2+1)):
                            p=Peer(await session.ws_connect(cluster.urls[(index+offset)%len(cluster.urls)]+'/ws',headers=cookies[i],max_msg_size=2**20))
                            peers.append(p);pair.append(p)
                        a,b=pair
                        await a.ws.send_json({'type':'create_room','settings':{'gameId':'carrom','players':0,'live':1}})
                        created=await a.get('created')
                        await b.ws.send_json({'type':'join_room','roomId':created['roomId']})
                        await b.get('joined')
                        await asyncio.gather(a.get('start'),b.get('start'))
                        rooms.append(pair)
                        setup_ms.append((time.monotonic()-begin)*1000)
                    except Exception as exc: errors['setup:'+type(exc).__name__+':'+str(exc)[:100]]+=1
            await asyncio.gather(*(setup(i) for i in range(args.players//2)))
            # All sockets stay open until after the common sustained measurement.
            peak=sum(not p.ws.closed for p in peers)
            report['clientsAtBarrier']=peak
            active=rooms[:args.active_rooms]
            async def begin(pair):
                async with sem:
                    a,b=pair
                    try:
                        for p in pair: await p.ws.send_json({'type':'runtime_ready'})
                        await asyncio.gather(a.get('begin_match'),b.get('begin_match'))
                        await a.ws.send_json({'type':'move','packet':{'n':0,'i':'capacity-start','m':{'m':0}}})
                        await asyncio.gather(a.get('move',marker='capacity-start'),b.get('move',marker='capacity-start'))
                        return pair
                    except Exception as exc: errors['begin:'+type(exc).__name__+':'+str(exc)[:100]]+=1
            active=[r for r in await asyncio.gather(*(begin(r) for r in active)) if r]
            report['activeRoomsAtBarrier']=len(active)
            report['rampSeconds']=round(time.monotonic()-started,2)
            end=time.monotonic()+args.duration
            async def exercise(pair,index):
                count=0
                await asyncio.sleep((index%20)*.05)
                while time.monotonic()<end:
                    a,b=pair
                    try:
                        for p in pair:
                            probe=time.monotonic()
                            await p.ws.send_json({'type':'ping','t':count,'authority':True})
                            await p.get('pong')
                            ping_ms.append((time.monotonic()-probe)*1000)
                        # Real rules-authorized movement on the current server turn.
                        actor=a if a.turn==[0] else b if a.turn==[1] else None
                        if actor:
                            seat=0 if actor is a else 1
                            sequence=actor.sequence[seat]
                            marker=f'capacity-{index}-{count}'
                            before=time.monotonic()
                            await actor.ws.send_json({'type':'move','packet':{'n':sequence,'i':marker,'m':{'m':6,'ps':.2+(count%5)*.1}}})
                            await asyncio.gather(*(p.get('move',marker=marker) for p in pair))
                            ack_ms.append((time.monotonic()-before)*1000)
                        count+=1
                    except Exception as exc:
                        errors['active:'+type(exc).__name__+':'+str(exc)[:100]]+=1
                        break
                    await asyncio.sleep(args.interval)
            async def idle_probe(p):
                while time.monotonic()<end:
                    try:
                        before=time.monotonic()
                        await p.ws.send_json({'type':'ping','t':0})
                        await p.get('pong')
                        ping_ms.append((time.monotonic()-before)*1000)
                    except Exception as exc:
                        errors['idle:'+type(exc).__name__]+=1
                        break
                    await asyncio.sleep(5)
            active_ids={id(p) for pair in active for p in pair}
            await asyncio.gather(*(exercise(pair,i) for i,pair in enumerate(active)),
                *(idle_probe(p) for p in peers if id(p) not in active_ids))
            report['clientsAfterHold']=sum(not p.ws.closed for p in peers)
            report['setupMs']=distribution(setup_ms)
            report['moveFanoutMs']=distribution(ack_ms)
            report['heartbeatMs']=distribution(ping_ms)
            report['errors']=dict(errors)
            report['ok']=not errors and peak==args.players and report['clientsAfterHold']==args.players and len(active)==args.active_rooms
            report['meetsLocalLatencyTarget']=report['ok'] and bool(ack_ms) and report['moveFanoutMs']['p95']<=250
            report['gamehostMetrics']=[]
            for url in cluster.hosts:
                async with session.get(url+'/v1/metrics',headers={'X-SamiDev-Service-Key':cluster.secret}) as response:
                    report['gamehostMetrics'].append(await response.json())
            report['gatewayMetrics']=[]
            for url in cluster.urls:
                async with session.get(url+'/metrics') as response:
                    report['gatewayMetrics'].append(await response.text())
            report['logs']=str(cluster.folder)
    finally:
        stop_progress.set();await progress_task
        await asyncio.gather(*(p.close() for p in peers),return_exceptions=True)
        await cluster.close()
    Path(args.output).write_text(json.dumps(report,ensure_ascii=False,indent=2))
    print(json.dumps(report,ensure_ascii=False),flush=True)
    return 0 if report.get('ok') else 2


if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--players',type=int,default=200)
    ap.add_argument('--active-rooms',type=int,default=None)
    ap.add_argument('--gateways',type=int,default=2)
    ap.add_argument('--hosts',type=int,default=2)
    ap.add_argument('--concurrency',type=int,default=32)
    ap.add_argument('--duration',type=float,default=20)
    ap.add_argument('--interval',type=float,default=2)
    ap.add_argument('--output',default='/tmp/samidev-capacity.json')
    args=ap.parse_args()
    if args.active_rooms is None: args.active_rooms=args.players//2
    if args.players<2 or args.players%2 or not 0<=args.active_rooms<=args.players//2: ap.error('even players; active rooms <= players/2')
    raise SystemExit(asyncio.run(run(args)))
