"""Small authenticated bridge for the optional external pool agent. No game-rule hooks."""
import json,time
from aiohttp import web
from social_platform import PREFIX,PlatformError

class BotPlayBridge:
    def __init__(self,manager,api):self.manager=manager;self.api=api;self.p=api.platform
    async def shorten(self,token):
        key=self.p.token_key(token)
        if self.p.r is None:
            entry=self.p.mem_sessions.get(key)
            if not entry:raise PlatformError('AUTH_REQUIRED','الجلسة منتهية',401)
            entry.expires_at=time.monotonic()+90
        else:
            transient=getattr(self.p.r,'transient',self.p.r)
            if not await transient.expire(self.p.k_session(key),90):raise PlatformError('AUTH_REQUIRED','الجلسة منتهية',401)
    async def issue(self,request):
        actor=await self.api._admin(request);uid=request.match_info['user_id']
        async with self.manager.control():
            user=await self.p.get_user(uid)
            if not user or user.get('managedBot')!='1' or user.get('botEnabled')!='1' or user.get('role')!='user' or user.get('banned')=='1':raise PlatformError('BOT_UNAVAILABLE','الحساب الآلي غير متاح',409)
            previous=user.get('botPlaySession')
            if previous and await self.p.resolve_session_key(previous):raise PlatformError('BOT_BUSY','الحساب يعمل مع عامل لعب آخر',409)
            token=await self.p.create_session(uid,metadata={'device':'pool-agent'})
            await self.shorten(token)
            await self.manager.write(uid,{'botPlaySession':self.p.token_key(token)})
        return web.json_response({'ok':True,'session':token,'expiresIn':90},headers={'Cache-Control':'no-store'})
    async def heartbeat(self,request):
        user=await self.api._user(request);token=request.cookies.get('samidev_session')
        if user.get('managedBot')!='1' or user.get('botEnabled')!='1' or user.get('role')!='user' or user.get('botPlaySession')!=self.p.token_key(token):raise PlatformError('BOT_UNAVAILABLE','توقف تشغيل الحساب الآلي',403)
        await self.p.community_rules.access(user['id'],user.get('botRoom','majlis'))
        await self.shorten(token)
        return web.json_response({'ok':True,'room':user.get('botRoom'),'skill':user.get('botSkill','medium')})
    async def status(self,request):
        await self.api._admin(request)
        body=await self.api._body(request)
        if set(body)-{'activeGames','online'} or type(body.get('online')) is not bool or type(body.get('activeGames')) is not int or not 0<=body['activeGames']<=100:raise PlatformError('BAD_BOT_WORKER','حالة العامل غير صالحة')
        value=json.dumps({'online':body['online'],'activeGames':body['activeGames'],'checkedAt':int(time.time()*1000)})
        if self.p.r is None:self.manager.play_worker=(value,time.monotonic()+35)
        else:await self.p.r.set(f'{PREFIX}:bot-play-worker',value,ex=35)
        return web.json_response({'ok':True})
    async def state(self):
        if self.p.r is None:
            entry=getattr(self.manager,'play_worker',None);value=entry[0] if entry and entry[1]>time.monotonic() else None
        else:value=await self.p.r.get(f'{PREFIX}:bot-play-worker')
        return json.loads(value) if value else {'online':False,'activeGames':0}
    def install(self,app):
        app.router.add_post('/api/admin/bots/{user_id}/play-session',self.issue)
        app.router.add_post('/api/admin/bots/play-worker',self.status)
        app.router.add_post('/api/bot-play/heartbeat',self.heartbeat)
