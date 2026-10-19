"""Durable community definitions; disabling preserves chat, accounts and matches."""
import json
import re
from contextlib import asynccontextmanager


class CommunityCatalog:
    def __init__(self,service):
        self.p=service;self.memory={}

    def key(self):
        from social_platform import PREFIX
        return PREFIX+':community-catalog:definitions'

    async def refresh(self):
        from social_platform import COMMUNITIES,DEFAULT_COMMUNITIES
        value=await self.p.r.get(self.key()) if self.p.r is not None else None
        saved=json.loads(value) if value else self.memory if self.p.r is None else {}
        rows={key:{**item,'enabled':True} for key,item in DEFAULT_COMMUNITIES.items()}
        rows.update(saved)
        COMMUNITIES.clear();COMMUNITIES.update(rows)
        return rows

    @asynccontextmanager
    async def transaction(self):
        from social_platform import PlatformError
        if self.p.r is None:
            async with self.p.lock:yield
        elif hasattr(self.p.r,'pool'):
            async with self.p.r.transaction([self.key()]):yield
        else:raise PlatformError('DURABLE_STORE_REQUIRED','إدارة المساحات تتطلب التخزين الدائم PostgreSQL',503)

    async def save(self,body,cid=None):
        from social_platform import PlatformError,sanitize_plain_text
        allowed={'name','description','mark','accent','countryCode','order','enabled'}
        if not isinstance(body,dict) or set(body)-(allowed if cid else allowed|{'id'}):raise PlatformError('BAD_COMMUNITY','حقول المساحة غير صالحة')
        creating=cid is None
        if creating:
            cid=body.get('id')
            if not isinstance(cid,str) or not re.fullmatch(r'[a-z][a-z0-9_-]{1,31}',cid):raise PlatformError('BAD_COMMUNITY_ID','معرّف المساحة 2–32 حرفًا إنجليزيًا صغيرًا أو رقمًا أو _ أو -')
            if 'name' not in body:raise PlatformError('BAD_COMMUNITY_NAME','اسم المساحة مطلوب')
        updates={}
        for key,limit in [('name',48),('description',180),('mark',8)]:
            if key in body:
                value=body[key]
                if not isinstance(value,str) or len(value)>limit:raise PlatformError('BAD_COMMUNITY','نص المساحة غير صالح')
                updates[key]=sanitize_plain_text(value,limit,empty_code='BAD_COMMUNITY',empty_message='اسم المساحة مطلوب',too_long_code='BAD_COMMUNITY') if value.strip() else ''
                if key=='name' and not updates[key]:raise PlatformError('BAD_COMMUNITY_NAME','اسم المساحة مطلوب')
        if 'accent' in body:
            if not isinstance(body['accent'],str) or not re.fullmatch(r'#[0-9a-fA-F]{6}',body['accent']):raise PlatformError('BAD_COMMUNITY_COLOR','اختر لونًا صحيحًا')
            updates['accent']=body['accent']
        if 'countryCode' in body:
            if body['countryCode'] not in ('','sa','kw','jo','iq'):raise PlatformError('BAD_COMMUNITY_FLAG','العلم غير مدعوم؛ يمكنك استخدام رمز المساحة')
            updates['countryCode']=body['countryCode']
        if 'enabled' in body:
            if type(body['enabled']) is not bool:raise PlatformError('BAD_COMMUNITY_STATE','حالة التفعيل غير صالحة')
            updates['enabled']=body['enabled']
        if 'order' in body:
            if type(body['order']) is not int or not 0<=body['order']<=999:raise PlatformError('BAD_COMMUNITY_ORDER','الترتيب بين 0 و999')
            updates['order']=body['order']
        async with self.transaction():
            rows=await self.refresh()
            if creating and cid in rows:raise PlatformError('COMMUNITY_EXISTS','معرّف المساحة مستخدم بالفعل',409)
            if not creating and cid not in rows:raise PlatformError('BAD_COMMUNITY','المساحة غير موجودة',404)
            if creating and len(rows)>=64:raise PlatformError('COMMUNITY_LIMIT','الحد الأقصى 64 مساحة',409)
            item={**rows.get(cid,{'id':cid,'description':'','mark':'🌐','accent':'#27927b','countryCode':'','order':len(rows)+1,'enabled':True}),**updates}
            if not item['enabled'] and not any(row.get('enabled',True) for key,row in rows.items() if key!=cid):raise PlatformError('LAST_COMMUNITY','أبقِ مساحة واحدة مفعلة على الأقل',409)
            rows[cid]=item
            if self.p.r is None:self.memory=rows
            else:await self.p.r.set(self.key(),json.dumps(rows,ensure_ascii=False,separators=(',',':')))
        await self.refresh()
        return item


def install(app,api):
    from aiohttp import web
    async def catalog(request):
        await api._admin(request)
        if request.method=='GET':
            rows=await api.platform.community_catalog(include_disabled=True)
            return web.json_response({'ok':True,'communities':rows},headers={'Cache-Control':'no-store'})
        item=await api.platform.community_definitions.save(await api._body(request),request.match_info.get('community_id'))
        return web.json_response({'ok':True,'community':item})
    app.router.add_get('/api/admin/communities',catalog)
    app.router.add_post('/api/admin/communities',catalog)
    app.router.add_patch('/api/admin/communities/{community_id}',catalog)
