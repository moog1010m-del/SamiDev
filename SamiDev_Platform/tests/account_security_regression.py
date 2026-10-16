"""Real HTTP account controls, provider doubles, memory + real PostgreSQL/Redis."""
import asyncio
import json
import os
import secrets
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
os.environ['SAMIDEV_PLATFORM_PREFIX'] = 'securitytest' + secrets.token_hex(6)
os.environ['SAMIDEV_FIREBASE_AUTH'] = '0'
from social_platform import PlatformService, PlatformHttp, PlatformError, PREFIX
from firebase_identity import FirebaseFailure
from account_security import AccountSecurityHttp, device_metadata
from aiohttp import web, DummyCookieJar
from aiohttp.test_utils import TestClient, TestServer, make_mocked_request


def identity(uid='a', **overrides):
    return {**dict(uid=uid, email=f'{uid}@example.test', email_verified=True, auth_time=int(time.time())), **overrides}


def provider(service):
    service.firebase.enabled = True
    service.firebase.project = 'isolated-security-test'
    service.firebase.verify = AsyncMock(return_value=identity())
    service.firebase.session_valid = AsyncMock(return_value=True)
    service.firebase.account_info = AsyncMock(return_value={'email':'a@example.test','providers':['password','google.com']})
    service.firebase.delete_user = AsyncMock()
    service.firebase.revoke_sessions = AsyncMock()


class SecurityScenarios:
    async def asyncSetUp(self):
        self.service = await self.new_service()
        provider(self.service)
        self.user = await self.service.firebase_account(identity(), username='Player_A')
        self.other = await self.service.firebase_account(identity('b'), username='Player_B')
        self.first = await self.service.create_session(self.user['id'], firebase_auth_time=int(time.time()), metadata={'device':'iPhone','client':'تطبيق SamiDev','country':'SA'})
        self.second = await self.service.create_session(self.user['id'], firebase_auth_time=int(time.time()), metadata={'device':'Windows','client':'Chrome','country':''})
        self.other_token = await self.service.create_session(self.other['id'], firebase_auth_time=int(time.time()))
        api = PlatformHttp(self.service, None)
        @web.middleware
        async def errors(request, handler):
            try:
                return await handler(request)
            except PlatformError as e:
                return web.json_response({'ok':False,'error':e.code,'message':e.message},status=e.status)
        app = web.Application(middlewares=[errors])
        AccountSecurityHttp(api).install(app.router)
        app.router.add_get('/api/me',api.me)
        app.router.add_post('/api/auth/firebase',api.firebase_exchange)
        app.router.add_post('/api/auth/login',api.login)
        self.client = TestClient(TestServer(app), cookie_jar=DummyCookieJar())
        await self.client.start_server()

    async def asyncTearDown(self):
        await self.client.close()
        await self.close_service()

    async def req(self, method, path, token=None, body=None):
        response = await self.client.request(method,path,headers={'Cookie':f'samidev_session={token}'} if token else {},json=body)
        return response, await response.json()

    async def test_private_devices_and_account_require_session(self):
        for method,path in [('GET','/api/account'),('GET','/api/account/devices'),('DELETE','/api/account/devices/x'),('POST','/api/account/logout-all'),('POST','/api/account/delete')]:
            response,_=await self.req(method,path)
            self.assertEqual(response.status,401)

    async def test_devices_are_owned_and_do_not_expose_session_credentials(self):
        response,data=await self.req('GET','/api/account/devices',self.first)
        self.assertEqual(response.status,200)
        self.assertEqual(len(data['devices']),2)
        current=next(d for d in data['devices'] if d['current'])
        self.assertEqual(current['device'],'iPhone')
        self.assertEqual(current['country'],'SA')
        self.assertEqual(response.headers['Cache-Control'],'private, no-store')
        raw=json.dumps(data)
        for secret in [self.first,self.service.token_key(self.first),'sessionHash','firebaseAuthTime','a@example.test']:
            self.assertNotIn(secret,raw)
        self.assertTrue(await self.service.resolve_session(self.second))

    async def test_revoke_one_device_preserves_another_and_rejects_game_ticket(self):
        _,data=await self.req('GET','/api/account/devices',self.first)
        target=next(d for d in data['devices'] if not d['current'])
        ticket=await self.service.issue_game_ticket(self.user,session_token=self.second)
        response,result=await self.req('DELETE','/api/account/devices/'+target['id'],self.first)
        self.assertEqual(response.status,200);self.assertFalse(result['signedOut'])
        self.assertTrue(await self.service.resolve_session(self.first))
        self.assertIsNone(await self.service.resolve_session(self.second))
        self.assertIsNone(await self.service.consume_game_ticket(ticket['ticket']))

    async def test_cross_account_device_revocation_is_denied(self):
        _,data=await self.req('GET','/api/account/devices',self.other_token)
        response,_=await self.req('DELETE','/api/account/devices/'+data['devices'][0]['id'],self.first)
        self.assertEqual(response.status,404)
        self.assertTrue(await self.service.resolve_session(self.other_token))

    async def test_current_device_revoke_clears_cookie(self):
        _,data=await self.req('GET','/api/account/devices',self.first)
        current=next(d for d in data['devices'] if d['current'])
        response,result=await self.req('DELETE','/api/account/devices/'+current['id'],self.first)
        self.assertTrue(result['signedOut']);self.assertEqual(response.cookies['samidev_session']['max-age'],'0')
        self.assertIsNone(await self.service.resolve_session(self.first))
        self.assertTrue(await self.service.resolve_session(self.second))

    async def test_global_logout_invalidates_all_including_legacy_sessions(self):
        key=self.service.token_key(self.second)
        # Remove registry entry to simulate a cookie from the previous release.
        async with self.service.security.transaction(self.user['id']):
            rows=await self.service.security.records(self.user['id'])
            await self.service.security.save(self.user['id'],{k:v for k,v in rows.items() if v['sessionHash']!=key})
        response,result=await self.req('POST','/api/account/logout-all',self.first,{})
        self.assertEqual(response.status,200);self.assertTrue(result['signedOut'])
        self.assertIsNone(await self.service.resolve_session(self.first))
        self.assertIsNone(await self.service.resolve_session(self.second))
        self.assertTrue(await self.service.resolve_session(self.other_token))
        self.service.firebase.revoke_sessions.assert_awaited_once_with('a')

    async def test_revocation_outage_is_reported_without_false_success(self):
        self.service.firebase.revoke_sessions.side_effect = FirebaseFailure('AUTH_PROVIDER_UNAVAILABLE','offline',503)
        response,_ = await self.req('POST','/api/account/logout-all',self.first,{})
        self.assertEqual(response.status,503)
        self.assertTrue(await self.service.resolve_session(self.first))

    async def test_identity_binding_and_revoked_session_cannot_be_resurrected_by_touch(self):
        key=self.service.token_key(self.first)
        raw=json.loads(await self.service.security.raw(key))
        self.assertEqual(raw['firebaseUid'],'a')
        await self.service.delete_session(self.first)
        await self.service.security.touch(key)
        self.assertIsNone(await self.service.resolve_session(self.first))
        # A pre-fix cookie without an explicit identity binding requires login.
        second_key=self.service.token_key(self.second)
        data=json.loads(await self.service.security.raw(second_key));data.pop('firebaseUid')
        if self.service.r is None:
            self.service.mem_sessions[second_key].value=json.dumps(data)
        else:
            await self.service.r.set(self.service.k_session(second_key),json.dumps(data),ex=3600)
        self.assertIsNone(await self.service.resolve_session(self.second))

    async def test_logged_out_records_do_not_exhaust_device_limit(self):
        for _ in range(42):
            token=await self.service.create_session(self.user['id'],firebase_auth_time=int(time.time()))
            await self.service.delete_session(token)
        _,data=await self.req('GET','/api/account/devices',self.first)
        self.assertEqual(len(data['devices']),2)

    async def test_account_info_private_and_public_profile_has_no_email(self):
        _,info=await self.req('GET','/api/account',self.first)
        self.assertEqual(info['email'],'a@example.test')
        self.assertEqual(info['providers'],['password','google.com'])
        _,me=await self.req('GET','/api/me',self.first)
        self.assertNotIn('a@example.test',json.dumps(me))
        self.assertNotIn('firebaseUid',json.dumps(me))

    async def test_expired_guest_link_never_silently_creates_independent_account(self):
        self.service.firebase.verify.return_value=identity('new-guest-link')
        response,data=await self.req('POST','/api/auth/firebase',None,{'idToken':'x'*120,'username':'Lost_guest','linkGuest':True})
        self.assertEqual(response.status,409);self.assertEqual(data['error'],'GUEST_SESSION_EXPIRED')
        self.assertIsNone(await self.service.find_user_by_username('Lost_guest'))

    async def test_no_email_or_username_admin_grants_and_local_login_stays_disabled(self):
        self.service.firebase.verify.return_value=identity('outsider',email='owner@example.test')
        with patch.dict(os.environ,{'SAMIDEV_ADMIN_EMAIL':'owner@example.test'}):
            response,data=await self.req('POST','/api/auth/firebase',None,{'idToken':'x'*120,'username':'DeV','role':'admin'})
        self.assertEqual(response.status,200);self.assertEqual(data['user']['role'],'user')
        response,_=await self.req('POST','/api/auth/login',None,{'username':'DeV','password':'anything'})
        self.assertEqual(response.status,409)

    async def test_delete_rejects_missing_confirm_wrong_identity_and_stale_proof(self):
        for proof,body,status in [(identity(),{},400),(identity('b'),{'confirm':'DELETE','idToken':'x'*120},403),(identity(auth_time=int(time.time())-600),{'confirm':'DELETE','idToken':'x'*120},403)]:
            self.service.firebase.verify.return_value=proof
            response,_=await self.req('POST','/api/account/delete',self.first,body)
            self.assertEqual(response.status,status)
        self.service.firebase.delete_user.assert_not_awaited()
        self.assertTrue(await self.service.resolve_session(self.first))

    async def test_delete_removes_local_and_provider_data_and_keeps_other_account(self):
        await self.service.send_friend_request(self.user,self.other['username'])
        await self.service.respond_friend_request(self.other,self.user['id'],True)
        await self.service.grant_store_item(self.user['id'],'badge_ember')
        await self.service.append_community_chat(self.user['id'],'majlis','to erase')
        await self.service.append_community_chat(self.other['id'],'majlis','keep this')
        await self.service.record_game_result(self.user['id'],'pool','delete-test-match',won=True)
        response,data=await self.req('POST','/api/account/delete',self.first,{'confirm':'DELETE','idToken':'x'*120})
        self.assertEqual(response.status,200);self.assertTrue(data['deleted'])
        self.service.firebase.delete_user.assert_awaited_once_with('a')
        self.assertIsNone(await self.service.get_user(self.user['id']))
        self.assertIsNone(await self.service.find_user_by_username('Player_A'))
        self.assertIsNone(await self.service.resolve_session(self.second))
        self.assertTrue(await self.service.resolve_session(self.other_token))
        self.assertEqual((await self.service.social_state(self.other))['friends'],[])
        history=await self.service.community_chat_history('majlis')
        self.assertEqual([r['text'] for r in history],['keep this'])
        self.assertEqual(await self.service.deletions.pending(),[])
        if self.service.r is not None:
            async with self.service.r.pool.acquire() as conn:
                count=await conn.fetchval('SELECT count(*) FROM samidev_match_results WHERE account_key=$1',self.service.k_user(self.user['id']))
            self.assertEqual(count,0)

    async def test_provider_outage_persists_delete_job_and_blocks_sessions_until_retry(self):
        self.service.firebase.delete_user.side_effect=FirebaseFailure('AUTH_PROVIDER_UNAVAILABLE','offline',503)
        response,data=await self.req('POST','/api/account/delete',self.first,{'confirm':'DELETE','idToken':'x'*120})
        self.assertEqual(response.status,202);self.assertTrue(data['pending'])
        self.assertIn(self.user['id'],await self.service.deletions.pending())
        self.assertIsNone(await self.service.resolve_session(self.first))
        self.assertIsNone(await self.service.resolve_session(self.second))
        self.service.firebase.delete_user.side_effect=None
        self.assertTrue(await self.service.deletions.process(self.user['id']))
        self.assertEqual(await self.service.deletions.pending(),[])

    async def test_public_verified_deletion_works_for_banned_owner_without_app_session(self):
        await self.service.set_banned(self.user['id'],True)
        response,data=await self.req('POST','/api/account/delete',None,{'confirm':'DELETE','idToken':'x'*120,'username':'Player_B','userId':self.other['id']})
        self.assertEqual(response.status,200);self.assertTrue(data['deleted'])
        self.assertIsNone(await self.service.get_user(self.user['id']))
        self.assertTrue(await self.service.resolve_session(self.other_token))
        self.service.firebase.delete_user.assert_awaited_once_with('a')

    async def test_public_delete_proof_cannot_create_an_account_or_use_stale_identity(self):
        self.service.firebase.verify.return_value=identity(auth_time=int(time.time())-600)
        response,_=await self.req('POST','/api/account/delete',None,{'confirm':'DELETE','idToken':'x'*120})
        self.assertEqual(response.status,403)
        self.service.firebase.verify.return_value=identity('no-profile')
        response,_=await self.req('POST','/api/account/delete',None,{'confirm':'DELETE','idToken':'x'*120,'username':'Player_A'})
        self.assertEqual(response.status,404)
        self.service.firebase.delete_user.assert_not_awaited()

    async def test_public_preview_names_verified_account_without_creating_session_or_deleting(self):
        response,data=await self.req('POST','/api/account/deletion-preview',None,{'idToken':'x'*120,'username':'Player_B','userId':self.other['id']})
        self.assertEqual(response.status,200)
        self.assertEqual(data['username'],'Player_A');self.assertEqual(data['email'],'a@example.test')
        self.assertNotIn('samidev_session',response.cookies)
        self.service.firebase.delete_user.assert_not_awaited()
        self.assertTrue(await self.service.resolve_session(self.first))


class MemoryTests(SecurityScenarios,unittest.IsolatedAsyncioTestCase):
    async def new_service(self): return PlatformService()
    async def close_service(self): pass


@unittest.skipUnless(os.getenv('SAMIDEV_TEST_DATABASE_URL') and os.getenv('SAMIDEV_TEST_REDIS_URL'),'real test database/Redis URLs required')
class PostgresTests(SecurityScenarios,unittest.IsolatedAsyncioTestCase):
    async def new_service(self):
        import redis.asyncio as redis
        from postgres_platform import PostgresPlatformService
        self.redis=redis.from_url(os.environ['SAMIDEV_TEST_REDIS_URL'],decode_responses=True)
        service=PostgresPlatformService(os.environ['SAMIDEV_TEST_DATABASE_URL'],self.redis)
        await service.start()
        return service
    async def close_service(self):
        async with self.service.r.pool.acquire() as conn:
            await conn.execute('DELETE FROM samidev_social_documents WHERE split_part(key,\':\',1)=$1',PREFIX)
        await self.service.close()
        async for key in self.redis.scan_iter(match=PREFIX+':*'): await self.redis.delete(key)
        await self.redis.aclose()

    async def test_second_gateway_sees_revocation_and_resumes_durable_deletion(self):
        from postgres_platform import PostgresPlatformService
        other=PostgresPlatformService(os.environ['SAMIDEV_TEST_DATABASE_URL'],self.redis)
        await other.start();provider(other)
        try:
            rows=await other.security.devices(await other.get_user(self.user['id']),other.token_key(self.first),{})
            current=next(r for r in rows if r['current'])
            await other.security.revoke(self.user['id'],current['id'],other.token_key(self.second))
            self.assertIsNone(await self.service.resolve_session(self.first))
            self.service.firebase.delete_user.side_effect=FirebaseFailure('AUTH_PROVIDER_UNAVAILABLE','offline',503)
            await self.service.deletions.request(self.user)
            self.assertTrue(await other.deletions.process(self.user['id']))
            self.assertIsNone(await self.service.get_user(self.user['id']))
            other.firebase.delete_user.assert_awaited_once_with('a')
        finally:
            await other.close()


class MetadataTests(unittest.TestCase):
    def test_spoofed_geo_header_ignored_without_explicit_trusted_ingress(self):
        request=make_mocked_request('GET','/',headers={'User-Agent':'Mozilla/5.0 (iPhone) Safari/1','X-SamiDev-Country':'SA'})
        with patch.dict(os.environ,{'SAMIDEV_TRUST_GEO_HEADERS':'1'}):
            self.assertEqual(device_metadata(request)['country'],'')
            self.assertEqual(device_metadata(request,trust_proxy=True)['country'],'SA')
        request=make_mocked_request('GET','/',headers={'X-SamiDev-Country':'<script>'})
        with patch.dict(os.environ,{'SAMIDEV_TRUST_GEO_HEADERS':'1'}):
            self.assertEqual(device_metadata(request,trust_proxy=True)['country'],'')


if __name__=='__main__': unittest.main()
