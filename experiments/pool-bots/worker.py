"""Optional pool player process. All play goes through the normal authenticated /ws."""
import argparse,asyncio,json,os,random,signal,time,uuid
from pathlib import Path
from urllib.parse import urlsplit
import aiohttp
from planner import plan

def log(event,**fields):print(json.dumps({'event':event,**fields},ensure_ascii=False),flush=True)
class BridgeError(RuntimeError):pass
async def request(session,base,method,path,body=None):
    async with session.request(method,base+path,json=body,allow_redirects=False) as response:
        result=await response.json()
        if response.status!=200 or result.get('ok') is not True:raise BridgeError(result.get('error','HTTP_'+str(response.status)))
        return result

def eligible_room(room,join_after,now=None):
    settings=room.get('settings') or {}
    return settings.get('gameId')=='pool' and settings.get('gameType',0) in (0,7) and not room.get('started') and not room.get('finished') and room.get('occupied')==1 and room.get('capacity')==2 and (now if now is not None else time.time())*1000-room.get('createdAt',0)>=join_after*1000

class Player:
    def __init__(self,session,base,bot,room,scale=1,create=False,on_room=None):
        self.session=session;self.base=base;self.bot=bot;self.room=room;self.scale=scale;self.create=create;self.on_room=on_room
        self.ws=None;self.seat=None;self.view=None;self.begun=asyncio.Event();self.sync=asyncio.Event();self.pending={};self.done=False;self.settle=0;self.level=1;self.shots=0
    async def receive(self):
        try:
            async for raw in self.ws:
                if raw.type!=aiohttp.WSMsgType.TEXT:break
                data=json.loads(raw.data);kind=data.get('type')
                if kind in ('joined','created'):
                    self.room=data['roomId'];self.seat=data['seat']
                    if self.on_room:self.on_room(self.room)
                if kind in ('start','resync_state'):
                    view=(data.get('snapshot') or {}).get('pool')
                    if view:self.view=view
                    if kind=='start':await self.ws.send_json({'type':'runtime_ready'})
                    self.sync.set()
                if kind=='begin_match':self.begun.set()
                if kind=='move':
                    authority=data.get('authority') or {};reveal=data.get('reveal') or {}
                    view=authority.get('pool') or reveal.get('pool')
                    if view:self.view=view
                    packet=data.get('packet') or {};move=packet.get('m') or {}
                    if move.get('a')==1:self.settle=time.monotonic()+max(3,move.get('st',.5)*8)*self.scale
                    waiter=self.pending.pop(packet.get('i'),None)
                    if waiter and not waiter.done():waiter.set_result(data)
                if kind in ('desync','error'):
                    for waiter in self.pending.values():
                        if not waiter.done():waiter.set_exception(BridgeError(data.get('code') or data.get('reason') or kind))
                    self.pending.clear()
                    if kind=='error' and not self.begun.is_set():raise BridgeError(data.get('code','join_failed'))
                if kind=='left_room' or self.view and self.view.get('gameOver'):self.done=True
        finally:
            self.done=True
            for waiter in self.pending.values():
                if not waiter.done():waiter.set_exception(BridgeError('SOCKET_CLOSED'))
    async def resync(self):
        self.sync.clear();await self.ws.send_json({'type':'resync'});await asyncio.wait_for(self.sync.wait(),10)
    async def move(self,payload):
        if self.done or not self.view:raise BridgeError('MATCH_CLOSED')
        nonce='agent_'+uuid.uuid4().hex;future=asyncio.get_running_loop().create_future();self.pending[nonce]=future
        packet={'i':nonce,'n':self.view['sequence'][self.seat],'m':payload}
        try:
            await self.ws.send_json({'type':'move','packet':packet});return await asyncio.wait_for(future,12)
        finally:self.pending.pop(nonce,None)
    async def heartbeat(self):
        while not self.done:
            state=await request(self.session,self.base,'POST','/api/bot-play/heartbeat',{})
            if state['room']!=self.bot['room']:raise BridgeError('BOT_MOVED')
            self.bot['skill']=state['skill']
            await self.ws.send_json({'type':'ping','t':time.time()})
            await asyncio.sleep(15)
    async def play(self):
        await asyncio.wait_for(self.begun.wait(),90);await self.resync()
        while not self.done:
            if not self.view or self.view.get('gameOver'):break
            if self.view.get('turn')!=[self.seat] or time.monotonic()<self.settle:
                await asyncio.sleep(.10);continue
            # Same public synchronization handshake used by the browser.
            if self.view.get('awaitingReady'):
                await self.move({'__ready':1});continue
            await self.resync()
            if self.done or self.view.get('turn')!=[self.seat]:continue
            chosen=await asyncio.to_thread(plan,self.view,self.seat,self.bot['skill'],self.level)
            if not chosen:raise BridgeError('NO_LEGAL_TARGET')
            if chosen['placement'] is not None:await self.move({'a':2,'ps':chosen['placement']})
            log('thinking',bot=self.bot['id'],room=self.room,skill=self.bot['skill'],seconds=round(chosen['thinkSeconds'],2),target=chosen['target'])
            for step in chosen['steps']:
                await asyncio.sleep(step['delay']*self.scale)
                if self.done or self.view.get('turn')!=[self.seat]:break
                if step['move']['a']==1:
                    # Recheck admin disable/ban/room immediately before the actual shot.
                    state=await request(self.session,self.base,'POST','/api/bot-play/heartbeat',{})
                    if state['room']!=self.bot['room']:raise BridgeError('BOT_MOVED')
                await self.move(step['move'])
                if step['move']['a']==1:
                    self.shots+=1;log('shot',bot=self.bot['id'],room=self.room,skill=self.bot['skill'],count=self.shots)
            if self.view and self.view.get('gameOver'):self.done=True
    async def run(self):
        reader=None;heartbeat=None;actor=None
        try:
            me=await request(self.session,self.base,'GET','/api/me')
            self.level=next((s['level'] for s in me['user'].get('gameStatistics',[]) if s['gameId']=='pool'),1)
            ticket=await request(self.session,self.base,'POST','/api/game-ticket',{'communityId':self.bot['room']})
            async with self.session.ws_connect(self.base+'/ws?ticket='+ticket['ticket'],heartbeat=20,max_msg_size=2**20) as socket:
                self.ws=socket
                reader=asyncio.create_task(self.receive())
                await socket.send_json({'type':'create_room','settings':{'gameId':'pool','players':1,'gameType':0,'live':1},'name':self.bot['displayName'],'communityId':self.bot['room']} if self.create else {'type':'join_room','roomId':self.room,'name':self.bot['displayName']})
                heartbeat=asyncio.create_task(self.heartbeat());actor=asyncio.create_task(self.play())
                done,_=await asyncio.wait([reader,heartbeat,actor],return_when=asyncio.FIRST_COMPLETED)
                for task in done:task.result()
                if not socket.closed and self.room:
                    # Normal departure path; the authoritative server decides results.
                    await socket.send_json({'type':'leave_room'})
        finally:
            self.done=True
            for task in (reader,heartbeat,actor):
                if task:task.cancel()
            await asyncio.gather(*(t for t in (reader,heartbeat,actor) if t),return_exceptions=True)

class Worker:
    def __init__(self,base,token,max_games=4,wait=10,scale=1,bot_vs_bot=False):
        self.base=base;self.token=token;self.max_games=max_games;self.wait=wait;self.scale=scale;self.bot_vs_bot=bot_vs_bot
        self.jobs={};self.targets={};self.join_targets={};self.bots=[];self.communities=[];self.stop=asyncio.Event();self.last_roster=0
    async def launch(self,admin,bot,room=None,create=False):
        token=None
        try:
            result=await request(admin,self.base,'POST','/api/admin/bots/'+bot['id']+'/play-session',{})
            token=result['session']
            async with aiohttp.ClientSession(headers={'Origin':self.base},cookies={'samidev_session':token},timeout=aiohttp.ClientTimeout(total=15)) as session:
                player=Player(session,self.base,dict(bot),room,self.scale,create,lambda rid:self.targets.__setitem__(bot['id'],rid))
                await player.run()
                log('match_done',bot=bot['id'],room=player.room,shots=player.shots)
        except asyncio.CancelledError:raise
        except Exception as error:log('match_stopped',bot=bot['id'],reason=str(error) if isinstance(error,BridgeError) else type(error).__name__)
        finally:
            if token:
                try:
                    async with aiohttp.ClientSession(headers={'Origin':self.base},cookies={'samidev_session':token},timeout=aiohttp.ClientTimeout(total=3)) as session:
                        await request(session,self.base,'POST','/api/auth/logout',{})
                except Exception:pass
    async def run(self):
        async with aiohttp.ClientSession(headers={'Origin':self.base},cookies={'samidev_session':self.token},timeout=aiohttp.ClientTimeout(total=20)) as admin:
            try:
                while not self.stop.is_set():
                    self.jobs={uid:task for uid,task in self.jobs.items() if not task.done()}
                    self.targets={uid:rid for uid,rid in self.targets.items() if uid in self.jobs}
                    self.join_targets={uid:rid for uid,rid in self.join_targets.items() if uid in self.jobs}
                    if time.monotonic()-self.last_roster>20:
                        roster=await request(admin,self.base,'GET','/api/admin/bots')
                        self.bots=roster['bots'];self.communities=[c['id'] for c in roster['communities'] if c.get('enabled',True)];self.last_roster=time.monotonic()
                    rooms=(await request(admin,self.base,'GET','/api/lobby/rooms'))['rooms']
                    free=[b for b in self.bots if b['enabled'] and not b.get('banned') and b['id'] not in self.jobs]
                    for room in rooms:
                        if room['roomId'] in self.join_targets.values():continue
                        if room['roomId'] not in self.targets.values() and len(set(self.targets.values()))>=self.max_games:continue
                        if not eligible_room(room,self.wait):continue
                        matching=[b for b in free if b['room']==room['communityId']]
                        if not matching:continue
                        bot=random.choice(matching);free.remove(bot)
                        self.targets[bot['id']]=room['roomId'];self.join_targets[bot['id']]=room['roomId']
                        self.jobs[bot['id']]=asyncio.create_task(self.launch(admin,bot,room['roomId']))
                    if self.bot_vs_bot and len(set(self.targets.values()))<self.max_games:
                        occupied_rooms={r['communityId'] for r in rooms if r['settings'].get('gameId')=='pool'}
                        for cid in self.communities:
                            matching=[b for b in free if b['room']==cid]
                            if cid not in occupied_rooms and len(matching)>=2 and len(set(self.targets.values()))<self.max_games:
                                bot=matching[0];free.remove(bot);self.targets[bot['id']]='create:'+bot['id'];self.jobs[bot['id']]=asyncio.create_task(self.launch(admin,bot,create=True))
                    await request(admin,self.base,'POST','/api/admin/bots/play-worker',{'online':True,'activeGames':len(set(self.targets.values()))})
                    try:await asyncio.wait_for(self.stop.wait(),2)
                    except TimeoutError:pass
            finally:
                for task in self.jobs.values():task.cancel()
                await asyncio.gather(*self.jobs.values(),return_exceptions=True)
                try:await request(admin,self.base,'POST','/api/admin/bots/play-worker',{'online':False,'activeGames':0})
                except Exception:pass

def origin(value):
    url=urlsplit(value)
    if not url.hostname or url.username or url.password or url.query or url.fragment or url.path not in ('','/'):raise ValueError('Expected origin URL')
    if url.scheme!='https' and not(url.scheme=='http' and url.hostname in ('127.0.0.1','localhost','::1')):raise ValueError('HTTPS required')
    return value.rstrip('/')
async def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url',required=True);parser.add_argument('--enable-play',action='store_true');parser.add_argument('--max-games',type=int,default=4)
    parser.add_argument('--join-after',type=float,default=10);parser.add_argument('--bot-vs-bot',action='store_true');parser.add_argument('--test-time-scale',type=float,default=1)
    args=parser.parse_args();base=origin(args.base_url)
    if not args.enable_play:raise ValueError('Explicit --enable-play required')
    if not 1<=args.max_games<=16 or not 0<=args.join_after<=120 or not .01<=args.test_time_scale<=1:raise ValueError('Invalid limits')
    if args.test_time_scale!=1 and urlsplit(base).hostname not in ('127.0.0.1','localhost','::1'):raise ValueError('Test clock is localhost-only')
    token=os.environ.get('PLAZR_POOL_WORKER_ADMIN_SESSION','')
    if not token:raise ValueError('Set PLAZR_POOL_WORKER_ADMIN_SESSION securely')
    worker=Worker(base,token,args.max_games,args.join_after,args.test_time_scale,args.bot_vs_bot)
    for sig in (signal.SIGINT,signal.SIGTERM):
        try:asyncio.get_running_loop().add_signal_handler(sig,worker.stop.set)
        except NotImplementedError:pass
    await worker.run()
if __name__=='__main__':
    try:asyncio.run(main())
    except KeyboardInterrupt:pass
    except Exception as error:
        log('worker_stopped',reason=type(error).__name__);raise SystemExit(1)
