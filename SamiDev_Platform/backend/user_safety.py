"""Account-owned blocking, enforced on chat delivery and friendship operations."""
from social_platform import PREFIX, PlatformError, COMMUNITIES

class UserSafety:
    MAX_BLOCKS=500
    def __init__(self,platform):self.p=platform;self.memory={}
    def key(self,uid):return f'{PREFIX}:user-blocks:{uid}'
    async def blocked(self,uid):
        if not uid:return set()
        return set(await self.p.r.smembers(self.key(uid))) if self.p.r is not None else set(self.memory.get(uid,set()))
    async def pair_blocked(self,a,b):return b in await self.blocked(a) or a in await self.blocked(b)
    async def update(self,uid,target,enabled):
        if uid==target:raise PlatformError('SELF_BLOCK','لا يمكنك حظر نفسك')
        if not await self.p.get_user(target):raise PlatformError('USER_NOT_FOUND','المستخدم غير موجود',404)
        keys=[self.key(uid),self.p.k_user(uid),self.p.k_user(target),self.p.k_friends(uid),self.p.k_friends(target),self.p.k_requests(uid),self.p.k_requests(target)]
        async with self.p.accounts.transaction(keys):
            if not await self.p.get_user(uid):raise PlatformError('AUTH_REQUIRED','الحساب غير متاح',401)
            current=await self.blocked(uid)
            if enabled and target not in current and len(current)>=self.MAX_BLOCKS:raise PlatformError('BLOCK_LIMIT','وصلت إلى حد قائمة الحظر',409)
            if self.p.r is None:
                rows=self.memory.setdefault(uid,set())
                if enabled:rows.add(target)
                else:rows.discard(target)
            elif enabled:await self.p.r.sadd(self.key(uid),target)
            else:await self.p.r.srem(self.key(uid),target)
            if enabled:
                if self.p.r is None:
                    for owner,other in ((uid,target),(target,uid)):
                        self.p.mem_friends.setdefault(owner,set()).discard(other)
                        self.p.mem_requests.setdefault(owner,set()).discard(other)
                else:
                    for owner,other in ((uid,target),(target,uid)):
                        await self.p.r.srem(self.p.k_friends(owner),other)
                        await self.p.r.srem(self.p.k_requests(owner),other)
        # History and live subscriptions refresh without changing game state.
        for cid in COMMUNITIES:await self.p.live.publish(cid,{'type':'resync','targetUserId':uid})
        return {'blocked':enabled}
    async def community_event(self,uid,event):
        blocked=await self.blocked(uid)
        if not blocked:return event
        if event.get('type')=='message' and (event.get('message') or {}).get('userId') in blocked:return None
        if 'messages' in event:return {**event,'messages':[m for m in event['messages'] if m.get('userId') not in blocked]}
        return event
    async def game_event(self,uid,room_id,event,store):
        blocked=await self.blocked(uid)
        if not blocked:return event
        messages=event.get('messages',[]) if event.get('type')=='chat_history' else [event]
        seats=set()
        if any(not message.get('userId') for message in messages):
            state=await store.get_room_state(room_id)
            seats={p['seat'] for p in state.get('roster',[]) if p and p.get('accountId') in blocked}
        def hidden(message):return message.get('userId') in blocked if message.get('userId') else message.get('seat') in seats
        if event.get('type')=='chat_message' and hidden(event):return None
        if event.get('type')=='chat_history':return {**event,'messages':[m for m in event['messages'] if not hidden(m)]}

        return event

async def block_user(api,request):
    from aiohttp import web
    user=await api._user(request);target=request.match_info['user_id']
    if not await api.platform.allow_rate(f"user-block:{user['id']}",30,60):raise PlatformError('RATE_LIMIT','محاولات كثيرة؛ حاول لاحقًا',429)
    body=await api._body(request)
    if type(body.get('blocked')) is not bool or set(body)!={'blocked'}:raise PlatformError('BAD_BLOCK','حالة الحظر غير صالحة')
    return web.json_response({'ok':True,**await api.platform.safety.update(user['id'],target,body['blocked'])})
