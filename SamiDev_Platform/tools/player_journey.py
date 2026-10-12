"""Authenticated 500-player journeys on isolated LOCAL services.

No seeded accounts, balances, wins, inventory or private GameHost reads. Native
Uno client replicas play naturally from seat-filtered packets. This is not a
browser/Flutter/WAN/10k certification. Cleanup touches only the fixture namespace.
"""
import argparse
import asyncio
from collections import Counter, defaultdict
import json
import os
from pathlib import Path
import random
import shutil
import sys
import time

import aiohttp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tests'))
from realtime_cluster_fixture import Cluster


def require(condition, message):
    if not condition: raise AssertionError(message)


def percentiles(values):
    values=sorted(values)
    if not values: return {'count':0}
    return {'count':len(values),'p50':round(values[len(values)//2],2),
        'p95':round(values[min(len(values)-1,int(len(values)*.95))],2),
        'p99':round(values[min(len(values)-1,int(len(values)*.99))],2),'max':round(values[-1],2)}


class Replicas:
    async def start(self):
        self.pending={};self.counter=0;self.lock=asyncio.Lock()
        self.rpc_ms=[];self.processing_ms=[]
        self.process=await asyncio.create_subprocess_exec(shutil.which('node'),
            str(ROOT/'tests/player_journey_replica.js'),stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.DEVNULL,
            env={'PATH':os.environ['PATH'],'LANG':'C.UTF-8'})
        self.reader=asyncio.create_task(self.read())

    async def read(self):
        try:
            while line:=await self.process.stdout.readline():
                message=json.loads(line);future=self.pending.pop(message['id'],None)
                if 'processingMs' in message:self.processing_ms.append(message['processingMs'])
                if future and not future.done():
                    if message['ok']:future.set_result(message['value'])
                    else:future.set_exception(RuntimeError('replica: '+message['error']))
        finally:
            for future in self.pending.values():
                if not future.done():future.set_exception(RuntimeError('replica worker stopped'))

    async def call(self, op, player, **kwargs):
        began=time.monotonic()
        self.counter+=1;request=self.counter
        future=asyncio.get_running_loop().create_future();self.pending[request]=future
        try:
            async with self.lock:
                self.process.stdin.write((json.dumps({'id':request,'op':op,'player':player,**kwargs})+'\n').encode())
                await self.process.stdin.drain()
            return await asyncio.wait_for(future,30)
        finally:
            self.pending.pop(request,None)
            self.rpc_ms.append((time.monotonic()-began)*1000)

    async def close(self):
        if self.process.returncode is None:
            self.process.stdin.close()
            try:await asyncio.wait_for(self.process.wait(),3)
            except TimeoutError:self.process.kill();await self.process.wait()
        await self.reader


class Actor:
    def __init__(self, index, run):
        self.index=index;self.run=run;self.url=run.cluster.urls[index%len(run.cluster.urls)]
        self.username=run.name+'_'+str(index);self.password='Journey-'+run.name+'-password-42'
        self.cookie=None;self.uid=None;self.condition=asyncio.Condition();self.ws=None;self.reader=None
        self.tasks=[];self.generation=0;self.state=None;self.assignment=None;self.begun=False
        self.acks={};self.chats={};self.rewards={};self.positive_rewards={};self.syncs=0
        self.fatal=None;self.wins=0;self.inventory=[];self.stars=0;self.spent=0
        self.community='majlis' if index//2%2==0 else 'square'

    def headers(self, cookie=None):
        values={**self.run.cluster.base_headers,'X-Real-IP':f'10.42.{self.index//256}.{self.index%256}'}
        token=self.cookie if cookie is None else cookie
        if token:values['Cookie']='samidev_session='+token
        return values

    async def http(self, method, path, body=None, statuses=(200,), cookie=None, busy_attempt=0):
        began=time.monotonic()
        async with self.run.session.request(method,self.url+path,json=body,headers=self.headers(cookie)) as response:
            data=await response.json()
            self.run.latencies[path.split('?')[0]].append((time.monotonic()-began)*1000)
            if response.status==503 and data.get('error')=='AUTH_BUSY' and path in {'/api/auth/register','/api/auth/login'}:
                self.run.counts['auth_busy_responses']+=1
                require(busy_attempt<3,'authentication busy after bounded retries')
                await response.release()
                await asyncio.sleep(.25*(2**busy_attempt)+self.index%7*.025)
                return await self.http(method,path,body,statuses,cookie,busy_attempt+1)
            require(response.status in statuses,f'{method} {path}: HTTP {response.status}, code={data.get("error")}')
            if response.cookies.get('samidev_session') and path in {'/api/auth/register','/api/auth/login'}:
                value=response.cookies['samidev_session']
                require(value['httponly'] and value['secure'] and value['samesite']=='Lax','session cookie flags')
                self.cookie=value.value
            return response.status,data

    async def account(self):
        async with self.run.account_sem:
            _,registered=await self.http('POST','/api/auth/register',{'username':self.username,'password':self.password,'displayName':f'Journey {self.index}'})
            self.uid=registered['user']['id']
            require(registered['user']['starsCount']==0,'new account has unexpected stars')
            for _ in range(2):
                old=self.cookie
                await self.http('POST','/api/auth/logout',{})
                await self.http('GET','/api/me',statuses=(401,),cookie=old)
                self.cookie=None
                _,logged=await self.http('POST','/api/auth/login',{'username':self.username,'password':self.password})
                require(logged['user']['id']==self.uid,'login changed identity')
            _,store=await self.http('GET','/api/store')
            require(store['coins']==0 and store['dailyReward']['rewardedMatches']==0,'new account starts with money/rewards')
            require(store['dailyReward']['maxMatches']==5,'scenario requires configured five-match daily reward cap')
            self.coins_per_match=store['dailyReward']['coinsPerMatch']
            await self.http('POST',f'/api/communities/{self.community}/enter',{})
            self.run.counts['registered_logged_out_logged_in']+=1

    async def connect(self, action, room=None, token=None, replacing=False):
        await self.http('POST',f'/api/communities/{self.community}/enter',{})
        previous=self.ws;old_reader=self.reader
        self.generation+=1;generation=self.generation
        self.assignment=None;self.begun=False;self.state=None;self.fatal=None;self.acks={};self.chats={}
        if replacing:
            current=self.run.cluster.urls.index(self.url)
            self.url=self.run.cluster.urls[(current+1)%len(self.run.cluster.urls)]
        _,ticket=await self.http('POST','/api/game-ticket',{'communityId':self.community})
        self.ws=await self.run.session.ws_connect(self.url+'/ws?ticket='+ticket['ticket'],headers=self.headers(),max_msg_size=2**20)
        self.reader=asyncio.create_task(self.read(self.ws,generation));self.tasks.append(self.reader)
        payload={'type':action}
        if action=='create_room':payload['settings']={'gameId':'crazy8','seats':0,'live':1,'special':0}
        else:payload.update(roomId=room,**({'token':token} if token else {}))
        await self.ws.send_json(payload)
        await self.wait(lambda:self.assignment is not None)
        if replacing:
            await self.wait(lambda:self.state is not None)
            await asyncio.wait_for(old_reader,5)
            require(previous.closed,'replaced socket remains live')

    async def read(self, ws, generation):
        try:
            async for frame in ws:
                if frame.type!=aiohttp.WSMsgType.TEXT:continue
                if generation!=self.generation:continue
                data=json.loads(frame.data);kind=data['type']
                if kind in {'created','joined'}:self.assignment=data
                elif kind=='start':
                    state=await self.run.replicas.call('init',self.index,seat=self.assignment['seat'],settings=data['settings'],snapshot=data['snapshot'])
                    if generation==self.generation:self.state=state;self.begun=bool(data.get('begun'))
                elif kind=='begin_match':self.begun=True
                elif kind in {'move','authority_alarm','resync_state'}:
                    state=await self.run.replicas.call('event',self.index,message=data)
                    if generation!=self.generation:continue
                    self.state=state
                    if kind=='move':self.acks[data['packet']['i']]=data
                    elif kind=='resync_state':self.syncs+=1
                elif kind=='sync_required':await ws.send_json({'type':'resync'})
                elif kind=='chat_message':self.chats[data['text']]=data
                elif kind=='match_reward':
                    room=data['roomId']
                    require(room not in self.rewards,'duplicate reward notification')
                    self.rewards[room]=data
                    if data['amount']>0:self.positive_rewards[room]=data
                elif kind in {'error','desync'}:
                    self.run.counts['unexpected_protocol_errors']+=1
                    self.fatal=RuntimeError('server: '+str(data.get('code') or kind))
                async with self.condition:self.condition.notify_all()
        except asyncio.CancelledError:raise
        except Exception as exc:
            if generation==self.generation:self.fatal=exc
        finally:
            async with self.condition:self.condition.notify_all()

    async def wait(self, predicate, timeout=30):
        async with asyncio.timeout(timeout):
            async with self.condition:
                while not predicate():
                    if self.fatal:raise self.fatal
                    if self.ws.closed:raise RuntimeError('socket closed before expected event')
                    await self.condition.wait()
                if self.fatal:raise self.fatal

    async def synchronize(self):
        before=self.syncs
        await self.ws.send_json({'type':'resync'})
        await self.wait(lambda:self.syncs>before)

    async def close_socket(self):
        if self.ws and not self.ws.closed:await self.ws.close()
        if self.reader:
            try:await asyncio.wait_for(self.reader,3)
            except TimeoutError:self.reader.cancel();await asyncio.gather(self.reader,return_exceptions=True)

    async def buy(self):
        async with self.run.account_sem:
            _,snapshot=await self.http('GET','/api/store')
            budget=self.coins_per_match*5
            require(snapshot['coins']==budget and snapshot['dailyReward']['rewardedMatches']==5,'full rewards/balance before purchase')
            items=sorted((item for item in snapshot['catalog'] if item['slot']=='name_badge' and 0<item['price']<=budget),key=lambda item:item['id'])
            item=items[self.index%len(items)]
            self.run.purchase_variants.add(item['id'])
            # Two overlapping clicks: one purchase, one already-owned response.
            results=await asyncio.gather(*(self.http('POST','/api/store/buy',{'itemId':item['id']},statuses=(200,400)) for _ in range(2)))
            require(sorted(status for status,_ in results)==[200,400],'duplicate purchase did not return one success')
            require(next(data for status,data in results if status==400)['error']=='STORE_ALREADY_OWNED','duplicate purchase error')
            self.spent=item['price'];self.inventory=[item['id']]
            await self.http('POST','/api/store/equip',{'itemId':item['id']})
            if self.index%2==0 and budget-self.spent>=50:
                star=next(i for i in snapshot['catalog'] if i['id']=='profile_star')
                if budget-self.spent>=star['price']:
                    await self.http('POST','/api/store/buy',{'itemId':'profile_star'})
                    self.spent+=star['price'];self.stars=1
            _,after=await self.http('GET','/api/store')
            require(after['coins']==budget-self.spent,'purchase balance mismatch')
            require(set(self.inventory)<=set(after['inventory']) and after['starsCount']==self.stars,'inventory/stars mismatch')
            require(after['equipped']['name_badge']==item['id'],'equipment mismatch')
            require(sum(row['type']=='daily_match_reward' for row in after['ledger'])==5,'missing/duplicate reward ledger')
            require(sum(row['type']=='store_purchase' for row in after['ledger'])==1+self.stars,'purchase ledger mismatch')
            self.run.counts['store_purchase_equip_duplicate_protected']+=1

    async def final(self, matches):
        async with self.run.account_sem:
            await self.http('POST','/api/auth/logout',{})
            self.cookie=None
            await self.http('POST','/api/auth/login',{'username':self.username,'password':self.password})
            _,store=await self.http('GET','/api/store')
            require(store['coins']==self.coins_per_match*5-self.spent,'balance lost after logout/login')
            require(store['starsCount']==self.stars and set(self.inventory)<=set(store['inventory']),'inventory lost after login')
            _,profile=await self.http('GET','/api/me')
            stat=next(row for row in profile['user']['gameStatistics'] if row['gameId']=='crazy8')
            require(stat['played']==matches and stat['wins']==self.wins,'match statistics mismatch')
            self.run.counts['persistent_return_verified']+=1


class Journey:
    def __init__(self,args):
        self.args=args;self.cluster=Cluster(gateways=args.gateways,hosts=args.hosts,browser_origins=args.browser_sample)
        self.replicas=Replicas();self.name='j'+os.urandom(5).hex();self.counts=Counter();self.latencies=defaultdict(list)
        self.account_sem=asyncio.Semaphore(args.account_concurrency);self.setup_sem=asyncio.Semaphore(args.room_concurrency)
        self.actors=[Actor(i,self) for i in range(args.players)]
        self.purchase_variants=set();self.phase='starting';self.failures=[];self.rounds=[];self.started=time.monotonic()
        self.output=Path(args.output);self.output.mkdir(parents=True,exist_ok=True)
        self.stop_progress=asyncio.Event();self.rng=random.Random(args.seed)

    async def progress(self):
        while not self.stop_progress.is_set():
            print(json.dumps({'phase':self.phase,'seconds':round(time.monotonic()-self.started),'counts':dict(self.counts)}),flush=True)
            try:await asyncio.wait_for(self.stop_progress.wait(),10)
            except TimeoutError:pass

    async def parallel(self, coroutines):
        results=await asyncio.gather(*coroutines,return_exceptions=True)
        for index,result in enumerate(results):
            if isinstance(result,BaseException):self.failures.append({'phase':self.phase,'index':index,'error':str(result) or type(result).__name__})
        require(not any(isinstance(r,BaseException) for r in results),'phase failed; see report.json')
        return results

    async def open_pair(self,index):
        a,b=self.actors[index*2:index*2+2]
        async with self.setup_sem:
            await a.connect('create_room')
            await b.connect('join_room',a.assignment['roomId'])
            await asyncio.gather(a.wait(lambda:a.state is not None),b.wait(lambda:b.state is not None))
            require(a.assignment['seat']==0 and b.assignment['seat']==1,'seat assignment')
            return a,b

    @staticmethod
    def consistent(a,b):
        for field in ('sequence','turn','gameOver','handCounts'):
            require(a.state[field]==b.state[field],f'client replicas disagree on {field}')

    async def play(self,index,pair,round_number):
        a,b=pair;room=a.assignment['roomId'];trace=[];moves=0
        started=time.monotonic();reconnected=False
        try:
            for actor in pair:
                text=f'جولة {round_number} — لاعب {actor.index} — {self.name}'
                await actor.ws.send_json({'type':'chat_send','text':text})
                await asyncio.gather(*(p.wait(lambda p=p,text=text:text in p.chats) for p in pair))
                for p in pair:require(p.chats[text]['seat']==actor.assignment['seat'],'chat author mismatch')
                self.counts['match_chat_delivered_to_both']+=1
            while not a.state['gameOver']:
                self.consistent(a,b)
                require(moves<self.args.max_moves,'match did not finish naturally within move budget')
                if round_number==2 and index%self.args.reconnect_every==0 and moves==5 and not reconnected:
                    before=a.assignment['connectionEpoch'];token=a.assignment['token']
                    await a.connect('join_room',room,token,replacing=True)
                    require(a.assignment['connectionEpoch']>before,'reconnect did not advance generation')
                    await b.synchronize()
                    self.consistent(a,b);reconnected=True;self.counts['mid_match_cross_gateway_reconnect']+=1
                seat=a.state['turn'][0];actor=pair[seat]
                chosen=await self.replicas.call('choose',actor.index)
                require(chosen is not None,'active player has no decision')
                marker=f'{self.name}-{round_number}-{index}-{moves}'
                packet={**chosen,'i':marker};before=time.monotonic()
                await actor.ws.send_json({'type':'move','packet':packet})
                await asyncio.gather(*(p.wait(lambda p=p:marker in p.acks) for p in pair))
                elapsed=(time.monotonic()-before)*1000;self.latencies['move_fanout'].append(elapsed)
                self.consistent(a,b)
                trace.append({'move':moves,'seat':seat,'packet':packet,'turn':a.state['turn'],
                    'sequence':a.state['sequence'],'ackMs':round(elapsed,2)})
                moves+=1;self.counts['legal_native_moves']+=1
                await asyncio.sleep(self.rng.uniform(self.args.think_min,self.args.think_max))
            require(b.state['gameOver'],'only one player saw game over')
            require(a.state['finishOrder']==b.state['finishOrder'],'winner differs across replicas')
            for seat in a.state['finishOrder'][0]:pair[seat].wins+=1
            await asyncio.gather(*(p.wait(lambda p=p:room in p.rewards) for p in pair))
            for actor in pair:
                notice=actor.rewards[room]
                require(notice['amount']==(actor.coins_per_match if round_number<=5 else 0),'wrong reward/cap')
                require(notice['rewardedMatches']==min(5,round_number),'wrong reward count')
            self.counts['naturally_completed_matches']+=1
            return {'roomId':room,'round':round_number,'moves':moves,'winner':a.state['finishOrder'][0],
                'seconds':round(time.monotonic()-started,2),'reconnected':reconnected}
        finally:
            (self.output/f'round-{round_number}-match-{index}.json').write_text(json.dumps(trace,ensure_ascii=False))
            await asyncio.gather(*(p.close_socket() for p in pair),return_exceptions=True)
            for actor in pair:await self.replicas.call('close',actor.index)

    async def rewards_verified(self,round_number):
        async def check(actor):
            async with self.account_sem:
                _,store=await actor.http('GET','/api/store')
                require(store['dailyReward']['rewardedMatches']==min(5,round_number),'API reward count disagrees with event')
                require(store['coins']==actor.coins_per_match*min(5,round_number)-actor.spent,'API wallet reward mismatch')
                require(len(actor.positive_rewards)==min(5,round_number),'missing/duplicate positive reward notice')
        await self.parallel([check(a) for a in self.actors])
        self.counts['wallets_checked_after_match']+=len(self.actors)

    async def community_chat(self):
        async def group(cid):
            members=[a for a in self.actors if a.community==cid]
            for actor in members:
                text=f'مرحبا من {actor.index} — {self.name}'
                _,sent=await actor.http('POST',f'/api/communities/{cid}/chat',{'text':text})
                viewer=next((a for a in members if a is not actor),actor)
                _,state=await viewer.http('GET',f'/api/communities/{cid}')
                matching=[m for m in state['messages'] if m['id']==sent['message']['id']]
                require(len(matching)==1 and matching[0]['text']==text and matching[0]['userId']==actor.uid,'community chat did not reach other account')
                self.counts['community_chat_verified']+=1
                await asyncio.sleep(.2)  # honor the production per-room rate limit
        await self.parallel([group(cid) for cid in {a.community for a in self.actors}])

    async def public_inventory(self):
        async def check(index):
            async with self.account_sem:
                actor=self.actors[index];viewer=self.actors[index^1]
                _,public=await viewer.http('GET','/api/public-profile/'+actor.uid)
                user=public['user']
                require(not {'passwordHash','password','sessionKey','coins','ledger'}&set(user),'public profile exposed private account data')
                require(user['starsCount']==actor.stars,'public star count differs')
                require(set(actor.inventory)<={item['id'] for item in user['showcaseItems']},'public inventory differs')
                require(user['nameBadge'] in actor.inventory,'public equipped badge differs')
                self.counts['public_inventory_verified']+=1
        await self.parallel([check(i) for i in range(len(self.actors))])

    async def browser_sample(self):
        actor=self.actors[0]
        _,before=await actor.http('GET','/api/store')
        require(before['coins']>=50 and before['starsCount']<5,'browser sample has no earned purchase budget')
        proc=await asyncio.create_subprocess_exec(shutil.which('node'),str(ROOT/'tests/player_journey_ui.mjs'),
            stdin=asyncio.subprocess.PIPE,stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        config={'base':actor.url,'cookie':actor.cookie,'ip':f'10.42.{actor.index//256}.{actor.index%256}',
            'coins':before['coins'],'output':str(self.output/'browser')}
        stdout,stderr=await proc.communicate(json.dumps(config).encode())
        require(proc.returncode==0,'browser sample failed: '+stderr.decode()[-1500:])
        result=json.loads(stdout)
        require(result['ok'],'browser sample failed')
        actor.spent+=result['price'];actor.stars+=result['starsDelta']
        self.counts['real_browser_purchase_verified']+=1

    async def execute(self):
        task=asyncio.create_task(self.progress());worker_started=False;report={}
        try:
            await self.cluster.start();await self.replicas.start();worker_started=True
            async with aiohttp.ClientSession(cookie_jar=aiohttp.DummyCookieJar(),
                timeout=aiohttp.ClientTimeout(total=45),connector=aiohttp.TCPConnector(limit=0)) as session:
                self.session=session
                self.phase='registration_login_logout'
                await self.parallel([a.account() for a in self.actors])
                self.phase='community_chat';await self.community_chat()
                for round_number in range(1,7):
                    self.phase=f'round_{round_number}_opening'
                    pairs=await self.parallel([self.open_pair(i) for i in range(self.args.players//2)])
                    peak=0
                    for url in self.cluster.urls:
                        async with session.get(url+'/metrics') as response:
                            text=await response.text()
                        peak+=int(next(line.split()[1] for line in text.splitlines() if line.startswith('samidev_connections ')))
                    require(peak==self.args.players,'all-connected barrier not reached')
                    self.phase=f'round_{round_number}_ready_barrier'
                    async def ready(pair):
                        for actor in pair:await actor.ws.send_json({'type':'runtime_ready'})
                        await asyncio.gather(*(p.wait(lambda p=p:p.begun) for p in pair))
                    await self.parallel([ready(pair) for pair in pairs])
                    require(all(actor.begun for actor in self.actors),'all-playing barrier not reached')
                    self.phase=f'round_{round_number}_playing'
                    matches=await self.parallel([self.play(i,pair,round_number) for i,pair in enumerate(pairs)])
                    self.rounds.append({'round':round_number,'simultaneousClients':peak,'activeRoomsAtBarrier':len(pairs),'matches':matches})
                    await self.rewards_verified(round_number)
                    if round_number==5:
                        self.phase='store_buy_equip';await self.parallel([a.buy() for a in self.actors])
                        if self.args.browser_sample:
                            self.phase='real_browser_purchase';await self.browser_sample()
                        await self.public_inventory()
                self.phase='final_logout_login_persistence'
                await self.parallel([a.final(6) for a in self.actors])
                for actor in self.actors:await actor.http('POST',f'/api/communities/{actor.community}/leave',{})
                self.gateway_metrics=[]
                for url in self.cluster.urls:
                    async with session.get(url+'/metrics') as response:self.gateway_metrics.append(await response.text())
        except Exception as exc:
            self.failures.append({'phase':self.phase,'error':str(exc) or type(exc).__name__})
        finally:
            report={'version':1,'requestedPlayers':self.args.players,'matchesPerRewardCycle':5,'extraCapMatch':True,
                'game':'crazy8','gateways':self.args.gateways,'gamehosts':self.args.hosts,'seed':self.args.seed,
                'seconds':round(time.monotonic()-self.started,2),'counts':dict(self.counts),
                'purchaseVariants':sorted(self.purchase_variants),'rounds':self.rounds,
                'latenciesMs':{key:percentiles(values) for key,values in self.latencies.items()},
                'failures':self.failures,'scope':'real HTTP accounts and native headless Uno client replicas; optional real Chromium purchase sample; TLS proxy headers simulated on loopback; no Flutter/WAN/physics/10k certification',
                'fixtureLogs':str(self.cluster.folder)}
            report['generatorReplicaRpcMs']=percentiles(self.replicas.rpc_ms) if worker_started else {'count':0}
            report['generatorReplicaProcessingMs']=percentiles(self.replicas.processing_ms) if worker_started else {'count':0}
            report['gatewayMetrics']=getattr(self,'gateway_metrics',[])
            report['browserSample']='passed' if self.counts['real_browser_purchase_verified'] else 'not-run'
            functional=not self.failures and self.counts['naturally_completed_matches']==self.args.players//2*6
            latency=self.latencies.get('move_fanout',[])
            responsive=bool(latency) and percentiles(latency)['p95']<=self.args.max_p95_ms
            report['functionalPass']=functional;report['latencyPass']=responsive
            report['verdict']='PASS_JOURNEY_PREPRODUCTION' if functional and responsive else 'NO_GO'
            report['productionCertified']=False
            report['remainingValidation']=['full mixed-game physics journeys','real TLS/proxy/WAN deployment','long soak and reconnect storms','real Flutter devices','known replay/failover gaps in SYNC_CAPACITY_REVIEW_AR.md']
            self.output.joinpath('report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
            self.stop_progress.set();await task
            await asyncio.gather(*(a.close_socket() for a in self.actors),return_exceptions=True)
            if worker_started:await self.replicas.close()
            await self.cluster.close()
        print(json.dumps({key:value for key,value in report.items() if key not in {'rounds','latenciesMs'}},ensure_ascii=False),flush=True)
        print('Report: '+str(self.output/'report.json'),flush=True)
        return 0 if report['verdict']=='PASS_JOURNEY_PREPRODUCTION' else 2


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--players',type=int,default=500)
    parser.add_argument('--gateways',type=int,default=3)
    parser.add_argument('--hosts',type=int,default=3)
    parser.add_argument('--account-concurrency',type=int,default=12)
    parser.add_argument('--room-concurrency',type=int,default=32)
    parser.add_argument('--think-min',type=float,default=.025)
    parser.add_argument('--think-max',type=float,default=.075)
    parser.add_argument('--max-moves',type=int,default=2000)
    parser.add_argument('--reconnect-every',type=int,default=25)
    parser.add_argument('--seed',type=int,default=20261012)
    parser.add_argument('--max-p95-ms',type=float,default=250)
    parser.add_argument('--output',default='/tmp/samidev-player-journey')
    parser.add_argument('--browser-sample',action='store_true',help='Require a real Chromium preview/cancel/confirm purchase using earned coins.')
    args=parser.parse_args()
    if args.players<2 or args.players%2 or args.reconnect_every<1:parser.error('players must be positive/even; reconnect-every positive')
    if min(args.gateways,args.hosts,args.account_concurrency,args.room_concurrency,args.max_moves)<1:parser.error('worker and concurrency counts must be positive')
    if not 0<=args.think_min<=args.think_max or args.max_p95_ms<=0:parser.error('invalid think time or latency threshold')
    raise SystemExit(asyncio.run(Journey(args).execute()))
