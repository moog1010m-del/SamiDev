"""Account-scoped, expiring web-only 1v1 challenges; game rules stay in store."""
import asyncio, json, secrets, time
from contextlib import asynccontextmanager
from aiohttp import web
from social_platform import PREFIX, PlatformError
from store import sanitize_settings, game_capacity

class WebChallenges:
    def __init__(self, api):
        self.api=api; self.p=api.platform; self.mem={}; self.lock=asyncio.Lock()
    @asynccontextmanager
    async def transaction(self,keys):
        if self.p.r is None:
            async with self.lock:yield
        else:
            # Challenges coordinate transient state without opening a social-document
            # transaction: acceptance also reads safety and enters room admission.
            transient=getattr(self.p.r,'transient',self.p.r)
            async with transient.lock(self.key('coordination'),timeout=25,blocking_timeout=3):
                async with asyncio.timeout(20):yield
    def key(self,s):return f'{PREFIX}:web-challenge:{s}'
    async def get(self,k):
        if self.p.r is not None:
            v=await self.p.r.get(self.key(k)); return json.loads(v) if v else None
        v=self.mem.get(k);return v[1] if v and v[0]>time.time() else None
    async def put(self,k,v,ttl=180):
        if self.p.r is not None:await self.p.r.set(self.key(k),json.dumps(v),ex=ttl)
        else:self.mem[k]=(time.time()+ttl,v)
    async def presence(self,uid,client):await self.put('client:'+uid,client,90)
    async def allowed(self,rid,uid):
        pair=await self.get('room:'+rid)
        if pair and uid not in pair:raise PlatformError('INVITE_RESERVED','هذه الطاولة مخصصة لصاحب الدعوة والمدعو',403)
    async def request(self,request):
        user=await self.api._user(request);uid=str(user['id']); body=await self.api._body(request) if request.method=='POST' else {}
        if request.method=='GET':
            ident=await self.get('user:'+uid); row=await self.get('id:'+ident) if ident else None
            if row and row['expires']<time.time() and row['status']=='pending':row={**row,'status':'expired'}
            if row:
                row=dict(row);host_token=row.pop('hostToken',None)
                if uid==row['sender'] and host_token:row['token']=host_token
            return web.json_response({'ok':True,'challenge':row,'serverNow':time.time()})
        if request.headers.get('X-Plazr-Client')!='web':raise PlatformError('WEB_ONLY','الدعوات متاحة على الويب فقط')
        if not await self.p.allow_rate('web-challenge:'+uid,15,60):raise PlatformError('RATE_LIMIT','انتظر قليلًا قبل المحاولة مجددًا',429)
        action=body.get('action'); ident=str(body.get('id') or '')
        if action=='send':
            target=str(body.get('target') or '');gid=body.get('gameId'); cid=str(body.get('community') or '')
            if gid not in {'pool','carrom','crazy8','tablesoccer'}:raise PlatformError('BAD_GAME','اللعبة غير مدعومة')
            if target==uid or not await self.p.get_user(target):raise PlatformError('BAD_TARGET','المستخدم غير متاح')
            if await self.p.safety.pair_blocked(uid,target):raise PlatformError('BLOCKED','لا يمكن دعوة هذا المستخدم',403)
            if not await self.p.is_online(target):raise PlatformError('OFFLINE','المستخدم غير متصل الآن')
            client=await self.get('client:'+target)
            if client=='app':raise PlatformError('APP_USER','عذرًا، هذا المستخدم يستخدم التطبيق؛ الدعوات حاليًا بين مستخدمي الويب فقط')
            if client!='web':raise PlatformError('UNAVAILABLE','هذا المستخدم غير متاح لدعوات الويب حاليًا')
            members=await self.p.community_members(cid)
            if not {uid,target}.issubset({str(m['id']) for m in members}):raise PlatformError('COMMUNITY_MISMATCH','يجب أن تكونا في المساحة نفسها')
            async with self.transaction([self.key('user:'+v) for v in sorted([uid,target])]):
                for v in [uid,target]:
                    oldid=await self.get('user:'+v);old=await self.get('id:'+oldid) if oldid else None
                    if old and old['status']=='pending' and old['expires']>time.time():raise PlatformError('BUSY','توجد دعوة معلقة؛ انتظر أو ألغها أولًا',409)
                ident=secrets.token_urlsafe(20)
                row={'id':ident,'sender':uid,'target':target,'senderName':user.get('displayName') or user.get('username'),'gameId':gid,'community':cid,'status':'pending','expires':time.time()+30}
                await self.put('id:'+ident,row)
                for v in [uid,target]:await self.put('user:'+v,ident)
        else:
            async with self.transaction([self.key('id:'+ident)]):
                row=await self.get('id:'+ident)
                if not row or uid not in [row['sender'],row['target']]:raise PlatformError('NOT_FOUND','الدعوة غير موجودة',404)
                if row['status']!='pending' or row['expires']<time.time():raise PlatformError('EXPIRED','انتهت الدعوة أو تم الرد عليها',409)
                if action=='cancel' and uid==row['sender']:row['status']='cancelled'
                elif action=='reject' and uid==row['target']:row['status']='rejected'
                elif action=='accept' and uid==row['target']:
                    if await self.p.safety.pair_blocked(row['sender'],uid):raise PlatformError('BLOCKED','تعذر قبول الدعوة',403)
                    if await self.get('client:'+row['sender'])!='web':raise PlatformError('UNAVAILABLE','صاحب الدعوة غير متاح')
                    settings=sanitize_settings({'gameId':row['gameId'],'players':0,'seats':2,'live':1,'gameType':0})
                    if game_capacity(settings)!=2:raise PlatformError('BAD_CAPACITY','الدعوة فردية فقط')
                    async with self.p.room_policy.transaction():
                        for participant in [row['sender'],uid]:
                            await self.p.community_rules.access(participant,row['community'])
                            await self.p.room_policy.admit(self.api.room_store,participant,row['community'],'create_room',{})
                        room=await self.api.room_store.create_room(row['senderName'],settings,'web-challenge','challenge-'+ident,row['sender'],row['community'])
                    row.update(status='accepted',roomId=room['roomId'],hostToken=room['token'])
                    await self.put('room:'+room['roomId'],[row['sender'],uid],86400)
                else:raise PlatformError('FORBIDDEN','غير مسموح',403)
                await self.put('id:'+ident,row)
        return web.json_response({'ok':True})
