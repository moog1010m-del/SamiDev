"""Private account/session management. Device descriptions are never authority."""
import json
import math
import os
import re
import secrets
import time
from contextlib import asynccontextmanager


def device_metadata(request, *, trust_proxy=False):
    ua = request.headers.get('User-Agent', '')[:512]
    platform = next((label for needle, label in (
        ('iPad', 'iPad'), ('iPhone', 'iPhone'), ('Android', 'Android'),
        ('Windows', 'Windows'), ('Macintosh', 'Mac'), ('Linux', 'Linux')) if needle in ua), 'جهاز غير معروف')
    browser = next((label for needle, label in (
        ('SamiDev/', 'تطبيق SamiDev'), ('Edg/', 'Edge'), ('Firefox/', 'Firefox'),
        ('CriOS/', 'Chrome'), ('Chrome/', 'Chrome'), ('Safari/', 'Safari')) if needle in ua), 'متصفح')
    # Country only, from an explicitly configured ingress that OVERWRITES this
    # header. Never trust arbitrary client location/IP headers or request GPS.
    country = request.headers.get('X-SamiDev-Country', '').upper()
    if not (trust_proxy and os.getenv('SAMIDEV_TRUST_GEO_HEADERS') == '1'
            and re.fullmatch('[A-Z]{2}', country) and country not in {'XX', 'T1'}):
        country = ''
    return {'device': platform, 'client': browser, 'country': country}


class AccountSecurity:
    def __init__(self, service):
        self.s = service
        self.memory = {}
        self.seen = {}

    @asynccontextmanager
    async def transaction(self, uid):
        s = self.s
        if s.r is not None and not hasattr(s.r, 'pool'):
            async with s.r.lock(self.key(uid) + ':lock', timeout=30, blocking_timeout=5):
                yield
        else:
            async with s.accounts.transaction([s.k_user(uid), self.key(uid)]):
                yield

    def key(self, uid):
        from social_platform import PREFIX
        return f'{PREFIX}:account-sessions:{uid}'

    def seen_key(self, key):
        from social_platform import PREFIX
        return f'{PREFIX}:session-seen:{key}'

    async def records(self, uid):
        if self.s.r is None:
            return dict(self.memory.get(uid, {}))
        raw = await self.s.r.get(self.key(uid))
        return json.loads(raw) if raw else {}

    async def save(self, uid, rows):
        if self.s.r is None:
            self.memory[uid] = rows
        else:
            if rows:
                from social_platform import now_ms
                ttl = max(1, math.ceil((max(v['expiresAt'] for v in rows.values()) - now_ms()) / 1000))
                await self.s.r.set(self.key(uid), json.dumps(rows), ex=ttl)
            else:
                await self.s.r.delete(self.key(uid))

    async def raw(self, key):
        if self.s.r is not None:
            return await self.s.r.get(self.s.k_session(key))
        entry = self.s.mem_sessions.get(key)
        return entry.value if entry and entry.expires_at > time.monotonic() else None

    async def drop(self, key):
        if self.s.r is None:
            self.s.mem_sessions.pop(key, None)
            self.seen.pop(key, None)
        else:
            await self.s.r.delete(self.s.k_session(key), self.seen_key(key))

    async def touch(self, key):
        from social_platform import now_ms, SESSION_TTL
        stamp = now_ms()
        if self.s.r is None:
            self.seen[key] = stamp
        else:
            if self.seen.get(key, 0) > stamp - 60_000:
                return
            if len(self.seen) > 10000:
                self.seen = {k: v for k, v in self.seen.items() if v > stamp - 60_000}
            # A separate key cannot resurrect a revoked authentication session.
            await self.s.r.set(self.seen_key(key), str(stamp), ex=SESSION_TTL)
            self.seen[key] = stamp

    async def create(self, uid, *, firebase_auth_time=None, metadata=None):
        from social_platform import PlatformError, MemoryEntry, SESSION_TTL, now_ms
        s = self.s
        async with self.transaction(uid):
            user = await s.get_user(uid)
            if not user or user.get('deleting') == '1' or str(user.get('banned') or '0') == '1':
                raise PlatformError('AUTH_REQUIRED', 'يجب تسجيل الدخول', 401)
            token, device_id = secrets.token_urlsafe(32), secrets.token_urlsafe(18)
            key, stamp = s.token_key(token), now_ms()
            data = {'uid': uid, 'version': str(user.get('authVersion') or '0'),
                    'deviceId': device_id, 'createdAt': stamp, 'expiresAt': stamp + SESSION_TTL * 1000}
            if firebase_auth_time is not None:
                data['firebaseAuthTime'] = firebase_auth_time
            if user.get('firebaseUid'):
                data['firebaseUid'] = user['firebaseUid']
                data['firebaseProject'] = user.get('firebaseProject', '')
            rows = await self.records(uid)
            rows = {k: v for k, v in rows.items() if v['expiresAt'] > stamp and v['version'] == data['version']}
            rows = {k: v for k, v in rows.items() if await self.raw(v['sessionHash'])}
            if len(rows) >= 40:
                raise PlatformError('SESSION_LIMIT', 'بلغت الحد الأقصى للأجهزة. سجّل الخروج من جهاز ثم حاول مجددًا.', 409)
            rows[device_id] = {**data, **(metadata or {}), 'sessionHash': key}
            await self.save(uid, rows)
            value = json.dumps(data)
            if s.r is None:
                s.mem_sessions[key] = MemoryEntry(value, time.monotonic() + SESSION_TTL)
            else:
                await s.r.set(s.k_session(key), value, ex=SESSION_TTL)
        await s.touch_presence(uid)
        return token

    async def devices(self, user, current_key, metadata):
        from social_platform import now_ms, SESSION_TTL
        uid, s = str(user['id']), self.s
        async with self.transaction(uid):
            rows = await self.records(uid)
            # Existing cookies from before this feature are enrolled on demand.
            # Global revocation also invalidates legacy cookies that never enroll.
            raw = await self.raw(current_key)
            if raw and not any(v['sessionHash'] == current_key for v in rows.values()):
                data = json.loads(raw)
                remaining = await getattr(s.r, 'transient', s.r).ttl(s.k_session(current_key)) if s.r is not None else int(s.mem_sessions[current_key].expires_at - time.monotonic())
                if data.get('uid') == uid and remaining > 0:
                    rows[secrets.token_urlsafe(18)] = {**data, **metadata, 'sessionHash': current_key,
                        'createdAt': None, 'expiresAt': now_ms() + min(remaining, SESSION_TTL) * 1000}
            active, result = {}, []
            for device_id, row in rows.items():
                if row['expiresAt'] <= now_ms() or row['version'] != str(user.get('authVersion') or '0'):
                    continue
                if not await self.raw(row['sessionHash']):
                    continue
                active[device_id] = row
                seen = await s.r.get(self.seen_key(row['sessionHash'])) if s.r is not None else self.seen.get(row['sessionHash'])
                result.append({'id': device_id, 'device': row.get('device', 'جهاز غير معروف'),
                    'client': row.get('client', 'متصفح'), 'country': row.get('country', ''),
                    'createdAt': row.get('createdAt'), 'lastSeenAt': int(seen) if seen else row.get('createdAt'),
                    'expiresAt': row['expiresAt'], 'current': row['sessionHash'] == current_key})
            await self.save(uid, active)
        return sorted(result, key=lambda v: (v['current'], v['lastSeenAt'] or 0), reverse=True)

    async def revoke(self, uid, device_id, current_key):
        from social_platform import PlatformError
        s = self.s
        async with self.transaction(uid):
            rows = await self.records(uid)
            row = rows.pop(device_id, None)
            if not row:
                raise PlatformError('DEVICE_NOT_FOUND', 'الجهاز غير موجود أو انتهت جلسته', 404)
            await self.drop(row['sessionHash'])
            await self.save(uid, rows)
            return row['sessionHash'] == current_key

    async def revoke_all(self, uid):
        s = self.s
        async with self.transaction(uid):
            user = await s.get_user(uid)
            fields = {'authVersion': str(int(user.get('authVersion') or 0) + 1)}
            if s.r is None:
                user.update(fields)
            else:
                await s.r.hset(s.k_user(uid), mapping=fields)
            for row in (await self.records(uid)).values():
                await self.drop(row['sessionHash'])
            await self.save(uid, {})


class AccountSecurityHttp:
    def __init__(self, api):
        self.api, self.s = api, api.platform

    def install(self, router):
        from account_deletion import delete_account, deletion_preview
        router.add_get('/api/account', self.account)
        router.add_get('/api/account/devices', self.devices)
        router.add_delete('/api/account/devices/{device_id}', self.revoke)
        router.add_post('/api/account/logout-all', self.revoke_all)
        async def remove(request):
            return await delete_account(self.api, request)
        async def preview(request):
            return await deletion_preview(self.api, request)
        router.add_post('/api/account/delete', remove)
        router.add_post('/api/account/deletion-preview', preview)

    async def account(self, request):
        from aiohttp import web
        from firebase_identity import FirebaseFailure
        from social_platform import PlatformError
        user = await self.api._user(request)
        await self.limit(user, 'info', 30)
        info = {'email': '', 'providers': [], 'isGuest': user.get('guest') == '1'}
        if user.get('firebaseUid'):
            try:
                info.update(await self.s.firebase.account_info(user['firebaseUid']))
            except FirebaseFailure as error:
                raise PlatformError(error.code, error.message, error.status) from None
        return web.json_response({'ok': True, **info}, headers={'Cache-Control': 'private, no-store'})

    async def devices(self, request):
        from aiohttp import web
        from social_platform import SESSION_COOKIE
        user = await self.api._user(request)
        await self.limit(user, 'devices', 60)
        rows = await self.s.security.devices(user, self.s.token_key(request.cookies.get(SESSION_COOKIE)),
            device_metadata(request, trust_proxy=self.api.trust_proxy))
        return web.json_response({'ok': True, 'devices': rows}, headers={'Cache-Control': 'private, no-store'})

    async def revoke(self, request):
        from aiohttp import web
        from social_platform import SESSION_COOKIE
        user = await self.api._user(request)
        await self.limit(user, 'revoke', 30)
        current = await self.s.security.revoke(str(user['id']), request.match_info['device_id'],
            self.s.token_key(request.cookies.get(SESSION_COOKIE)))
        response = web.json_response({'ok': True, 'signedOut': current})
        if current:
            response.del_cookie(SESSION_COOKIE, path='/')
        return response

    async def revoke_all(self, request):
        from aiohttp import web
        from social_platform import SESSION_COOKIE, PlatformError
        from firebase_identity import FirebaseFailure
        user = await self.api._user(request)
        await self.limit(user, 'logout-all', 10)
        if user.get('firebaseUid'):
            try:
                await self.s.firebase.revoke_sessions(user['firebaseUid'])
            except FirebaseFailure as error:
                raise PlatformError(error.code, error.message, error.status) from None
        await self.s.security.revoke_all(str(user['id']))
        response = web.json_response({'ok': True, 'signedOut': True})
        response.del_cookie(SESSION_COOKIE, path='/')
        return response

    async def limit(self, user, action, count):
        from social_platform import PlatformError
        if not await self.s.allow_rate(f"account-{action}:{user['id']}", count, 60):
            raise PlatformError('RATE_LIMIT', 'محاولات كثيرة؛ حاول بعد قليل', 429)
