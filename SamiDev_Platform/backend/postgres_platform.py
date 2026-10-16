"""PostgreSQL social service with atomic registration, purchases and friendship.

Existing password hashes and API payloads are retained. Redis only receives the
short-lived session/ticket/presence/rate-limit keys through the routing store.
"""
import secrets

from postgres_store import PostgresSocialStore
from social_platform import (
    PlatformService, PlatformError, normalize_username, normalize_display,
    _hash_password, now_ms, public_user,
)


class PostgresPlatformService(PlatformService):
    def __init__(self, url, transient, *, max_connections=10):
        if transient is None:
            raise RuntimeError('PostgreSQL social mode requires a shared Redis realtime store')
        super().__init__(PostgresSocialStore(url, transient, max_connections=max_connections))

    async def start(self):
        await self.r.start()
        try:
            await super().start()
        except BaseException:
            await self.r.close()
            raise

    async def close(self):
        await self.live.close()
        await self.r.close()

    async def create_user(self, username, password, display_name=None, *, role='user', allow_existing=False):
        username = normalize_username(username)
        lower = username.lower()
        display = username
        # Expensive password hashing happens before acquiring database locks.
        encoded = await self.password_work(_hash_password, password)
        uid = secrets.token_urlsafe(12)
        user = dict(id=uid, username=username, usernameLower=lower, displayName=display,
                    passwordHash=encoded, role=role if role in {'user', 'admin', 'moderator'} else 'user',
                    createdAt=str(now_ms()), wins='0', reputation='0', coins='0', banned='0',
                    starsCount='0', nameBadge='')
        username_key = self.k_username(lower)
        # Account enumeration uses SQL, avoiding one growing, globally locked
        # users-set document on every registration.
        async with self.r.transaction([username_key, self.k_user(uid)]):
            existing_id = await self.r.get(username_key)
            if not existing_id:
                await self.r.set(username_key, uid)
                await self.r.hset(self.k_user(uid), mapping=user)
                return user
        if allow_existing:
            existing = await self.get_user(existing_id)
            if existing: return existing
        raise PlatformError('USERNAME_TAKEN', 'اسم المستخدم مستخدم بالفعل', 409)

    async def firebase_account(self, claims, *, username="", display_name=None):
        identity_key = self.k_firebase(claims["uid"])
        # Re-read after a concurrent first login; one Firebase UID gets one profile.
        for _ in range(3):
            mapped = await self.r.get(identity_key)
            uid = mapped or secrets.token_urlsafe(12)
            normalized = normalize_username(username or ('Player_' + secrets.token_hex(5))) if not mapped else None
            keys = [identity_key, self.k_user(uid)]
            if normalized: keys.append(self.k_username(normalized.lower()))
            async with self.r.transaction(keys):
                current = await self.r.get(identity_key)
                if current and current != uid:
                    continue
                user = await self.get_user(uid)
                if current:
                    if not user or user.get('firebaseUid') != claims['uid'] or user.get('firebaseProject') != self.firebase.project:
                        raise PlatformError('IDENTITY_CONFLICT', 'تعذر مطابقة هوية الحساب.', 409)
                    if str(user.get('banned') or '0') == '1':
                        raise PlatformError('ACCOUNT_BANNED', 'هذا الحساب محظور', 403)
                    if claims['uid'] == self.firebase.admin_uid and user.get('role') != 'admin':
                        user['role'] = 'admin'
                        await self.r.hset(self.k_user(uid), mapping={'role': 'admin'})
                    return user
                if normalized is None:
                    continue  # Identity was removed while acquiring the locks.
                if await self.r.get(self.k_username(normalized.lower())):
                    if not username:
                        continue
                    raise PlatformError('USERNAME_TAKEN', 'اسم المستخدم مستخدم بالفعل', 409)
                user = dict(id=uid, username=normalized, usernameLower=normalized.lower(),
                    displayName=normalized, passwordHash='',
                    role='admin' if claims['uid'] == self.firebase.admin_uid else 'user',
                    createdAt=str(now_ms()), wins='0', reputation='0', coins='0', banned='0',
                    starsCount='0', nameBadge='', firebaseUid=claims['uid'],
                    firebaseProject=self.firebase.project, firebaseEmail=claims['email'], authVersion='1')
                await self.r.set(self.k_username(normalized.lower()), uid)
                await self.r.hset(self.k_user(uid), mapping=user)
                await self.r.set(identity_key, uid)
                return user
        raise PlatformError('AUTH_BUSY', 'الحساب يُحدّث الآن، حاول مجددًا.', 503)

    async def buy_store_item(self, uid, item_id):
        async with self.r.transaction([self.k_user(uid), self.k_inventory(uid), self.k_store_ledger(uid)]):
            return await super().buy_store_item(uid, item_id)

    async def update_profile(self, uid, **kwargs):
        # Renames manage their own username locks. An avatar update takes the
        # account lock so an in-flight request cannot recreate deleted data.
        display_name = kwargs.pop('display_name', None)
        if display_name is not None:
            await self.accounts.rename(uid, display_name)
        async with self.r.transaction([self.k_user(uid)]):
            return await super().update_profile(uid, **kwargs)

    async def submit_report(self, reporter_id, target_id, **kwargs):
        async with self.r.transaction([self.k_user(reporter_id), self.k_user(target_id), self.k_reports()]):
            return await super().submit_report(reporter_id, target_id, **kwargs)

    async def set_role(self, target_id, role):
        async with self.r.transaction([self.k_user(target_id)]):
            return await super().set_role(target_id, role)

    async def set_banned(self, target_id, banned):
        async with self.r.transaction([self.k_user(target_id)]):
            return await super().set_banned(target_id, banned)

    async def record_game_result(self, uid, game, match, *, won, drawn=False):
        from games import GAMES
        if game not in GAMES or not match or len(match) > 128 or (won and drawn):
            raise PlatformError('BAD_MATCH_RESULT', 'نتيجة المباراة غير صالحة')
        user_key, stats_key = self.k_user(uid), self.k_game_stats(uid, game)
        legacy_claim = self.k_game_result(uid, match)
        async with self.r.transaction([user_key, stats_key, legacy_claim]) as conn:
            if not await self.r.exists(user_key): return False
            if await self.r.exists(legacy_claim): return False
            inserted = await conn.fetchval('''INSERT INTO samidev_match_results(account_key,match_id,game_id,outcome)
                VALUES ($1,$2,$3,$4) ON CONFLICT DO NOTHING RETURNING true''',
                user_key, match, game, 'win' if won else 'draw' if drawn else 'loss')
            if not inserted: return False
            await self.r.hincrby(stats_key, 'played', 1)
            if won:
                await self.r.hincrby(stats_key, 'wins', 1)
                await self.r.hincrby(user_key, 'wins', 1)
            if drawn: await self.r.hincrby(stats_key, 'draws', 1)
            return True

    async def equip_store_item(self, uid, item_id):
        async with self.r.transaction([self.k_user(uid), self.k_inventory(uid), self.k_equipped(uid)]):
            return await super().equip_store_item(uid, item_id)

    def _friend_keys(self, a, b):
        return [self.k_user(a), self.k_user(b), self.k_requests(a), self.k_requests(b),
                self.k_friends(a), self.k_friends(b)]

    async def send_friend_request(self, sender, target_username):
        target = await self.find_user_by_username(target_username)
        if not target:
            raise PlatformError('USER_NOT_FOUND', 'المستخدم غير موجود', 404)
        a, b = str(sender['id']), str(target['id'])
        async with self.r.transaction(self._friend_keys(a, b) + [self.k_username(target['usernameLower'])]):
            return await super().send_friend_request(sender, target_username)

    async def respond_friend_request(self, user, sender_id, accept):
        async with self.r.transaction(self._friend_keys(str(user['id']), sender_id)):
            return await super().respond_friend_request(user, sender_id, accept)

    async def search_users(self, query, current_uid, limit=15):
        q = str(query or '').strip().lower()
        if len(q) < 2: return []
        # Search in SQL instead of fetching every account from a Redis set.
        async with self.r.pool.acquire() as conn:
            rows = await conn.fetch('''SELECT value->>'id' AS id
                FROM samidev_social_documents
                WHERE kind='hash' AND key LIKE $1 AND value->>'id' <> $2
                AND strpos(lower(concat(value->>'username', ' ', value->>'displayName')), $3) > 0
                ORDER BY key LIMIT $4''', self.k_user('') + '%', current_uid, q, max(1, min(100, int(limit))))
        out = []
        for row in rows:
            uid = row['id']
            user = await self.get_user(uid)
            if user:
                relation = 'friend' if await self.are_friends(current_uid, uid) else 'none'
                out.append(public_user(user, relation=relation, online=await self.is_online(uid)))
        return out

    async def list_users(self, limit=200):
        async with self.r.pool.acquire() as conn:
            rows = await conn.fetch('''SELECT value->>'id' AS id
                FROM samidev_social_documents WHERE kind='hash' AND key LIKE $1
                ORDER BY (value->>'createdAt')::bigint DESC LIMIT $2''',
                self.k_user('') + '%', max(1, min(500, int(limit))))
        out = []
        for row in rows:
            user = await self.get_user(row['id'])
            if user: out.append(public_user(user, online=await self.is_online(row['id'])))
        return out
