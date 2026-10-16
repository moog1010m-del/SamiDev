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
    service.firebase.admin_uid = ''
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

    async def test_account_controls_use_official_sdk_and_delete_is_idempotent(self):
        user = SimpleNamespace(email='private@example.test', provider_data=[SimpleNamespace(provider_id='google.com')])
        with patch.object(sdk_auth, 'get_user', return_value=user) as get:
            self.assertEqual(await self.identity.account_info('official-uid'), {'email':'private@example.test','providers':['google.com']})
            get.assert_called_once_with('official-uid', app=self.identity._app)
        with patch.object(sdk_auth, 'revoke_refresh_tokens') as revoke:
            await self.identity.revoke_sessions('official-uid')
            revoke.assert_called_once_with('official-uid', app=self.identity._app)
        with patch.object(sdk_auth, 'delete_user') as delete:
            await self.identity.delete_user('official-uid')
            delete.assert_called_once_with('official-uid', app=self.identity._app)
        with patch.object(sdk_auth, 'delete_user', side_effect=sdk_auth.UserNotFoundError('already removed')):
            await self.identity.delete_user('official-uid')

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
        app.router.add_get('/api/admin/users', api.admin_users)
        self.client = TestClient(TestServer(app))
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()

    async def exchange(self, **body):
        response = await self.client.post('/api/auth/firebase', json={'idToken': 'x'*120, **body})
        return response, await response.json()

    async def test_local_login_registration_and_sessions_disabled_when_firebase_enabled(self):
        self.assertEqual(FirebaseIdentity().config(), {'provider': 'local'})
        config = await (await self.client.get('/api/auth/config')).json()
        self.assertEqual(set(config), {'ok', 'provider', 'apiKey', 'projectId', 'authDomain', 'googleClientId', 'googleIosClientId'})
        response = await self.client.post('/api/auth/register', json={})
        self.assertEqual(response.status, 409)
        response = await self.client.post('/api/auth/login', json={'username':'old_player', 'password':'Original-password-123'})
        self.assertEqual(response.status, 409)
        self.assertIsNone(await self.service.resolve_session(self.old_session))
        self.service.firebase.enabled = False
        self.assertIsNotNone(await self.service.resolve_session(self.old_session))
        response = await self.client.post('/api/auth/login', json={'username':'old_player', 'password':'Original-password-123'})
        self.assertEqual(response.status, 200)

    async def test_new_verified_profile_and_repeated_exchange(self):
        response, data = await self.exchange()
        self.assertEqual(response.status, 200)
        self.assertRegex(data['user']['username'], r'^Player_[a-f0-9]{10}$')
        self.assertTrue(data['user']['freeRenameAvailable'])
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

    async def test_automatic_guest_link_keeps_name_progress_and_free_rename_after_restore(self):
        guest=await self.service.accounts.guest();guest['coins']='321'
        token=await self.service.create_session(guest['id'])
        self.client.session.cookie_jar.update_cookies({'samidev_session':token})
        response,data=await self.exchange(linkGuest=True)
        self.assertEqual(response.status,200)
        self.assertEqual(data['user']['id'],guest['id'])
        self.assertEqual(data['user']['username'],guest['username'])
        self.assertEqual(int((await self.service.get_user(guest['id']))['coins']),321)
        self.assertTrue(data['user']['freeRenameAvailable'])
        for _ in range(2):
            restored=await (await self.client.get('/api/me')).json()
            self.assertEqual(restored['user']['id'],guest['id'])
            self.assertFalse(restored['user']['isGuest'])
        renamed=await self.service.accounts.rename(guest['id'],'Chosen_later')
        self.assertEqual(renamed['freeRenameUsed'],'1')

    async def test_existing_identity_switches_from_guest_without_merging_or_resetting_rename(self):
        saved=await self.service.firebase_account(claims(),username='Saved_player')
        saved['coins']='456';saved['freeRenameUsed']='1'
        guest=await self.service.accounts.guest();guest['coins']='999'
        token=await self.service.create_session(guest['id'])
        self.client.session.cookie_jar.update_cookies({'samidev_session':token})
        response,data=await self.exchange(linkGuest=True,username='old_player')
        self.assertEqual(response.status,200)
        self.assertEqual(data['user']['id'],saved['id'])
        self.assertEqual(int((await self.service.get_user(saved['id']))['coins']),456)
        self.assertFalse(data['user']['freeRenameAvailable'])
        self.assertEqual(guest['guest'],'1');self.assertNotIn('firebaseUid',guest)

    async def test_account_linking_is_rejected_without_mutating_old_test_data(self):
        before = dict(self.old)
        response, data = await self.exchange(legacyUsername='old_player', legacyPassword='Original-password-123', username='new_player')
        self.assertEqual(response.status, 400)
        self.assertEqual(data['error'], 'ACCOUNT_LINKING_DISABLED')
        self.assertEqual(self.old, before)
        response, data = await self.exchange(username='old_player')
        self.assertEqual(data['error'], 'USERNAME_TAKEN')
        self.assertEqual(len(self.service.mem_users), 1)
        self.assertFalse(self.service.mem_firebase)

    async def test_admin_bootstrap_only_from_configured_verified_uid(self):
        self.service.firebase.admin_uid = 'trusted-admin'
        response, data = await self.exchange(username='regular_player', role='admin', firebaseUid='trusted-admin')
        self.assertEqual(data['user']['role'], 'user')
        self.service.firebase.verify.return_value = claims('trusted-admin')
        response, data = await self.exchange(username='trusted_admin')
        self.assertEqual(data['user']['role'], 'admin')
        self.assertEqual((await (await self.client.get('/api/auth/config')).json()).get('adminUid'), None)
        self.service.firebase.admin_uid = 'firebase-a'
        self.service.firebase.verify.return_value = claims()
        response, data = await self.exchange()
        self.assertEqual(data['user']['role'], 'admin')

    async def test_second_google_identity_cannot_claim_admin_name_or_session(self):
        self.service.firebase.admin_uid = 'admin-google'
        self.service.firebase.verify.return_value = claims('admin-google')
        response, data = await self.exchange(username='Incident_Admin')
        self.assertEqual(response.status, 200)
        original = dict(await self.service.get_user(data['user']['id']))
        admin_cookie = response.cookies['samidev_session'].value
        self.service.firebase.verify.return_value = claims('other-google')
        for name in ['Incident_Admin', 'incident_admin', 'INCIDENT_ADMIN']:
            response, rejected = await self.exchange(username=name, role='admin', firebaseUid='admin-google')
            self.assertEqual(response.status, 409)
            self.assertEqual(rejected['error'], 'USERNAME_TAKEN')
            self.assertNotIn('samidev_session', response.cookies)
        guest = await self.service.accounts.guest()
        with self.assertRaises(PlatformError) as collision:
            await self.service.accounts.link(guest['id'], claims('other-google'), 'incident_admin')
        self.assertEqual(collision.exception.code, 'USERNAME_TAKEN')
        self.assertEqual((await self.service.get_user(guest['id']))['guest'], '1')
        self.assertEqual(await self.service.get_user(original['id']), original)
        self.assertEqual((await self.service.resolve_session(admin_cookie))['id'], original['id'])
        response, other = await self.exchange(username='Other_Account')
        self.assertEqual(response.status, 200)
        self.assertNotEqual(other['user']['id'], original['id'])
        self.assertEqual(other['user']['role'], 'user')
        denied = await self.client.get('/api/admin/users')
        self.assertEqual(denied.status, 403)
        self.assertEqual((await (await self.client.get('/api/admin/users')).json())['error'], 'ADMIN_REQUIRED')
        self.assertEqual((await (await self.client.get('/api/me')).json())['user']['id'], other['user']['id'])
        # An already linked Google identity cannot select a different player by name.
        response, again = await self.exchange(username='Incident_Admin')
        self.assertEqual(again['user']['id'], other['user']['id'])
        self.assertEqual(again['user']['role'], 'user')
        self.assertEqual(await self.service.get_user(original['id']), original)

    async def test_inconsistent_identity_mapping_fails_without_issuing_session(self):
        admin = await self.service.firebase_account(claims('trusted-admin'), username='Protected_Admin')
        admin['role'] = 'admin'
        self.service.mem_firebase[(self.service.firebase.project, 'firebase-a')] = admin['id']
        response, data = await self.exchange(username='Protected_Admin')
        self.assertEqual(response.status, 409)
        self.assertEqual(data['error'], 'IDENTITY_CONFLICT')
        self.assertNotIn('samidev_session', response.cookies)
        self.assertEqual(admin['firebaseUid'], 'trusted-admin')

    async def test_exchange_rechecks_identity_before_creating_session(self):
        with patch.object(self.service, 'firebase_account', AsyncMock(return_value=self.old)):
            response, data = await self.exchange(username='old_player')
        self.assertEqual(response.status, 409)
        self.assertEqual(data['error'], 'IDENTITY_CONFLICT')
        self.assertNotIn('samidev_session', response.cookies)

    async def test_auth_audit_contains_no_credentials_or_email(self):
        with self.assertLogs('samidev.auth', level='INFO') as records:
            response, data = await self.exchange(username='audit_player')
        self.assertEqual(response.status, 200)
        entry = json.loads(records.records[-1].getMessage())
        self.assertEqual(entry['result'], 'accepted')
        self.assertEqual(entry['accountId'], data['user']['id'])
        self.assertEqual(entry['role'], 'user')
        self.assertEqual(entry['store'], 'memory')
        for secret in ['x' * 120, 'player@example.test', 'firebase-a', 'samidev_session']:
            self.assertNotIn(secret, records.records[-1].getMessage())
        self.assertEqual(set(entry), {'event','at','attemptId','instance','store','identityHash','linkGuest','result','accountId','role'})

    async def test_memory_restart_can_reuse_name_but_cannot_inherit_admin_identity(self):
        self.service.firebase.admin_uid = 'trusted-admin'
        original = await self.service.firebase_account(claims('trusted-admin'), username='Restart_Admin')
        restarted = PlatformService()
        provider(restarted)
        restarted.firebase.admin_uid = 'trusted-admin'
        recreated = await restarted.firebase_account(claims('new-google'), username='Restart_Admin')
        self.assertEqual(original['role'], 'admin')
        self.assertEqual(recreated['role'], 'user')
        self.assertNotEqual(recreated['id'], original['id'])
        self.assertNotEqual(recreated['firebaseUid'], original['firebaseUid'])

    async def test_unverified_provider_rejected_before_profile_creation(self):
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

    async def test_admin_name_isolation_across_gateways_and_guest_upgrade(self):
        a, b = self.services
        a.firebase.admin_uid = 'incident-admin'
        admin = await a.firebase_account(claims('incident-admin'), username='Protected_Admin')
        before = dict(await b.get_user(admin['id']))
        outsider = claims('incident-outsider')
        for name in ['Protected_Admin','protected_admin','PROTECTED_ADMIN']:
            with self.assertRaises(PlatformError) as failure:
                await b.firebase_account(outsider, username=name)
            self.assertEqual(failure.exception.code, 'USERNAME_TAKEN')
        guest = await b.accounts.guest()
        with self.assertRaises(PlatformError) as failure:
            await b.accounts.link(guest['id'], outsider, 'protected_admin')
        self.assertEqual(failure.exception.code, 'USERNAME_TAKEN')
        self.assertEqual(await a.get_user(admin['id']), before)
        self.assertTrue((await b.get_user(guest['id']))['guest'] == '1')
        self.assertIsNone(await a.r.get(a.k_firebase('incident-outsider')))
        other = await b.accounts.link(guest['id'], outsider, 'Independent_User')
        self.assertNotEqual(other['id'], admin['id'])
        self.assertEqual(other['role'], 'user')
        self.assertEqual((await a.firebase_account(outsider, username='Protected_Admin'))['id'], other['id'])
        self.assertEqual(await a.get_user(admin['id']), before)

    async def test_atomic_mapping_preserved_inventory_and_durability(self):
        a, b = self.services
        results = await asyncio.gather(*(self.services[i%2].firebase_account(claims(), username='racer') for i in range(16)))
        self.assertEqual(len({r['id'] for r in results}), 1)
        uid = results[0]['id']
        self.assertEqual(await b.r.get(b.k_firebase('firebase-a')), uid)
        self.assertIsNone(await self.redis.get(b.k_firebase('firebase-a')))
        await a.r.hset(a.k_user(uid), mapping={'coins':'1000'})
        await a.buy_store_item(uid, 'badge_shard')
        # Two new identities racing for one username: exactly one succeeds.
        race = await asyncio.gather(a.firebase_account(claims('c'), username='target'), b.firebase_account(claims('d'), username='target'), return_exceptions=True)
        self.assertEqual(sum(isinstance(x, dict) for x in race), 1)
        self.assertEqual([x.code for x in race if isinstance(x, PlatformError)], ['USERNAME_TAKEN'])
        b.firebase.admin_uid = 'firebase-a'
        self.assertEqual((await b.firebase_account(claims()))['role'], 'admin')
        await a.close(); await a.start()
        async for key in self.redis.scan_iter(match=os.environ['SAMIDEV_PLATFORM_PREFIX'] + ':*'): await self.redis.delete(key)
        restored = await a.firebase_account(claims())
        self.assertEqual((restored['id'], restored['coins'], restored['role']), (uid, '850', 'admin'))
        self.assertIn('badge_shard', (await a.store_snapshot(uid))['inventory'])

    async def test_automatic_guest_exchange_is_idempotent_across_gateways(self):
        from aiohttp import DummyCookieJar
        a,b=self.services
        guest=await a.accounts.guest()
        await a.r.hset(a.k_user(guest['id']),mapping={'coins':'987'})
        token=await a.create_session(guest['id'])
        clients=[]
        @web.middleware
        async def errors(request,handler):
            try:return await handler(request)
            except PlatformError as e:return web.json_response({'error':e.code},status=e.status)
        try:
            for service in self.services:
                app=web.Application(middlewares=[errors])
                app.router.add_post('/api/auth/firebase',PlatformHttp(service,None).firebase_exchange)
                client=TestClient(TestServer(app),cookie_jar=DummyCookieJar())
                await client.start_server();clients.append(client)
            async def exchange(i):
                response=await clients[i%2].post('/api/auth/firebase',json={'idToken':'x'*120,'linkGuest':True},headers={'Cookie':'samidev_session='+token})
                data=await response.json()
                self.assertEqual(response.status,200,data)
                self.assertTrue(data['user']['freeRenameAvailable'])
                self.assertEqual(data['user']['username'],guest['username'])
                return data['user']['id']
            ids=await asyncio.gather(*(exchange(i) for i in range(12)))
            self.assertEqual(set(ids),{guest['id']})
            self.assertEqual((await b.get_user(guest['id']))['coins'],'987')
        finally:
            for client in clients:await client.close()

    async def test_automatic_names_are_unique_and_identity_creation_is_atomic_across_gateways(self):
        a,b=self.services
        profiles=await asyncio.gather(*(self.services[i%2].firebase_account(claims('auto-'+str(i))) for i in range(12)))
        self.assertEqual(len({p['usernameLower'] for p in profiles}),12)
        self.assertTrue(all(p['username'].startswith('Player_') for p in profiles))
        repeated=await asyncio.gather(*(self.services[i%2].firebase_account(claims('same-auto')) for i in range(12)))
        self.assertEqual(len({p['id'] for p in repeated}),1)
        self.assertEqual(len({p['username'] for p in repeated}),1)
        self.assertTrue(public_user(repeated[0])['freeRenameAvailable'])


if __name__ == '__main__': unittest.main(verbosity=2)
