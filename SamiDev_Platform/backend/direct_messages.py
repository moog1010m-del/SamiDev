"""Friend-only messaging. Durable bounded histories; isolated personal event bus."""
import asyncio
import hashlib
import json
import os
import re
import secrets
import time
from aiohttp import web
from community_live import CommunityLive


class DirectMessages:
    def __init__(self, service):
        self.s = service
        self.memory = {}
        self.push_queue = asyncio.Queue(maxsize=128)
        self.push_task = None
        self.live = CommunityLive(service, namespace='personal-live')

    def key(self, kind, *ids):
        from social_platform import PREFIX
        return ':'.join((PREFIX, kind, *ids))

    def thread(self, a, b):
        return self.key('direct', *sorted((a, b)))

    async def get(self, key, default=None):
        raw = await self.s.r.get(key) if self.s.r is not None else self.memory.get(key)
        return json.loads(raw) if raw else default

    async def put(self, key, value):
        raw = json.dumps(value, ensure_ascii=False, separators=(',', ':'))
        if self.s.r is None: self.memory[key] = raw
        else: await self.s.r.set(key, raw)

    def locks(self, a, b, *keys):
        s = self.s
        return [s.k_user(a), s.k_user(b), s.k_friends(a), s.k_friends(b),
                s.safety.key(a), s.safety.key(b), *keys]

    async def access(self, a, b):
        from social_platform import PlatformError
        if not re.fullmatch(r'[A-Za-z0-9_-]{12,32}', b) or a == b:
            raise PlatformError('BAD_USER', 'اختر صديقًا صالحًا')
        users = [await self.s.get_user(a), await self.s.get_user(b)]
        if not all(users) or any(u.get('deleting') == '1' or u.get('banned') == '1' for u in users):
            raise PlatformError('USER_NOT_FOUND', 'الحساب غير متاح', 404)
        if await self.s.safety.pair_blocked(a, b) or not await self.s.are_friends(a, b):
            raise PlatformError('FRIENDS_REQUIRED', 'المحادثة متاحة للأصدقاء فقط', 403)
        return users[1]

    async def history(self, a, b):
        from social_platform import public_user
        peer = await self.access(a, b)
        doc = await self.get(self.thread(a, b), {'seq': 0, 'messages': [], 'read': {}})
        return {'user': public_user(peer, online=await self.s.is_online(b)),
                'messages': doc['messages'], 'seq': doc['seq'],
                'muted': bool(await self.get(self.key('direct-mute', a, b), False))}

    async def send(self, a, b, body):
        from social_platform import PlatformError, sanitize_plain_text, now_ms, public_user
        text = body.get('text')
        nonce = body.get('clientMessageId')
        if not isinstance(text, str) or not text.strip() or len(text) > 2000:
            raise PlatformError('BAD_MESSAGE', 'اكتب رسالة من حرف إلى ٢٠٠٠ حرف')
        text = sanitize_plain_text(text, 2000)
        if not text.strip(): raise PlatformError('BAD_MESSAGE', 'اكتب رسالة صالحة')
        if not isinstance(nonce, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,80}', nonce):
            raise PlatformError('BAD_MESSAGE_ID', 'تعذر التحقق من الرسالة')
        key = self.thread(a, b)
        mute = self.key('direct-mute', b, a)
        async with self.s.accounts.transaction(self.locks(a, b, key, mute)):
            await self.access(a, b)
            doc = await self.get(key, {'seq': 0, 'messages': [], 'read': {}})
            old = next((m for m in doc['messages'] if m['senderId'] == a and m['clientMessageId'] == nonce), None)
            if old: return old
            doc['seq'] += 1
            msg = dict(id=secrets.token_urlsafe(16), seq=doc['seq'], senderId=a, text=text,
                       createdAt=now_ms(), clientMessageId=nonce)
            doc['messages'] = (doc['messages'] + [msg])[-500:]
            doc['read'][a] = doc['seq']
            await self.put(key, doc)
            muted = bool(await self.get(mute, False))
        # Events carry no private body: consumers fetch through authorization.
        await asyncio.gather(*(self.live.publish(uid, {'type': 'direct', 'peerId': peer, 'messageId': msg['id'], 'notify': not muted and uid == b}) for uid, peer in ((a, b), (b, a))))
        if not muted and os.getenv('SAMIDEV_PUSH_ENABLED') == '1':
            if self.push_task is None: self.push_task = asyncio.create_task(self.push_worker(), name='friend-push')
            try: self.push_queue.put_nowait((b, a, msg['id']))
            except asyncio.QueueFull: pass
        return msg

    async def read(self, a, b, seq):
        from social_platform import PlatformError
        if type(seq) is not int or seq < 0: raise PlatformError('BAD_SEQUENCE', 'رقم قراءة غير صالح')
        key = self.thread(a, b)
        async with self.s.accounts.transaction(self.locks(a, b, key)):
            await self.access(a, b)
            doc = await self.get(key, {'seq': 0, 'messages': [], 'read': {}})
            previous = doc['read'].get(a, 0)
            doc['read'][a] = max(previous, min(seq, doc['seq']))
            if previous == doc['read'][a]: return
            await self.put(key, doc)
        await self.live.publish(a, {'type': 'resync'})

    async def mute(self, a, b, enabled):
        from social_platform import PlatformError
        if type(enabled) is not bool: raise PlatformError('BAD_MUTE', 'اختر حالة كتم صالحة')
        key = self.key('direct-mute', a, b)
        async with self.s.accounts.transaction(self.locks(a, b, key)):
            await self.access(a, b)
            await self.put(key, enabled)
        await self.live.publish(a, {'type': 'resync'})
        return enabled

    async def inbox(self, user):
        a = user['id']
        social = await self.s.social_state(user)
        threads = []
        for peer in social['friends']:
            b = peer['id']
            if await self.s.safety.pair_blocked(a, b): continue
            doc = await self.get(self.thread(a, b), {'seq': 0, 'messages': [], 'read': {}})
            last = doc['messages'][-1] if doc['messages'] else None
            read = doc['read'].get(a, 0)
            threads.append({'user': peer, 'lastMessage': last,
                            'unread': sum(m['senderId'] != a and m['seq'] > read for m in doc['messages']),
                            'muted': bool(await self.get(self.key('direct-mute', a, b), False))})
        threads.sort(key=lambda t: (t['lastMessage'] or {}).get('createdAt', 0), reverse=True)
        return {'threads': threads, 'requests': social['requests'],
                'pushEnabled': os.getenv('SAMIDEV_PUSH_ENABLED') == '1', 'pushConfig': self.push_config()}

    @staticmethod
    def push_config():
        result = {}
        project = os.getenv('SAMIDEV_FIREBASE_PROJECT_ID', '').strip()
        key = os.getenv('SAMIDEV_FIREBASE_API_KEY', '').strip()
        sender = os.getenv('SAMIDEV_FIREBASE_MESSAGING_SENDER_ID', '').strip()
        for platform in ('android', 'ios'):
            app = os.getenv('SAMIDEV_FIREBASE_' + platform.upper() + '_APP_ID', '').strip()
            if project and key and sender and app:
                result[platform] = dict(projectId=project, apiKey=key, messagingSenderId=sender, appId=app)
                if platform == 'ios': result[platform]['iosBundleId'] = 'com.samidev.platform'
        return result

    async def invite(self, uid, token=None):
        from social_platform import PlatformError
        key = self.key('friend-link', uid)
        async with self.s.accounts.transaction([self.s.k_user(uid), key]):
            if not await self.s.get_user(uid): raise PlatformError('AUTH_REQUIRED', 'سجّل الدخول', 401)
            secret = secrets.token_urlsafe(24)
            await self.put(key, {'hash': hashlib.sha256(secret.encode()).hexdigest(), 'expiresAt': int(time.time()) + 7 * 86400})
        return {'url': 'https://plazr.net/platform/?friend=' + uid + '.' + secret, 'expiresInDays': 7}

    async def redeem(self, user, token):
        from social_platform import PlatformError
        if not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{12,32}\.[A-Za-z0-9_-]{32}', token):
            raise PlatformError('INVALID_INVITE', 'رابط الصداقة غير صالح أو انتهى', 404)
        uid, secret = token.split('.')
        doc = await self.get(self.key('friend-link', uid), {})
        target = await self.s.get_user(uid)
        if not target or doc.get('expiresAt', 0) < time.time() or not secrets.compare_digest(doc.get('hash', ''), hashlib.sha256(secret.encode()).hexdigest()):
            raise PlatformError('INVALID_INVITE', 'رابط الصداقة غير صالح أو انتهى', 404)
        return await self.s.send_friend_request(user, target['username'])

    async def devices(self, uid):
        return await self.get(self.key('push-devices', uid), {})

    async def device(self, uid, session, body):
        from social_platform import PlatformError
        device, token = body.get('deviceId'), body.get('fid')
        if not isinstance(device, str) or not re.fullmatch(r'[A-Za-z0-9_-]{16,64}', device):
            raise PlatformError('BAD_DEVICE', 'جهاز غير صالح')
        if token is not None and (not isinstance(token, str) or not re.fullmatch(r'[A-Za-z0-9_-]{22}', token)):
            raise PlatformError('BAD_TOKEN', 'عنوان إشعارات غير صالح')
        key = self.key('push-devices', uid)
        async with self.s.accounts.transaction([self.s.k_user(uid), key]):
            if not await self.s.get_user(uid): raise PlatformError('AUTH_REQUIRED', 'سجّل الدخول', 401)
            devices = await self.devices(uid)
            devices.pop(device, None)
            if token:
                if len(devices) >= 10: raise PlatformError('DEVICE_LIMIT', 'وصلت للحد الأقصى لأجهزة الإشعارات')
                devices[device] = {'fid': token, 'session': session, 'at': int(time.time())}
            await self.put(key, devices)

    async def friendship_changed(self, sender, target, pending=False):
        await asyncio.gather(self.live.publish(sender, {'type': 'resync'}), self.live.publish(target, {'type': 'resync'}))
        if pending and os.getenv('SAMIDEV_PUSH_ENABLED') == '1':
            if self.push_task is None: self.push_task = asyncio.create_task(self.push_worker(), name='friend-push')
            try: self.push_queue.put_nowait((target, sender, '', 'friend_request'))
            except asyncio.QueueFull: pass

    async def close(self):
        await self.live.close()
        if self.push_task:
            self.push_task.cancel()
            await asyncio.gather(self.push_task, return_exceptions=True)
            self.push_task = None

    async def push_worker(self):
        while True:
            args = await self.push_queue.get()
            await self.push(*args)

    async def push(self, uid, sender, message_id, kind="direct"):
        # No private message or invented person names on the lock screen.
        if os.getenv('SAMIDEV_PUSH_ENABLED') != '1': return
        try:
            if kind == 'direct': await self.access(uid, sender)
            else:
                recipient = await self.s.get_user(uid)
                source = await self.s.get_user(sender)
                if not recipient or not source or any(u.get('banned') == '1' or u.get('deleting') == '1' for u in (recipient, source)) or await self.s.safety.pair_blocked(uid, sender): return
                requests = await self.s.r.smembers(self.s.k_requests(uid)) if self.s.r is not None else self.s.mem_requests.get(uid, set())
                if sender not in requests: return
            if await self.get(self.key('direct-mute', uid, sender), False): return
            devices = await self.devices(uid)
            tokens = []
            for doc in devices.values():
                if doc['at'] > time.time() - 30 * 86400:
                    session_user = await self.s.resolve_session_key(doc['session'])
                    if session_user and session_user['id'] == uid: tokens.append(doc['fid'])
            if not tokens: return
            from firebase_admin import messaging
            self.s.firebase._sdk()
            def deliver():
                return messaging.send_each_for_multicast(messaging.MulticastMessage(fids=list(set(tokens)),
                    notification=messaging.Notification(title='Plazr', body='وصلك طلب صداقة جديد' if kind == 'friend_request' else 'وصلتك رسالة جديدة من صديق'),
                    data={'type': kind, 'peerId': sender, 'accountId': uid, 'messageId': message_id},
                    android=messaging.AndroidConfig(ttl=300, notification=messaging.AndroidNotification(channel_id='plazr_friends')),
                    apns=messaging.APNSConfig(headers={'apns-expiration': str(int(time.time()) + 300)}, payload=messaging.APNSPayload(aps=messaging.Aps(sound='default')))), app=self.s.firebase._app)
            await self.s.firebase._work(deliver)
        except asyncio.CancelledError: raise
        except Exception:
            # Committed messages remain successful if the push provider fails.
            import logging
            logging.getLogger(__name__).warning('Friend push delivery unavailable')


class DirectHttp:
    def __init__(self, api): self.api, self.d = api, api.platform.direct

    async def call(self, request):
        from social_platform import PlatformError, SESSION_COOKIE
        user = await self.api._user(request)
        uid = user['id']
        if not await self.api.platform.allow_rate('direct:' + uid, 120, 60):
            raise PlatformError('RATE_LIMIT', 'رسائل كثيرة؛ جرّب بعد قليل', 429)
        op = request.match_info.get('op', '')
        peer = request.match_info.get('user_id', '')
        body = await self.api._body(request) if request.method != 'GET' else {}
        if op == 'inbox': result = await self.d.inbox(user)
        elif op == 'link': result = await self.d.invite(uid)
        elif op == 'redeem':
            result = await self.d.redeem(user, body.get('token'))
            await self.d.friendship_changed(uid, result['user']['id'], result['status'] == 'pending')
        elif op == 'device':
            await self.d.device(uid, self.api.platform.token_key(request.cookies.get(SESSION_COOKIE)), body)
            result = {}
        elif request.method == 'GET': result = await self.d.history(uid, peer)
        elif op == 'messages': result = {'message': await self.d.send(uid, peer, body)}
        elif op == 'read':
            await self.d.read(uid, peer, body.get('seq')); result = {}
        elif op == 'mute': result = {'muted': await self.d.mute(uid, peer, body.get('muted'))}
        else: raise PlatformError('NOT_FOUND', 'غير موجود', 404)
        return web.json_response({'ok': True, **result}, headers={'Cache-Control': 'private, no-store'})

    async def events(self, request):
        from social_platform import PlatformError
        user = await self.api._user(request)
        uid = user['id']
        if not await self.api.platform.allow_rate('personal-stream:' + uid, 30, 60):
            raise PlatformError('RATE_LIMIT', 'اتصالات كثيرة', 429)
        response = web.StreamResponse(headers={'Content-Type': 'text/event-stream', 'Cache-Control': 'private, no-store, no-transform', 'X-Accel-Buffering': 'no'})
        async with self.d.live.subscribe(uid, uid) as queue:
            await response.prepare(request)
            try:
                await response.write(b'data: {"type":"resync"}\n\n')
                while True:
                    try: event = await asyncio.wait_for(queue.get(), 15)
                    except TimeoutError: event = {'type': 'resync'}
                    if event.get('type') == 'closed': break
                    try: await self.api._user(request)
                    except PlatformError:
                        await response.write(b'data: {"type":"access_denied"}\n\n'); break
                    # Recheck authorization after queueing, including late blocks.
                    if event.get('peerId'):
                        try: await self.d.access(uid, event['peerId'])
                        except PlatformError: continue
                        if await self.d.get(self.d.key('direct-mute', uid, event['peerId']), False): event = {**event, 'notify': False}
                    await asyncio.wait_for(response.write(('data: ' + json.dumps(event) + '\n\n').encode()), 5)
            except (ConnectionError, TimeoutError, RuntimeError): pass
        return response

    def install(self, app):
        app.router.add_get('/api/direct/events', self.events)
        app.router.add_get('/api/direct/{op:inbox}', self.call)
        app.router.add_post('/api/direct/{op:link|redeem|device}', self.call)
        app.router.add_get('/api/direct/{user_id}/messages', self.call)
        app.router.add_post('/api/direct/{user_id}/{op:messages|read|mute}', self.call)
