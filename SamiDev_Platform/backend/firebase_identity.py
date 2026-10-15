"""Firebase identity verification only. Gameplay and durable profiles stay local."""
import asyncio
import os
import time
import threading


class FirebaseFailure(Exception):
    def __init__(self, code, message, status=401):
        self.code, self.message, self.status = code, message, status
        super().__init__(message)


class FirebaseIdentity:
    def __init__(self):
        self.enabled = os.getenv('SAMIDEV_FIREBASE_AUTH', '0') == '1'
        self.project = os.getenv('SAMIDEV_FIREBASE_PROJECT_ID', '').strip()
        self.api_key = os.getenv('SAMIDEV_FIREBASE_API_KEY', '').strip()
        # Server-only bootstrap identity; never accept a role from client input.
        self.admin_uid = os.getenv('SAMIDEV_FIREBASE_ADMIN_UID', '').strip()
        self._app = None
        self._init_lock = threading.Lock()
        self._slots = asyncio.Semaphore(16)
        self._users = {}
        if self.enabled and (not self.project or not self.api_key):
            raise RuntimeError('Firebase auth requires project ID and public API key')

    def config(self):
        return {'provider': 'firebase' if self.enabled else 'local',
                **({'apiKey': self.api_key, 'projectId': self.project} if self.enabled else {})}

    def _sdk(self):
        import firebase_admin
        from firebase_admin import auth
        with self._init_lock:
            if self._app is None:
                name = 'samidev-' + self.project
                try:
                    self._app = firebase_admin.get_app(name)
                except ValueError:
                    self._app = firebase_admin.initialize_app(options={
                        'projectId': self.project, 'httpTimeout': 10}, name=name)
        return auth

    async def _work(self, callback):
        try:
            await asyncio.wait_for(self._slots.acquire(), 3)
            task = asyncio.create_task(asyncio.to_thread(callback))
            def completed(done):
                self._slots.release()
                # A timed-out request leaves its bounded worker running until the
                # SDK finishes. Retrieve late errors without logging token data.
                if not done.cancelled():
                    done.exception()
            task.add_done_callback(completed)
            return await asyncio.wait_for(asyncio.shield(task), 15)
        except FirebaseFailure:
            raise
        except Exception:
            raise FirebaseFailure('AUTH_PROVIDER_UNAVAILABLE', 'خدمة تسجيل الدخول غير متاحة مؤقتًا. حاول لاحقًا.', 503) from None

    async def verify(self, token):
        if not self.enabled:
            raise FirebaseFailure('AUTH_PROVIDER_DISABLED', 'Firebase غير مفعّل على هذا الخادم.', 503)
        if not isinstance(token, str) or not 100 <= len(token) <= 16384:
            raise FirebaseFailure('INVALID_ID_TOKEN', 'جلسة Firebase غير صالحة. سجّل الدخول مجددًا.')
        def check():
            auth = self._sdk()
            try:
                claims = auth.verify_id_token(token, app=self._app, check_revoked=True)
            except (auth.InvalidIdTokenError, auth.ExpiredIdTokenError, auth.RevokedIdTokenError,
                    auth.UserDisabledError, auth.UserNotFoundError, ValueError):
                raise FirebaseFailure('INVALID_ID_TOKEN', 'انتهت جلسة Firebase أو أُلغيت. سجّل الدخول مجددًا.') from None
            if claims.get('email_verified') is not True or not claims.get('email'):
                raise FirebaseFailure('EMAIL_NOT_VERIFIED', 'وثّق بريدك الإلكتروني ثم حاول مجددًا.', 403)
            if not isinstance(claims.get('uid'), str) or not 1 <= len(claims['uid']) <= 128:
                raise FirebaseFailure('INVALID_ID_TOKEN', 'هوية Firebase غير صالحة.')
            auth_time = claims.get('auth_time')
            if not isinstance(auth_time, int) or auth_time <= 0 or auth_time > time.time() + 60:
                raise FirebaseFailure('INVALID_ID_TOKEN', 'وقت المصادقة غير صالح.')
            return claims
        return await self._work(check)

    async def session_valid(self, uid, auth_time, project):
        if not self.enabled or project != self.project or not isinstance(auth_time, int):
            return False
        cached = self._users.get(uid)
        if cached and cached[0] > time.monotonic():
            valid_after, enabled = cached[1:]
        else:
            def lookup():
                auth = self._sdk()
                try:
                    user = auth.get_user(uid, app=self._app)
                except auth.UserNotFoundError:
                    return 0, False
                return user.tokens_valid_after_timestamp / 1000, not user.disabled and user.email_verified
            valid_after, enabled = await self._work(lookup)
            if len(self._users) >= 10000:
                self._users = {key: value for key, value in self._users.items() if value[0] > time.monotonic()}
                if len(self._users) >= 10000:
                    self._users.pop(next(iter(self._users)))
            self._users[uid] = (time.monotonic() + 30, valid_after, enabled)
        return enabled and auth_time >= valid_after
