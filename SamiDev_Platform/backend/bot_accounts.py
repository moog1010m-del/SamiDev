"""Optional managed automated accounts. No gameplay engine or chat-model calls."""
import asyncio,json,logging,secrets
from contextlib import asynccontextmanager
from aiohttp import web

LOG=logging.getLogger('samidev.bot_accounts')
NAMES='نواف فهد خالد سعد تركي فيصل سلطان عبدالله محمد أحمد راشد ماجد بدر وليد طلال مشعل عبدالعزيز ياسر ريان زياد سلمان سعود بندر ناصر منصور عادل نايف عمار حمد راكان هيثم سامر مهند رامي لؤي إياد أسامة أنس عمر يوسف علي حسن حسين إبراهيم إسماعيل زيد سيف فواز هاني مراد'.split()

class BotAccounts:
    def __init__(self,platform):
        from social_platform import PREFIX
        self.p=platform;self.index=f'{PREFIX}:users:managed-bots';self.local_lock=asyncio.Lock();self.memory_ids=set();self.task=None
    @asynccontextmanager
    async def control(self):
        if self.p.r is None:
            async with self.local_lock:yield
        else:
            # Do not nest two locks on the one-connection SQL admission pool.
            transient=getattr(self.p.r,'transient',self.p.r)
            async with transient.lock(self.index+':control',timeout=120,blocking_timeout=10):yield
    @asynccontextmanager
    async def transaction(self,keys):
        if self.p.r is None:
            async with self.p.lock:yield
        elif hasattr(self.p.r,'transaction'):
            async with self.p.r.transaction(keys):yield
        else:yield
    async def ids(self):
        return sorted(await self.p.r.smembers(self.index) if self.p.r is not None else self.memory_ids)
    async def raw(self):
        rows=[]
        for uid in await self.ids():
            user=await self.p.get_user(uid)
            if user and user.get('managedBot')=='1':rows.append(user)
        return rows
    async def snapshot(self):
        from social_platform import COMMUNITIES,STORE_CATALOG,public_user
        worker=await self.play_bridge.state() if hasattr(self,'play_bridge') else {'online':False,'activeGames':0}
        rows=[]
        for raw in await self.raw():
            user=public_user(raw,online=await self.p.is_online(raw['id']))
            user.update(name=raw.get('botName',raw.get('username','')),room=raw.get('botRoom','majlis'),enabled=raw.get('botEnabled')=='1',skill=raw.get('botSkill','medium'),avatarUrl=('/api/avatar/'+raw['id']+'?v='+raw.get('botAvatarVersion','0')) if raw.get('avatarData') else '',presenceError=raw.get('botPresenceError',''),gameplayReady=worker['online'])
            rows.append(user)
        return dict(ok=True,bots=rows,communities=list(COMMUNITIES.values()),badges=[dict(id=k,name=v['name'],asset=v.get('asset','')) for k,v in STORE_CATALOG.items() if v.get('slot')=='name_badge' and not v.get('retired')],gameplayReady=worker['online'],playWorker=worker)
    async def create(self,room,name):
        from social_platform import now_ms
        uid=secrets.token_urlsafe(12);username='Bot_'+secrets.token_hex(6)
        user=dict(id=uid,username=username,usernameLower=username.lower(),displayName=username,passwordHash='',role='user',createdAt=str(now_ms()),wins='0',reputation='0',coins='0',banned='0',starsCount='0',nameBadge='',managedBot='1',botRoom=room,botEnabled='0',botSkill='medium',bio='حساب لاعب آلي',botName=name)
        keys=[self.index,self.p.k_user(uid),self.p.k_username(username.lower()),self.p.k_users()]
        async with self.transaction(keys):
            if self.p.r is not None:
                if not await self.p.r.set(keys[2],uid,nx=True):raise RuntimeError('Bot username collision')
                await self.p.r.hset(keys[1],mapping=user)
                await self.p.r.sadd(self.index,uid)
                if not hasattr(self.p.r,'pool'):await self.p.r.sadd(self.p.k_users(),uid)
            else:
                self.p.mem_users[uid]=user;self.p.mem_usernames[username.lower()]=uid;self.memory_ids.add(uid)
        return user
    async def write(self,uid,updates):
        async with self.transaction([self.p.k_user(uid)]):
            current=await self.p.get_user(uid)
            if not current or current.get('managedBot')!='1':
                from social_platform import PlatformError
                raise PlatformError('BOT_NOT_FOUND','الحساب الآلي غير موجود',404)
            if self.p.r is not None:await self.p.r.hset(self.p.k_user(uid),mapping=updates)
            else:current.update(updates)
    async def provision(self,body):
        from social_platform import COMMUNITIES,PlatformError
        target=body.get('targetPerRoom');count=body.get('addCount');room=body.get('room')
        if type(body.get('enabled',False)) is not bool:raise PlatformError('BAD_BOT_VALUE','حالة الاتصال غير صالحة')
        if target is not None:
            if type(target) is not int or not 1<=target<=100:raise PlatformError('BAD_BOT_COUNT','العدد لكل روم من 1 إلى 100')
            if count is not None or room is not None:raise PlatformError('BAD_BOT_COUNT','اختر تجهيز الرومات أو الإضافة لروم')
            rooms=list(COMMUNITIES)
        else:
            if room not in COMMUNITIES or type(count) is not int or not 1<=count<=50:raise PlatformError('BAD_BOT_COUNT','اختر رومًا وعددًا من 1 إلى 50')
            rooms=[room]
        created=0
        async with self.control():
            existing=await self.raw()
            if len(existing)>1000:raise PlatformError('BOT_LIMIT','وصلت إلى حد الحسابات الآلية')
            plans={cid:max(0,target-sum(u.get('botRoom')==cid for u in existing)) if target is not None else count for cid in rooms}
            if len(existing)+sum(plans.values())>1000:raise PlatformError('BOT_LIMIT','الحد الأقصى 1000 حساب آلي')
            for cid,amount in plans.items():
                offset=sum(u.get('botRoom')==cid for u in existing)
                for number in range(amount):
                    slot=offset+number
                    name=NAMES[slot%len(NAMES)]+((' '+str(slot//len(NAMES)+1)) if slot>=len(NAMES) else '')
                    user=await self.create(cid,name)
                    if body.get('enabled'):await self.write(user['id'],{'botEnabled':'1'})
                    created+=1
        # Presence renewal respects room limits; an account may remain offline if full.
        await self.sweep()
        return dict(ok=True,created=created,total=len(await self.ids()))
    async def update(self,uid,body):
        from social_platform import COMMUNITIES,STORE_CATALOG,PlatformError,normalize_avatar_data,sanitize_plain_text,now_ms
        allowed={'name','bio','avatarData','badgeId','room','enabled','skill'}
        if not body or set(body)-allowed:raise PlatformError('BAD_BOT_VALUE','حقول غير صالحة')
        updates={}
        if 'name' in body:
            updates['botName']=sanitize_plain_text(body['name'],40,empty_code='BAD_BOT_NAME',empty_message='الاسم مطلوب',too_long_code='BAD_BOT_NAME')
        if 'bio' in body:
            if not isinstance(body['bio'],str) or len(body['bio'])>160:raise PlatformError('BAD_BIO','البايو بحد أقصى 160 حرفًا')
            updates['bio']=sanitize_plain_text(body['bio'],160,empty_code='BAD_BIO',empty_message='بايو غير صالح',too_long_code='BAD_BIO') if body['bio'].strip() else ''
        if 'avatarData' in body:
            updates['avatarData']=normalize_avatar_data(body['avatarData']);updates['botAvatarVersion']=str(now_ms())
        if 'room' in body:
            if body['room'] not in COMMUNITIES:raise PlatformError('BAD_COMMUNITY','المساحة غير صالحة')
            updates['botRoom']=body['room']
        if 'enabled' in body:
            if type(body['enabled']) is not bool:raise PlatformError('BAD_BOT_VALUE','حالة الاتصال غير صالحة')
            updates['botEnabled']='1' if body['enabled'] else '0'
        if 'skill' in body:
            if body['skill'] not in ('beginner','medium','expert'):raise PlatformError('BAD_BOT_SKILL','مستوى المهارة غير صالح')
            updates['botSkill']=body['skill']
        badge=body.get('badgeId')
        if 'badgeId' in body:
            item=STORE_CATALOG.get(badge)
            if badge!='' and (not item or item.get('slot')!='name_badge' or item.get('retired')):raise PlatformError('BAD_BOT_BADGE','الشارة غير متاحة')
            updates['nameBadge']=badge
        async with self.control():
            await self.write(uid,updates)
            if badge:
                await self.p.grant_store_item(uid,badge,reason='bot-admin')
            user=await self.p.get_user(uid)
            if updates.get('botEnabled')=='0' or 'botRoom' in updates:
                await self.offline(uid)
        await self.sweep()
        return dict(ok=True)
    async def set_presence(self,body):
        from social_platform import COMMUNITIES,PlatformError
        if set(body)-{'enabled','room'} or type(body.get('enabled')) is not bool or (body.get('room') is not None and body['room'] not in COMMUNITIES):raise PlatformError('BAD_BOT_VALUE','اختر حالة اتصال ورومًا صحيحًا')
        count=0
        async with self.control():
            for user in await self.raw():
                if body.get('room') is not None and user.get('botRoom')!=body['room']:continue
                await self.write(user['id'],{'botEnabled':'1' if body['enabled'] else '0'});count+=1
        await self.sweep()
        return dict(ok=True,updated=count)
    async def offline(self,uid):
        await self.p.leave_community(uid)
        if self.p.r is not None:await self.p.r.delete(self.p.k_presence(uid))
        else:self.p.mem_presence.pop(uid,None)
    async def sweep(self):
        from social_platform import COMMUNITIES,PlatformError
        async with self.control():
            rows=await self.raw()
            for user in rows:
                if user.get('botEnabled')!='1' or user.get('banned')=='1':await self.offline(user['id'])
            for cid in COMMUNITIES:
                assigned=[u for u in rows if u.get('botEnabled')=='1' and u.get('banned')!='1' and u.get('botRoom')==cid]
                if not assigned:continue
                async with self.p.room_policy.transaction():
                    members=await self.p.community_members(cid,250);occupied={u['id'] for u in members}
                    limit=(await self.p.room_policy.settings(cid))['maxMembers']
                    for user in assigned:
                        uid=user['id'];error=''
                        try:
                            if uid not in occupied and len(occupied)>=limit:raise PlatformError('COMMUNITY_FULL','المساحة ممتلئة',409)
                            await self.p._touch_community(uid,cid);occupied.add(uid)
                        except PlatformError as exc:
                            error=exc.code;await self.offline(uid)
                        if user.get('botPresenceError','')!=error:await self.write(uid,{'botPresenceError':error})
    async def start(self,app):
        async def run():
            while True:
                try:await self.sweep()
                except asyncio.CancelledError:raise
                except Exception:LOG.exception('Managed bot presence renewal failed')
                await asyncio.sleep(20)
        self.task=asyncio.create_task(run(),name='managed-bot-presence')
    async def stop(self,app):
        if self.task:
            self.task.cancel();await asyncio.gather(self.task,return_exceptions=True);self.task=None

def install(app,api):
    manager=BotAccounts(api.platform)
    from bot_play_bridge import BotPlayBridge
    manager.play_bridge=BotPlayBridge(manager,api)
    manager.play_bridge.install(app)
    async def listing(request):
        await api._admin(request)
        return web.json_response(await manager.snapshot(),headers={'Cache-Control':'no-store'})
    async def provision(request):
        actor=await api._admin(request)
        if not await api.platform.allow_rate('bot-provision:'+actor['id'],6,60):
            from social_platform import PlatformError
            raise PlatformError('RATE_LIMIT','انتظر قليلًا قبل إضافة دفعة أخرى',429)
        result=await manager.provision(await api._body(request))
        LOG.info(json.dumps({'actor':actor['id'],'action':'provision','created':result['created']}))
        return web.json_response(result)
    async def update(request):
        actor=await api._admin(request);uid=request.match_info['user_id']
        result=await manager.update(uid,await api._body(request))
        LOG.info(json.dumps({'actor':actor['id'],'action':'update-bot','target':uid}))
        return web.json_response(result)
    async def bulk(request):
        actor=await api._admin(request)
        result=await manager.set_presence(await api._body(request))
        LOG.info(json.dumps({'actor':actor['id'],'action':'bulk-bot-presence','updated':result['updated']}))
        return web.json_response(result)
    app.router.add_get('/api/admin/bots',listing)
    app.router.add_patch('/api/admin/bots',bulk)
    app.router.add_post('/api/admin/bots',provision)
    app.router.add_patch('/api/admin/bots/{user_id}',update)
    app.on_cleanup.insert(0,manager.stop)
    return manager
