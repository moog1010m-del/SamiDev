"""Offline webhook/checkout regressions. Optional real SQL via test DB URL."""
import asyncio
import copy
import hashlib
import json
import os
import secrets
import sys
import unittest
from contextlib import asynccontextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer
from social_platform import PlatformError
from xsolla_payments import XsollaPayments, WebhookError, PACKS, PREFIX


class Documents:
    """Transactional test double; not a substitute for a real SQL run."""
    def __init__(self):
        self.data = {}
        self.lock = asyncio.Lock()
        self.fail_ledger = False

    @asynccontextmanager
    async def transaction(self, keys):
        async with self.lock:
            before = copy.deepcopy(self.data)
            try:
                yield
            except BaseException:
                self.data = before
                raise

    async def hgetall(self, key):
        return dict(self.data.get(key, {}))

    async def hset(self, key, *, mapping):
        self.data.setdefault(key, {}).update(mapping)

    async def hincrby(self, key, field, delta):
        value = int(self.data[key].get(field, 0)) + delta
        self.data[key][field] = str(value)
        return value

    async def lpush(self, key, value):
        if self.fail_ledger:
            raise RuntimeError('injected storage failure')
        self.data.setdefault(key, []).insert(0, value)

    async def ltrim(self, key, start, end):
        self.data[key] = self.data[key][start:end+1]


class Platform:
    def __init__(self, store):
        self.r = store

    def k_user(self, uid):
        return f'{PREFIX}:user:{uid}'

    def k_store_ledger(self, uid):
        return f'{PREFIX}:store:ledger:{uid}'

    async def get_user(self, uid):
        return await self.r.hgetall(self.k_user(uid))

    async def allow_rate(self, *args):
        return True


class PaymentTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = Documents()
        self.platform = Platform(self.store)
        async def user(request):
            return await self.platform.get_user('alice')
        self.http = SimpleNamespace(platform=self.platform, _user=user,
                                    _body=lambda request: request.json(), _peer=lambda request: '8.8.8.8')
        self.payments = XsollaPayments(self.http)
        self.payments.project = '318587'
        self.payments.secret = 'test-webhook-secret'
        await self.store.hset(self.platform.k_user('alice'), mapping={'id': 'alice', 'coins': '50'})

    def event(self, order_id=1, kind='order_paid', mode='default', sku='plazr_coins_1000'):
        pack = next(p for p in PACKS if p['sku'] == sku)
        return dict(notification_type=kind, user={'external_id': 'alice'},
                    billing={'settings': {'project_id': 318587}},
                    order={'id': order_id, 'mode': mode, 'currency': 'USD',
                           'currency_type': 'real', 'amount': str(pack['usd'])},
                    items=[{'sku': sku, 'quantity': 1}])

    async def balance(self):
        return int((await self.platform.get_user('alice'))['coins'])

    async def test_every_pack(self):
        for index, pack in enumerate(PACKS):
            await self.payments.process(self.event(index+1, sku=pack['sku']))
        self.assertEqual(await self.balance(), 50 + sum(p['coins'] for p in PACKS))

    async def test_concurrent_duplicate_across_instances(self):
        other = XsollaPayments(self.http)
        other.project = self.payments.project
        await asyncio.gather(*(p.process(self.event()) for p in [self.payments, other]*15))
        self.assertEqual(await self.balance(), 1050)

    async def test_full_refund_and_late_payment(self):
        await self.payments.process(self.event())
        await self.store.hincrby(self.platform.k_user('alice'), 'coins', -1000)
        await self.payments.process(self.event(kind='order_canceled'))
        await self.payments.process(self.event(kind='order_canceled'))
        await self.payments.process(self.event())
        self.assertEqual(await self.balance(), -950)

    async def test_cancel_before_payment(self):
        await self.payments.process(self.event(kind='order_canceled'))
        await self.payments.process(self.event())
        self.assertEqual(await self.balance(), 50)

    async def test_sandbox_never_grants_spendable_coins(self):
        await self.payments.process(self.event(mode='sandbox'))
        await self.payments.process(self.event(mode='sandbox', kind='order_canceled'))
        self.assertEqual(await self.balance(), 50)
        await self.payments.process(self.event())
        self.assertEqual(await self.balance(), 1050)

    async def test_bad_amount_currency_quantity_sku_project_user(self):
        edits = [lambda e: e['order'].update(amount='0.01'),
                 lambda e: e['order'].update(currency='SAR'),
                 lambda e: e['items'][0].update(quantity=True),
                 lambda e: e['items'][0].update(sku='unknown'),
                 lambda e: e['billing']['settings'].update(project_id=999),
                 lambda e: e['user'].update(external_id='missing')]
        for edit in edits:
            event = self.event()
            edit(event)
            with self.assertRaises(WebhookError):
                await self.payments.process(event)
        self.assertEqual(await self.balance(), 50)

    async def test_storage_failure_rolls_back_and_retry_succeeds(self):
        self.store.fail_ledger = True
        with self.assertRaises(RuntimeError):
            await self.payments.process(self.event())
        self.assertEqual(await self.balance(), 50)
        self.store.fail_ledger = False
        await self.payments.process(self.event())
        self.assertEqual(await self.balance(), 1050)

    async def test_http_signature_raw_body_and_invalid_json(self):
        self.payments.durable = lambda: True
        app = web.Application()
        app.router.add_post('/webhook', self.payments.webhook)
        async with TestClient(TestServer(app)) as client:
            raw = json.dumps(self.event(), indent=2).encode()
            def headers(value):
                return {'Authorization': 'Signature ' + hashlib.sha1(value + self.payments.secret.encode()).hexdigest()}
            response = await client.post('/webhook', data=raw, headers=headers(raw))
            self.assertEqual(response.status, 204)
            response = await client.post('/webhook', data=raw+b' ', headers=headers(raw))
            self.assertEqual(response.status, 400)
            self.assertEqual((await response.json())['error']['code'], 'INVALID_SIGNATURE')
            for raw in [b'[]', b'{', b'{"user":[],"notification_type":"order_paid"}']:
                response = await client.post('/webhook', data=raw, headers=headers(raw))
                self.assertEqual(response.status, 400)
        self.assertEqual(await self.balance(), 1050)

    async def test_checkout_project_auth_sandbox_and_session_identity(self):
        self.payments.durable = lambda: True
        self.payments.enabled = True
        self.payments.api_key = 'test-api-key'
        self.payments.return_url = 'https://example.test/platform/?topup=return'
        self.payments.sandbox = True
        captured = {}
        class Response:
            status = 201
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            async def json(self): return {'token': 'test-token', 'order_id': 12}
        class Session:
            def __init__(self, **kwargs): pass
            async def __aenter__(self): return self
            async def __aexit__(self, *args): pass
            def post(self, url, **kwargs):
                captured.update(url=url, **kwargs)
                return Response()
        app = web.Application()
        app.router.add_post('/checkout', self.payments.checkout)
        with patch('xsolla_payments.ClientSession', Session):
            async with TestClient(TestServer(app)) as client:
                response = await client.post('/checkout', json={'sku': PACKS[0]['sku'], 'uid': 'victim', 'price': .01})
                self.assertEqual(response.status, 200)
                self.assertTrue((await response.json())['url'].startswith('https://sandbox-secure.xsolla.com/'))
        self.assertEqual(captured['auth'].login, '318587')
        self.assertEqual(captured['json']['user']['id']['value'], 'alice')
        self.assertIs(captured['json']['sandbox'], True)
        self.assertEqual(captured['json']['purchase']['items'], [{'sku': PACKS[0]['sku'], 'quantity': 1}])
        self.assertEqual(await self.balance(), 50)

    async def test_memory_store_cannot_enable_payments(self):
        self.assertFalse(self.payments.available())

    async def test_production_origin_exemption_is_only_for_signed_webhook(self):
        import app as server
        self.payments.durable = lambda: True
        application = web.Application(middlewares=[server.platform_origin_middleware])
        application.router.add_post('/api/payments/xsolla/webhook', self.payments.webhook)
        async def ordinary(request): return web.Response(status=204)
        application.router.add_post('/api/payments/xsolla/checkout', ordinary)
        application.router.add_post('/api/store/buy', ordinary)
        with patch.object(server, 'PRODUCTION_MODE', True), \
             patch.object(server.SERVICE.platform_http, '_secure', return_value=True):
            async with TestClient(TestServer(application)) as client:
                raw = json.dumps({'notification_type': 'user_validation', 'user': {'id': 'alice'}}).encode()
                headers = {'Authorization': 'Signature ' + hashlib.sha1(raw + self.payments.secret.encode()).hexdigest()}
                response = await client.post('/api/payments/xsolla/webhook', data=raw, headers=headers)
                self.assertEqual(response.status, 204)
                response = await client.post('/api/payments/xsolla/webhook', data=raw)
                self.assertEqual(response.status, 400)
                for path in ['/api/payments/xsolla/checkout', '/api/store/buy', '/api/payments/xsolla/webhook/']:
                    response = await client.post(path, data='{}', headers={'Sec-Fetch-Site': 'cross-site'})
                    self.assertEqual(response.status, 403)

    @unittest.skipUnless(os.getenv('SAMIDEV_TEST_DATABASE_URL'), 'test PostgreSQL URL not configured')
    async def test_real_postgres_concurrent_fulfillment(self):
        from postgres_store import PostgresSocialStore
        store = PostgresSocialStore(os.environ['SAMIDEV_TEST_DATABASE_URL'], object())
        await store.start()
        uid = 'xsolla_test_' + secrets.token_hex(8)
        self.platform.r = store
        event = self.event(secrets.randbelow(10**15))
        event['user']['external_id'] = uid
        keys = [self.platform.k_user(uid), self.platform.k_store_ledger(uid),
                f'{PREFIX}:store:xsolla:318587:default:{event["order"]["id"]}']
        try:
            await store.hset(keys[0], mapping={'id': uid, 'coins': '50'})
            await asyncio.gather(*(self.payments.process(event) for _ in range(15)))
            self.assertEqual(int((await store.hgetall(keys[0]))['coins']), 1050)
            event['notification_type'] = 'order_canceled'
            await asyncio.gather(*(self.payments.process(event) for _ in range(15)))
            self.assertEqual(int((await store.hgetall(keys[0]))['coins']), 50)
        finally:
            await store.delete(*keys)
            await store.close()


if __name__ == '__main__':
    unittest.main(verbosity=2)
