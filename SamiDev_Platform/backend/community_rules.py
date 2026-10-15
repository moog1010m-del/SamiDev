"""Explicit, server-enforced community scope; no client-provided authority."""
import json
import time
from contextlib import asynccontextmanager


class CommunityRules:
    def __init__(self, service):
        self.service = service
        self.audit = {}

    @staticmethod
    def data(user, field):
        try:
            value = json.loads(user.get(field) or '{}')
            return value if isinstance(value, dict) else {}
        except (ValueError, TypeError):
            return {}

    def can_moderate(self, user, cid):
        return user.get('role') == 'admin' or self.data(user, 'communityModeratorOf').get(cid) is True

    def check(self, user, cid, *, chat=False):
        from social_platform import PlatformError, normalize_community_id
        cid = normalize_community_id(cid)
        if not user: raise PlatformError('AUTH_REQUIRED', 'سجّل الدخول أولًا', 401)
        if str(user.get('banned') or '0')=='1': raise PlatformError('ACCOUNT_BANNED','هذا الحساب محظور',403)
        if user.get('role')=='admin': return user
        state = self.data(user,'communityRestrictions').get(cid) or {}
        clock = int(time.time()*1000)
        if state.get('banned') is True:
            raise PlatformError('COMMUNITY_BANNED', 'لا يمكنك دخول هذه المساحة', 403)
        if int(state.get('kickedUntil') or 0)>clock:
            raise PlatformError('COMMUNITY_KICKED', 'أُخرجت من المساحة مؤقتًا؛ حاول لاحقًا', 403)
        if chat and int(state.get('mutedUntil') or 0)>clock:
            raise PlatformError('COMMUNITY_MUTED', 'أنت مكتوم في هذه المساحة مؤقتًا', 403)
        return user

    async def access(self, uid, cid, *, chat=False):
        return self.check(await self.service.get_user(uid),cid,chat=chat)

    @asynccontextmanager
    async def transaction(self, keys):
        from social_platform import PlatformError
        store = self.service.r
        if store is not None:
            if not hasattr(store,'pool'):
                raise PlatformError('DURABLE_STORE_REQUIRED', 'إدارة المساحات تتطلب PostgreSQL', 503)
            async with store.transaction(keys): yield
        else:
            async with self.service.lock: yield

    async def moderate(self, actor_id, cid, target_id, action, duration=600):
        from social_platform import PlatformError, normalize_community_id
        cid = normalize_community_id(cid)
        if action not in {'kick','ban','unban','mute','unmute','grant_moderator','revoke_moderator'}:
            raise PlatformError('BAD_MODERATION_ACTION', 'إجراء الإدارة غير مدعوم')
        if type(duration) is not int or not 30<=duration<=86400:
            raise PlatformError('BAD_DURATION', 'المدة بين ٣٠ ثانية و٢٤ ساعة')
        if actor_id == target_id:
            raise PlatformError('CANNOT_MODERATE_SELF', 'لا تنفذ هذا الإجراء على حسابك')
        service = self.service
        from social_platform import PREFIX
        audit_key=f"{PREFIX}:moderation-audit:{cid}"
        async with self.transaction([service.k_user(actor_id),service.k_user(target_id),audit_key]):
            actor = await service.get_user(actor_id)
            target = await service.get_user(target_id)
            if not actor or str(actor.get('banned') or '0')=='1' or not self.can_moderate(actor,cid):
                raise PlatformError('COMMUNITY_MODERATOR_REQUIRED', 'لا تملك صلاحية إدارة هذه المساحة', 403)
            if not target: raise PlatformError('USER_NOT_FOUND', 'الحساب غير موجود', 404)
            granting = action in {'grant_moderator','revoke_moderator'}
            if granting and actor.get('role') != 'admin':
                raise PlatformError('ADMIN_REQUIRED', 'تعيين المشرفين وسحب صلاحياتهم للإدارة فقط', 403)
            if actor.get('role') != 'admin' and (target.get('role') in {'admin','moderator'} or self.can_moderate(target,cid)):
                raise PlatformError('PROTECTED_ACCOUNT', 'لا يمكنك إدارة حساب إداري آخر', 403)
            if target.get('role') == 'admin' and action not in {'grant_moderator','revoke_moderator'}:
                raise PlatformError('PROTECTED_ACCOUNT', 'لا يمكن تنفيذ هذا الإجراء على مدير المنصة', 403)
            field = 'communityModeratorOf' if granting else 'communityRestrictions'
            value = self.data(target,field)
            if granting:
                if action=='grant_moderator': value[cid]=True
                else: value.pop(cid,None)
            else:
                state = dict(value.get(cid) or {})
                clock = int(time.time()*1000)
                if action=='kick':state['kickedUntil']=clock+60000
                if action=='ban':state['banned']=True
                if action=='unban':state['banned']=False;state['kickedUntil']=0
                if action=='mute':state['mutedUntil']=clock+duration*1000
                if action=='unmute':state['mutedUntil']=0
                value[cid]=state
            encoded=json.dumps(value,separators=(',',':'))
            if service.r is None: target[field]=encoded
            else: await service.r.hset(service.k_user(target_id),mapping={field:encoded})
            record={'actorId':actor_id,'targetId':target_id,'communityId':cid,'action':action,'at':int(time.time()*1000),'duration':duration if action=='mute' else None}
            if service.r is None:
                rows=self.audit.setdefault(cid,[]);rows.append(record);del rows[:-1000]
            else:
                await service.r.rpush(audit_key,json.dumps(record,separators=(',',':')))
                await service.r.ltrim(audit_key,-1000,-1)
        if action in {'kick','ban'}:
            if service.r is not None: await service.r.srem(service.k_community_members(cid),target_id)
            elif (service.mem_active_community.get(target_id) or (None,))[0]==cid:
                service.mem_active_community.pop(target_id,None)
        return {'communityId':cid,'targetUserId':target_id,'action':action}
