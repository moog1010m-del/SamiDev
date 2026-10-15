"""Guest identity upgrades and atomic single-name changes on existing player ids."""
import json
import secrets
from contextlib import asynccontextmanager


class AccountLifecycle:
    def __init__(self, service):
        self.service = service

    @asynccontextmanager
    async def transaction(self, keys):
        from social_platform import PlatformError
        if self.service.r is None:
            async with self.service.lock:
                yield
        elif hasattr(self.service.r, 'pool'):
            async with self.service.r.transaction(keys):
                yield
        else:
            raise PlatformError('DURABLE_STORE_REQUIRED', 'الحسابات تتطلب PostgreSQL', 503)

    async def guest(self):
        from social_platform import now_ms, PlatformError
        s = self.service
        for _ in range(4):
            uid, name = secrets.token_urlsafe(12), 'Guest_' + secrets.token_hex(5)
            key = s.k_username(name.lower())
            async with self.transaction([key, s.k_user(uid)]):
                exists = await s.r.get(key) if s.r is not None else s.mem_usernames.get(name.lower())
                if exists:
                    continue
                user = dict(id=uid, username=name, usernameLower=name.lower(), displayName=name,
                            passwordHash='', role='user', guest='1', authVersion='1',
                            createdAt=str(now_ms()), wins='0', reputation='0', coins='0',
                            banned='0', starsCount='0', nameBadge='badge_palm_swords')
                if s.r is None:
                    s.mem_users[uid] = user
                    s.mem_usernames[name.lower()] = uid
                else:
                    await s.r.set(key, uid)
                    await s.r.hset(s.k_user(uid), mapping=user)
                return user
        raise PlatformError('AUTH_BUSY', 'حاول مجددًا', 503)

    async def link(self, uid, claims, username=''):
        from social_platform import normalize_username, PlatformError
        s = self.service
        for _ in range(4):
            previous = await s.get_user(uid)
            if not previous:
                raise PlatformError('AUTH_REQUIRED', 'جلسة الضيف غير متاحة', 401)
            old = previous['usernameLower']
            name = normalize_username(username) if username else previous['username']
            lower = name.lower()
            identity = s.k_firebase(claims['uid'])
            async with self.transaction([s.k_user(uid), s.k_username(old), s.k_username(lower), identity]):
                user = await s.get_user(uid)
                if user['usernameLower'] != old:
                    continue
                if str(user.get('banned') or '0') == '1':
                    raise PlatformError('ACCOUNT_BANNED', 'هذا الحساب محظور', 403)
                if user.get('guest') != '1' or user.get('firebaseUid'):
                    raise PlatformError('NOT_A_GUEST', 'هذا الحساب مرتبط بالفعل', 409)
                mapped = await s.r.get(identity) if s.r is not None else s.mem_firebase.get((s.firebase.project, claims['uid']))
                if mapped:
                    raise PlatformError('ACCOUNT_ALREADY_LINKED', 'هذا البريد مرتبط بحساب موجود. اختر الدخول إلى حسابك بدل الربط.', 409)
                owner = await s.r.get(s.k_username(lower)) if s.r is not None else s.mem_usernames.get(lower)
                if owner and owner != uid:
                    raise PlatformError('USERNAME_TAKEN', 'اسم المستخدم مستخدم بالفعل', 409)
                fields = dict(guest='0', username=name, usernameLower=lower, displayName=name,
                              firebaseUid=claims['uid'], firebaseProject=s.firebase.project,
                              firebaseEmail=claims['email'], authVersion=str(int(user.get('authVersion') or 0)+1))
                if claims['uid'] == s.firebase.admin_uid:
                    fields['role'] = 'admin'
                if s.r is None:
                    s.mem_usernames.pop(old, None)
                    s.mem_usernames[lower] = uid
                    s.mem_firebase[(s.firebase.project, claims['uid'])] = uid
                    user.update(fields)
                else:
                    if old != lower:
                        await s.r.delete(s.k_username(old))
                    await s.r.set(s.k_username(lower), uid)
                    await s.r.hset(s.k_user(uid), mapping=fields)
                    await s.r.set(identity, uid)
                return {**user, **fields}
        raise PlatformError('AUTH_BUSY', 'حاول مجددًا', 503)

    async def rename(self, uid, value):
        from social_platform import normalize_username, PlatformError, now_ms, STORE_LEDGER_MAX
        s, name = self.service, normalize_username(value)
        lower = name.lower()
        for _ in range(4):
            previous = await s.get_user(uid)
            if not previous:
                raise PlatformError('AUTH_REQUIRED', 'الحساب غير موجود', 401)
            old = previous['usernameLower']
            async with self.transaction([s.k_user(uid), s.k_username(old), s.k_username(lower), s.k_store_ledger(uid)]):
                user = await s.get_user(uid)
                if user['usernameLower'] != old:
                    continue
                if user['username'] == name:
                    return user
                owner = await s.r.get(s.k_username(lower)) if s.r is not None else s.mem_usernames.get(lower)
                if owner and owner != uid:
                    raise PlatformError('USERNAME_TAKEN', 'اسم المستخدم مستخدم بالفعل', 409)
                free = user.get('freeRenameUsed') != '1'
                credits = int(user.get('renameCredits') or 0)
                if not free and credits < 1:
                    raise PlatformError('RENAME_ITEM_REQUIRED', 'استخدمت التغيير المجاني. اشتر بطاقة تغيير الاسم من المتجر.', 409)
                fields = dict(username=name, usernameLower=lower, displayName=name,
                              freeRenameUsed='1', renameCredits=str(credits if free else credits-1))
                entry = dict(id=secrets.token_urlsafe(10), type='username_change', createdAt=now_ms(),
                             oldUsername=user['username'], username=name, usedFree=free)
                if s.r is None:
                    s.mem_usernames.pop(old, None)
                    s.mem_usernames[lower] = uid
                    user.update(fields)
                    rows = s.mem_store_ledger.setdefault(uid, [])
                    rows.insert(0, entry)
                    del rows[STORE_LEDGER_MAX:]
                else:
                    if old != lower:
                        await s.r.delete(s.k_username(old))
                    await s.r.set(s.k_username(lower), uid)
                    await s.r.hset(s.k_user(uid), mapping=fields)
                    await s.r.lpush(s.k_store_ledger(uid), json.dumps(entry))
                    await s.r.ltrim(s.k_store_ledger(uid), 0, STORE_LEDGER_MAX-1)
                return {**user, **fields}
        raise PlatformError('AUTH_BUSY', 'حاول مجددًا', 503)
