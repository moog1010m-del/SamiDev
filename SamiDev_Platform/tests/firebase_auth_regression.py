"""Offline provider doubles + real HTTP and optional isolated PostgreSQL/Redis.
No Firebase credentials, live email, or production auth bypass are used.
"""
import asyncio
import json
import os
import secrets
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
os.environ['SAMIDEV_PLATFORM_PREFIX'] = 'fbtest' + secrets.token_hex(6)
os.environ['SAMIDEV_FIREBASE_AUTH'] = '0'
from firebase_identity import FirebaseIdentity, FirebaseFailure
from social_platform import PlatformService, PlatformHttp, PlatformError, public_user
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from firebase_admin import auth as sdk_auth


def claims(uid='firebase-a', **extra):
    return dict(uid=uid, email='player@example.test', email_verified=True,
                auth_time=int(time.time()), **extra)


def provider(service):
    service.firebase.enabled = True
    service.firebase.project = 'isolated-test'
    service.firebase.api_key = 'public-test-key'
    service.firebase.verify = AsyncMock(return_value=claims())
    service.firebase.session_valid = AsyncMock(return_value=True)


class VerifierTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.identity = FirebaseIdentity()
        self.identity.enabled = True
        self.identity.project = 'isolated-test'
        self.identity._app = object()
        self.identity._sdk = lambda: sdk_auth

    async def test_signature_verification_and_revocation_are_delegated_to_official_sdk(self):
        with patch.object(sdk_auth, 'verify_id_token', return_value=claims()) as verify:
            result = await self.identity.verify('x' * 120)
            verify.assert_called_once_with('x' * 120, app=self.identity._app, check_revoked=True)
            self.assertEqual(result['uid'], 'firebase-a')
        for error in (sdk_auth.InvalidIdTokenError('bad signature'), sdk_auth.RevokedIdTokenError('revoked')):
            with patch.object(sdk_auth, 'verify_id_token', side_effect=error):
                with self.assertRaises(FirebaseFailure) as caught:
                    await self.identity.verify('x' * 120)
                self.assertEqual(caught.exception.code, 'INVALID_ID_TOKEN')

    async def test_unverified_email_malformed_token_and_provider_outage(self):
        with self.assertRaises(FirebaseFailure):
            await self.identity.verify({'uid': 'forged'})
        unverified = claims(); unverified['email_verified'] = False
        with patch.object(sdk_auth, 'verify_id_token', return_value=unverified):
            with self.assertRaises(FirebaseFailure) as caught:
                await self.identity.verify('x' * 120)
            self.assertEqual(caught.exception.code, 'EMAIL_NOT_VERIFIED')
        with patch.object(sdk_auth, 'verify_id_token', side_effect=OSError('offline')):
            with self.assertRaises(FirebaseFailure) as caught:
                await self.identity.verify('x' * 120)
            self.assertEqual(caught.exception.status, 503)

    async def test_session_revocation_disabled_project_and_bounded_cache(self):
        stamp = int(time.time())
        user = SimpleNamespace(tokens_valid_after_timestamp=stamp * 1000, disabled=False, email_verified=True)
        with patch.object(sdk_auth, 'get_user', return_value=user) as get:
            self.assertTrue(await self.identity.session_valid('a', stamp, 'isolated-test'))
            self.assertTrue(await self.identity.session_valid('a', stamp, 'isolated-test'))
            self.assertEqual(get.call_count, 1)
            self.assertFalse(await self.identity.session_valid('a', stamp-1, 'isolated-test'))
            self.assertFalse(await self.identity.session_valid('a', stamp, 'other-project'))
            self.assertFalse(await self.identity.session_valid('a', None, 'isolated-test'))
            self.identity._users.clear(); user.disabled = True
            self.assertFalse(await self.identity.session_valid('a', stamp, 'isolated-test'))
            self.identity._users.clear(); user.disabled = False; user.email_verified = False
            self.assertFalse(await self.identity.session_valid('a', stamp, 'isolated-test'))


class HttpTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.service = PlatformService()
        self.old = await self.service.create_user('old_player', 'Original-password-123')
        self.old['coins'] = '1234'; self.old['role'] = 'moderator'
        self.old_session = await self.service.create_session(self.old['id'])
        provider(self.service)
        api = PlatformHttp(self.service, None)
        @web.middleware
        async def errors(request, handler):
            try: return await handler(request)
            except PlatformError as e:
                return web.json_response({'ok': False, 'error': e.code}, status=e.status)
        app = web.Application(middlewares=[errors])
        app.router.add_get('/api/auth/config', api.auth_config)
        app.router.add_post('/api/auth/firebase', api.firebase_exchange)
        app.router.add_post('/api/auth/register', api.register)
        app.router.add_post('/api/auth/login', api.login)
        app.router.add_post('/api/auth/logout', api.logout)
        app.router.add_get('/api/me', api.me)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

    async def exchange(self, **body):
        response = await self.client.post('/api/auth/firebase', json={'idToken': 'x'*120, **body})
        return response, await response.json()

    async def test_disabled_default_and_no_legacy_registration_when_enabled(self):
        self.assertEqual(FirebaseIdentity().config(), {'provider': 'local'})
        config = await (await self.client.get('/api/auth/config')).json()
        self.assertEqual(set(config), {'ok', 'provider', 'apiKey', 'projectId'})
        response = await self.client.post('/api/auth/register', json={})
        self.assertEqual(response.status, 409)
        self.service.firebase.enabled = False
        response = await self.client.post('/api/auth/login', json={'username':'old_player', 'password':'Original-password-123'})
        self.assertEqual(response.status, 200)

    async def test_new_verified_profile_and_repeated_exchange(self):
        response, data = await self.exchange()
        self.assertEqual(data['error'], 'PROFILE_SETUP_REQUIRED')
        response, data = await self.exchange(username='new_player', role='admin', coins=999999)
        self.assertEqual(response.status, 200)
        uid = data['user']['id']
        self.assertEqual(data['user']['role'], 'user')
        self.assertEqual(int((await self.service.get_user(uid))['coins']), 0)
        self.assertNotIn('firebaseEmail', data['user'])
        cookie = response.cookies['samidev_session']
        self.assertTrue(cookie['httponly']); self.assertEqual(cookie['samesite'], 'Lax')
        response, second = await self.exchange()
        self.assertEqual(second['user']['id'], uid)
        self.assertEqual(len(self.service.mem_users), 2)
        self.assertEqual((await self.service.get_user(uid))['passwordHash'], '')

    async def test_link_proof_preserves_identity_and_revokes_old_password_and_sessions(self):
        response, data = await self.exchange(legacyUsername='old_player', legacyPassword='wrong')
        self.assertEqual(response.status, 401)
        self.assertFalse(self.old.get('firebaseUid'))
        response, data = await self.exchange(username='old_player')
        self.assertEqual(data['error'], 'USERNAME_TAKEN')  # no auto-merge by username/email
        response, data = await self.exchange(legacyUsername='old_player', legacyPassword='Original-password-123')
        self.assertEqual(response.status, 200)
        self.assertEqual(data['user']['id'], self.old['id'])
        self.assertEqual(data['user']['role'], 'moderator')
        self.assertEqual(int((await self.service.get_user(self.old['id']))['coins']), 1234)
        response, repeated = await self.exchange(legacyUsername='old_player', legacyPassword='Original-password-123')
        self.assertEqual(response.status, 200)
        self.assertEqual(repeated['user']['id'], self.old['id'])
        self.assertEqual(len(self.service.mem_users), 1)
        self.assertIsNone(await self.service.resolve_session(self.old_session))
        with self.assertRaises(PlatformError) as caught:
            await self.service.authenticate('old_player', 'Original-password-123')
        self.assertEqual(caught.exception.code, 'AUTH_MIGRATED')
        self.service.firebase.enabled = False
        with self.assertRaises(PlatformError):
            await self.service.authenticate('old_player', 'Original-password-123')

    async def test_recent_proof_required_and_unverified_provider_rejected(self):
        stale = claims(); stale['auth_time'] -= 301
        self.service.firebase.verify.return_value = stale
        response, data = await self.exchange(legacyUsername='old_player', legacyPassword='Original-password-123')
        self.assertEqual(data['error'], 'REAUTH_REQUIRED')
        self.service.firebase.verify.side_effect = FirebaseFailure('EMAIL_NOT_VERIFIED', 'verify', 403)
        response, data = await self.exchange(username='new_player')
        self.assertEqual(response.status, 403)
        self.assertEqual(len(self.service.mem_users), 1)

    async def test_provider_outage_keeps_session_but_revocation_denies_access(self):
        response, data = await self.exchange(username='new_player')
        token = response.cookies['samidev_session'].value
        self.service.firebase.session_valid.side_effect = FirebaseFailure('AUTH_PROVIDER_UNAVAILABLE', 'offline', 503)
        response = await self.client.get('/api/me')
        self.assertEqual(response.status, 503)
        self.assertIn(self.service.token_key(token), self.service.mem_sessions)
        self.service.firebase.session_valid.side_effect = None
        self.service.firebase.session_valid.return_value = False
        response = await self.client.get('/api/me')
        self.assertEqual(response.status, 401)
        response = await self.client.post('/api/auth/logout')
        self.assertEqual(response.status, 200)
        self.assertNotIn(self.service.token_key(token), self.service.mem_sessions)


@unittest.skipUnless(os.getenv('SAMIDEV_TEST_DATABASE_URL') and os.getenv('SAMIDEV_TEST_REDIS_URL'), 'real test database/Redis URLs required')
class PostgresTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        import redis.asyncio as redis
        from postgres_platform import PostgresPlatformService
        self.redis = redis.from_url(os.environ['SAMIDEV_TEST_REDIS_URL'], decode_responses=True)
        self.services = [PostgresPlatformService(os.environ['SAMIDEV_TEST_DATABASE_URL'], self.redis) for _ in range(2)]
        for service in self.services:
            provider(service)
            await service.start()

    async def asyncTearDown(self):
        prefix = os.environ['SAMIDEV_PLATFORM_PREFIX']
        async with self.services[0].r.pool.acquire() as conn:
            await conn.execute('DELETE FROM samidev_social_documents WHERE key LIKE $1', prefix + ':%')
        for service in self.services: await service.close()
        async for key in self.redis.scan_iter(match=prefix + ':*'): await self.redis.delete(key)
        await self.redis.aclose()

    async def test_atomic_mapping_preserved_inventory_and_durability(self):
        a, b = self.services
        results = await asyncio.gather(*(self.services[i%2].firebase_account(claims(), username='racer') for i in range(16)))
        self.assertEqual(len({r['id'] for r in results}), 1)
        uid = results[0]['id']
        self.assertEqual(await b.r.get(b.k_firebase('firebase-a')), uid)
        self.assertIsNone(await self.redis.get(b.k_firebase('firebase-a')))
        old = await a.create_user('existing', 'Original-password-123', role='moderator')
        await a.r.hset(a.k_user(old['id']), mapping={'coins':'1000', 'wins':'17'})
        await a.buy_store_item(old['id'], 'badge_shard')
        bound = await b.firebase_account(claims('second-identity'), legacy_uid=old['id'])
        self.assertEqual((bound['id'], bound['coins'], bound['wins'], bound['role']), (old['id'], '850', '17', 'moderator'))
        self.assertIn('badge_shard', (await a.store_snapshot(old['id']))['inventory'])
        # Two different identities racing to link one account: exactly one wins.
        target = await a.create_user('target', 'Original-password-123')
        race = await asyncio.gather(a.firebase_account(claims('c'), legacy_uid=target['id']), b.firebase_account(claims('d'), legacy_uid=target['id']), return_exceptions=True)
        self.assertEqual(sum(isinstance(x, dict) for x in race), 1)
        self.assertEqual(sum(isinstance(x, PlatformError) for x in race), 1)
        await a.close(); await a.start()
        async for key in self.redis.scan_iter(match=os.environ['SAMIDEV_PLATFORM_PREFIX'] + ':*'): await self.redis.delete(key)
        self.assertEqual((await a.firebase_account(claims()))['id'], uid)
        self.assertEqual((await b.firebase_account(claims('second-identity')))['coins'], '850')


if __name__ == '__main__': unittest.main(verbosity=2)
