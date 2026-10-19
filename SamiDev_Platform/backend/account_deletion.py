"""Retryable self-service deletion; pending accounts cannot authenticate."""
import asyncio
import json
import logging
import time


class AccountDeletion:
    def __init__(self, service):
        self.s, self.jobs, self.task = service, {}, None

    def key(self, uid):
        from social_platform import PREFIX
        return f'{PREFIX}:account-deletion:{uid}'

    async def request(self, user):
        from social_platform import PlatformError, now_ms
        s, uid = self.s, str(user['id'])
        async with s.accounts.transaction([s.k_user(uid), self.key(uid)]):
            current = await s.get_user(uid)
            if not current:
                raise PlatformError('AUTH_REQUIRED', 'الحساب غير متاح', 401)
            job = {'id': uid, 'usernameLower': current['usernameLower'],
                   'firebaseUid': current.get('firebaseUid', ''), 'firebaseProject': current.get('firebaseProject', ''), 'requestedAt': now_ms()}
            fields = {'deleting': '1', 'authVersion': str(int(current.get('authVersion') or 0) + 1)}
            if s.r is None:
                current.update(fields)
                self.jobs[uid] = job
            else:
                await s.r.set(self.key(uid), json.dumps(job))
                await s.r.hset(s.k_user(uid), mapping=fields)
        # The durable job is written BEFORE contacting Firebase. Outage or crash
        # leaves a disabled account and an idempotent job, not a lost request.
        return await self.process(uid)

    async def process(self, uid):
        s = self.s
        job = json.loads(raw) if s.r is not None and (raw := await s.r.get(self.key(uid))) else self.jobs.get(uid)
        if not job:
            return True
        try:
            if job['firebaseUid']:
                if not s.firebase.enabled or job['firebaseProject'] != s.firebase.project:
                    raise RuntimeError('Deletion identity project mismatch')
                await s.firebase.delete_user(job['firebaseUid'])
            await self.purge(job)
            return True
        except asyncio.CancelledError:
            raise
        except Exception as error:
            # No email, credential, body or exception message goes to logs.
            logging.getLogger('samidev.auth').warning(json.dumps({
                'event': 'account.deletion_retry', 'accountId': uid, 'errorType': type(error).__name__}))
            return False

    @staticmethod
    def involves(row, uid):
        return isinstance(row, dict) and any(row.get(k) == uid for k in ('userId', 'actorId', 'targetId', 'reporterId', 'senderId'))

    async def purge(self, job):
        from social_platform import PREFIX, COMMUNITIES
        s, uid = self.s, job['id']
        identity = s.k_firebase(job['firebaseUid']) if job['firebaseUid'] else ''
        if s.r is None:
            async with s.lock:
                if uid not in self.jobs:
                    return
                for key, entry in list(s.mem_sessions.items()):
                    if json.loads(entry.value).get('uid') == uid:
                        await s.security.drop(key)
                s.security.memory.pop(uid, None)
                for mapping in (s.mem_users, s.mem_friends, s.mem_requests, s.mem_presence, s.mem_inventory,
                        s.mem_equipped, s.mem_store_ledger, s.mem_game_stats, s.mem_active_community, s.safety.memory):
                    mapping.pop(uid, None)
                if s.mem_usernames.get(job['usernameLower']) == uid:
                    s.mem_usernames.pop(job['usernameLower'], None)
                s.mem_firebase.pop((s.firebase.project, job['firebaseUid']), None)
                for mapping in (s.mem_friends, s.mem_requests, s.safety.memory):
                    for value in mapping.values():
                        value.discard(uid)
                for mapping in (s.mem_community_chat, s.community_rules.audit):
                    for key, rows in mapping.items():
                        mapping[key] = [row for row in rows if not self.involves(row, uid)]
                s.mem_reports[:] = [r for r in s.mem_reports if not self.involves(r, uid)]
                for mapping in (s.mem_daily_match_counts, s.mem_rep_daily):
                    for key in list(mapping):
                        if uid in key:
                            mapping.pop(key, None)
                for targets in s.mem_rep_daily.values():
                    targets.discard(uid)
                for name in ('mem_game_results', 'mem_match_reward_claims', 'mem_match_ratings'):
                    setattr(s, name, {row for row in getattr(s, name) if uid not in row})
                for key, entry in list(s.mem_tickets.items()):
                    if uid in str(entry.value):
                        s.mem_tickets.pop(key, None)
                self.jobs.pop(uid, None)
        else:
            # Deletion is available for durable PostgreSQL accounts. Identify
            # exact owned keys and inbound references, then take the same ordered
            # advisory locks as normal writes before removing each reference.
            async def candidates(conn):
                return await conn.fetch('''SELECT key,kind,value FROM samidev_social_documents
                    WHERE split_part(key, ':', 1)=$1 AND (
                        $2=ANY(string_to_array(key, ':')) OR key=ANY($3::text[])
                        OR (kind='set' AND value ? $2)
                        OR (kind='list' AND split_part(key, ':', 2) IN ('community','reports','moderation-audit'))
                    )''', PREFIX, uid, [identity, s.k_username(job['usernameLower'])])
            for _ in range(4):
                async with s.r.pool.acquire() as conn:
                    rows = await candidates(conn)
                keys = {r['key'] for r in rows} | {s.k_user(uid), self.key(uid), s.security.key(uid)}
                async with s.accounts.transaction(keys) as conn:
                    fresh = await candidates(conn)
                    if any(row['key'] not in keys for row in fresh):
                        # A pre-existing in-flight write added a reference before
                        # the account lock. Retry with the complete ordered set.
                        continue
                    rows = fresh
                    if not await s.r.get(self.key(uid)):
                        return  # Another gateway already finished this job.
                    for row in (await s.security.records(uid)).values():
                        await s.security.drop(row['sessionHash'])
                    for row in rows:
                        key, kind = row['key'], row['kind']
                        if key == self.key(uid):
                            continue
                        if key in {identity, s.k_username(job['usernameLower'])}:
                            if await s.r.get(key) == uid:
                                await s.r.delete(key)
                        elif uid in key.split(':'):
                            await s.r.delete(key)
                        elif kind == 'set':
                            await s.r.srem(key, uid)
                        elif kind == 'list':
                            current = await s.r.lrange(key, 0, -1)
                            filtered = [v for v in current if not self.involves(json.loads(v), uid)]
                            if len(filtered) != len(current):
                                await s.r.delete(key)
                                if filtered:
                                    await s.r.rpush(key, *filtered)
                    # The account FK cascades into durable match results.
                    await s.r.delete(s.k_user(uid), s.security.key(uid), self.key(uid))
                break
            else:
                raise RuntimeError('Concurrent account cleanup; retry queued')
            await s.r.delete(s.k_presence(uid), s.k_active_community(uid))
            for cid in COMMUNITIES:
                await s.r.srem(s.k_community_members(cid), uid)
        for cid in COMMUNITIES:
            await s.live.publish(cid, {'type': 'resync'})

    async def pending(self):
        if self.s.r is None:
            return list(self.jobs)[:10]
        from social_platform import PREFIX
        async with self.s.r.pool.acquire() as conn:
            return [r['uid'] for r in await conn.fetch('''SELECT split_part(key, ':', 3) AS uid
                FROM samidev_social_documents WHERE split_part(key, ':', 1)=$1
                AND split_part(key, ':', 2)='account-deletion' ORDER BY key LIMIT 10''', PREFIX)]

    async def run(self):
        while True:
            try:
                for uid in await self.pending():
                    await self.process(uid)
            except asyncio.CancelledError:
                raise
            except Exception:
                logging.getLogger('samidev.auth').warning('{"event":"account.deletion_worker_unavailable"}')
            await asyncio.sleep(30)

    async def start(self, app):
        if self.s.r is None or hasattr(self.s.r, 'pool'):
            self.task = asyncio.create_task(self.run(), name='account-deletions')

    async def stop(self, app):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)


async def delete_account(api, request):
    from aiohttp import web
    from social_platform import PlatformError, SESSION_COOKIE
    if not await api.platform.allow_rate(f"delete-proof:{api._peer(request)}", 20, 300):
        raise PlatformError('RATE_LIMIT', 'محاولات كثيرة؛ حاول لاحقًا', 429)
    user = await api._optional_user(request)
    try:
        body = await api._body(request)
    except PlatformError:
        if not user:
            raise PlatformError('AUTH_REQUIRED', 'أكد هويتك أولًا', 401) from None
        raise
    if not user and not isinstance(body.get('idToken'), str):
        raise PlatformError('AUTH_REQUIRED', 'أكد هويتك أولًا', 401)
    if body.get('confirm') != 'DELETE':
        raise PlatformError('CONFIRM_DELETE_REQUIRED', 'أكد حذف الحساب أولًا', 400)
    if not user or user.get('firebaseUid'):
        user, _ = await firebase_deletion_identity(api, body.get('idToken'), expected=user)
    elif user.get('guest') != '1':
        checked = await api.platform.authenticate(user['username'], str(body.get('password') or ''))
        if checked['id'] != user['id']:
            raise PlatformError('REAUTH_REQUIRED', 'أكد هوية حسابك', 403)
    if not await api.platform.allow_rate(f"delete-account:{user['id']}", 5, 300):
        raise PlatformError('RATE_LIMIT', 'محاولات كثيرة؛ حاول لاحقًا', 429)
    complete = await api.platform.deletions.request(user)
    response = web.json_response({'ok': True, 'deleted': complete, 'pending': not complete, 'signedOut': True}, status=200 if complete else 202)
    response.del_cookie(SESSION_COOKIE, path='/')
    return response


async def firebase_deletion_identity(api, token, *, expected=None):
    from firebase_identity import FirebaseFailure
    from social_platform import PlatformError
    s = api.platform
    try:
        claims = await s.firebase.verify(token)
    except FirebaseFailure as error:
        raise PlatformError(error.code, error.message, 403 if error.status == 401 else error.status) from None
    user = expected
    if not user:
        # A verified UID is the only selector. Names, emails and body userIds
        # cannot resolve an account, including in the public deletion flow.
        mapped = await s.r.get(s.k_firebase(claims['uid'])) if s.r is not None else s.mem_firebase.get((s.firebase.project, claims['uid']))
        user = await s.get_user(mapped) if mapped else None
        if not user:
            raise PlatformError('ACCOUNT_NOT_FOUND', 'الحساب غير موجود أو حُذف بالفعل', 404)
    if (claims['uid'] != user.get('firebaseUid') or user.get('firebaseProject') != s.firebase.project
            or time.time() - claims['auth_time'] > 300):
        raise PlatformError('REAUTH_REQUIRED', 'أكد الدخول إلى نفس الحساب مجددًا قبل الحذف', 403)
    return user, claims


async def deletion_preview(api, request):
    from aiohttp import web
    from social_platform import PlatformError
    if not await api.platform.allow_rate(f'deletion-preview:{api._peer(request)}', 20, 300):
        raise PlatformError('RATE_LIMIT', 'محاولات كثيرة؛ حاول لاحقًا', 429)
    body = await api._body(request)
    user, claims = await firebase_deletion_identity(api, body.get('idToken'))
    return web.json_response({'ok': True, 'username': user['username'], 'email': claims['email']}, headers={'Cache-Control':'private, no-store'})
