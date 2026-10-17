"""Server-owned admission and cooldown policy, shared by every gateway."""
import asyncio
import json
import time
from contextlib import asynccontextmanager

DEFAULTS = dict(maxMembers=200, maxTables=50, shortMatchSeconds=180, cooldownSeconds=60)
BOUNDS = dict(maxMembers=(1,200), maxTables=(1,200), shortMatchSeconds=(0,3600), cooldownSeconds=(0,3600))

class RoomPolicy:
    def __init__(self, platform):
        self.platform=platform
        self.memory={}
        self.lock=asyncio.Lock()

    def key(self, suffix):
        from social_platform import PREFIX
        return f'{PREFIX}:room-policy:{suffix}'

    @asynccontextmanager
    async def transaction(self):
        store=self.platform.r
        if store is None:
            async with self.lock: yield
        elif hasattr(store,'pool'):
            async with store.admission_lock(self.key('admission')): yield
        else:
            # Legacy Redis deployments; lock covers only bounded admission work.
            async with store.lock(self.key('admission'),timeout=60,blocking_timeout=3): yield

    async def clock(self):
        store=self.platform.r
        if store is None:return int(time.time()*1000)
        clock=await getattr(store,'transient',store).time()
        return int(clock[0])*1000+int(clock[1])//1000

    async def read(self, key):
        if key.startswith('cooldown:'):
            user=await self.platform.get_user(key.split(':',1)[1])
            return int((user or {}).get('matchCooldownUntil') or 0)
        value=await self.platform.r.get(self.key(key)) if self.platform.r is not None else self.memory.get(key)
        return json.loads(value) if value else None

    async def write(self,key,value):
        if key.startswith('cooldown:'):
            uid=key.split(':',1)[1];user=await self.platform.get_user(uid)
            if not user:return
            if self.platform.r is None:user['matchCooldownUntil']=str(value)
            else:await self.platform.r.hset(self.platform.k_user(uid),mapping={'matchCooldownUntil':str(value)})
            return
        encoded=json.dumps(value,separators=(',',':'))
        if self.platform.r is None:self.memory[key]=encoded
        else:await self.platform.r.set(self.key(key),encoded)

    async def settings(self,cid):
        return {**DEFAULTS,**(await self.read('settings:'+cid) or {})}

    async def configure(self,cid,body):
        from social_platform import PlatformError
        if not isinstance(body,dict) or set(body)!=set(DEFAULTS):raise PlatformError('BAD_ROOM_POLICY','أرسل جميع إعدادات الغرف')
        if any(type(body[k]) is not int or not lo<=body[k]<=hi for k,(lo,hi) in BOUNDS.items()):
            raise PlatformError('BAD_ROOM_POLICY','حدود الغرف غير صالحة؛ الأعضاء والطاولات ١–٢٠٠ والمدد ٠–٣٦٠٠ ثانية')
        async with self.transaction():await self.write('settings:'+cid,body)
        return body

    async def snapshots(self,store):
        from store import StoreError
        if getattr(store,'distributed',False):
            ids=await store.r.zrange(store.kroom_index(),0,-1)
            pipe=store.r.pipeline(transaction=False)
            for rid in ids:
                pipe.hmget(store.kroom(rid),'communityId','finished','waitingExpired','started','begun','waitingExpiresAt')
                pipe.hvals(store.kplayers(rid))
            rows=await pipe.execute();now=await self.clock();out=[]
            for i,rid in enumerate(ids):
                meta,players=rows[i*2:i*2+2]
                if all(value is None for value in meta) or meta[1]=='1' or meta[2]=='1':continue
                if meta[3]!='1' and meta[4]!='1' and int(meta[5] or 0)>0 and now>=int(meta[5]):continue
                out.append({'roomId':rid,'communityId':meta[0] or 'majlis','roster':[json.loads(player) for player in players]})
            return out
        ids=list(store.rooms)
        out=[]
        for rid in ids:
            try:room=await store.get_room_state(rid)
            except StoreError as error:
                if error.code=='ROOM_NOT_FOUND':continue
                raise
            if not room.get('finished') and not room.get('waitingExpired'):out.append(room)
        return out

    async def admit(self,store,uid,cid,kind,msg):
        from store import StoreError
        now=await self.clock()
        target=str(msg.get('roomId') or '')
        if kind=='join_invite':
            if getattr(store,'distributed',False):target=await store.r.get(store.kinvite(str(msg.get('inviteToken') or ''))) or ''
            else:target=(store.invites.get(str(msg.get('inviteToken') or '')) or ('',))[0]
        if target:
            room=await store.get_room_state(target);cid=room.get('communityId') or cid
        reconnect=False
        if kind=='join_room' and msg.get('token'):
            mapped=await store.r.get(store.ktoken(str(msg['token']))) if getattr(store,'distributed',False) else store.tokens.get(str(msg['token']))
            if isinstance(mapped,str):
                parts=mapped.rsplit(':',1);mapped=(parts[0],int(parts[1])) if len(parts)==2 and parts[1].isdigit() else None
            if mapped and mapped[0]==target:
                reconnect=any(p.get('accountId')==uid and p.get('seat')==mapped[1] for p in room.get('roster',[]))
        if reconnect:
            await self.platform._touch_community(uid,cid)
            return True
        config=await self.settings(cid)
        until=await self.read('cooldown:'+uid) or 0
        if until>now:raise StoreError('MATCH_COOLDOWN',f'انتظر {max(1,(until-now+999)//1000)} ثانية قبل الدخول إلى طاولة جديدة')
        rooms=await self.snapshots(store)
        if any(any(p.get('accountId')==uid for p in r.get('roster',[])) for r in rooms):
            raise StoreError('ACCOUNT_IN_MATCH','لديك طاولة مفتوحة؛ عد إليها أو أنهِ المباراة أولًا')
        members=await self.platform.community_members(cid,250)
        if uid not in {str(p['id']) for p in members} and len(members)>=config['maxMembers']:
            raise StoreError('COMMUNITY_FULL','المساحة ممتلئة؛ حاول لاحقًا')
        count=sum(r.get('communityId')==cid for r in rooms)
        if kind=='quick_play':
            await self.platform._touch_community(uid,cid)
            return count<config['maxTables']
        if kind=='create_room' and count>=config['maxTables']:
            raise StoreError('COMMUNITY_TABLE_LIMIT','وصلت المساحة إلى الحد الأقصى للطاولات')
        # Capacity was checked under this shared lock; reserve presence even for
        # direct WebSocket clients that never called the HTTP enter endpoint.
        await self.platform._touch_community(uid,cid)
        return True

    async def departed(self,room,uid):
        config=await self.settings(room.get('communityId') or 'majlis')
        now=await self.clock()
        await self.write('cooldown:'+uid,max(await self.read('cooldown:'+uid) or 0,now+config['cooldownSeconds']*1000))

    async def finish(self,store,rid):
        # Marking completion and publishing cooldown share the admission lock.
        async with self.transaction():
            room=await store.get_room_state(rid)
            if room.get('finished'):return
            config=await self.settings(room.get('communityId') or 'majlis')
            began=int(room.get('begunAt') or room.get('createdAt') or 0)
            if await self.clock()-began<config['shortMatchSeconds']*1000:
                for uid in (await store.account_ids_for_room(rid)).values():await self.departed(room,uid)
            await store.mark_finished(rid)
