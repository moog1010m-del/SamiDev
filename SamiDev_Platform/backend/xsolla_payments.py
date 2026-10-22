"""Xsolla Catalog checkout and combined webhooks; PostgreSQL owns fulfillment."""
import hashlib
import hmac
import ipaddress
import json
import logging
import os
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode, urlsplit

from aiohttp import BasicAuth, ClientSession, ClientTimeout, web
from social_platform import PlatformError, now_ms, PREFIX

LOG = logging.getLogger(__name__)
PACKS = tuple(dict(sku=f'plazr_coins_{coins}', coins=coins,
                  usd=coins // 1000) for coins in (1000, 5000, 10000, 25000, 50000))
BY_SKU = {p['sku']: p for p in PACKS}
WEBHOOK_PATH = '/api/payments/xsolla/webhook'


class WebhookError(Exception):
    def __init__(self, code):
        self.code = code


class XsollaPayments:
    def __init__(self, http):
        self.http = http
        self.platform = http.platform
        self.project = os.getenv('XSOLLA_PROJECT_ID', '318587')
        self.api_key = os.getenv('XSOLLA_API_KEY', '')
        self.secret = os.getenv('XSOLLA_WEBHOOK_SECRET', '')
        self.return_url = os.getenv('XSOLLA_RETURN_URL', '')
        self.sandbox = os.getenv('XSOLLA_SANDBOX', '1') == '1'
        self.enabled = os.getenv('XSOLLA_ENABLED', '0') == '1'

    def durable(self):
        from postgres_store import PostgresSocialStore
        return isinstance(self.platform.r, PostgresSocialStore)

    def available(self):
        url = urlsplit(self.return_url)
        return bool(self.enabled and self.durable() and self.project.isdigit() and self.api_key
                    and self.secret and url.scheme == 'https' and url.netloc)

    def catalog(self):
        return dict(available=self.available(), sandbox=self.sandbox,
                    packs=[dict(p, currency='USD') for p in PACKS])

    async def checkout(self, request):
        user = await self.http._user(request)
        if not self.available():
            raise PlatformError('PAYMENTS_UNAVAILABLE', 'شحن الكوينز غير متاح حاليًا', 503)
        if not await self.platform.allow_rate(f'xsolla-checkout:{user["id"]}', 5, 60):
            raise PlatformError('RATE_LIMIT', 'محاولات كثيرة؛ حاول بعد قليل', 429)
        body = await self.http._body(request)
        pack = BY_SKU.get(str(body.get('sku') or ''))
        if not pack:
            raise PlatformError('BAD_PACK', 'باقة الكوينز غير صالحة', 400)
        settings = dict(currency='USD', return_url=self.return_url)
        settings['redirect_policy'] = dict(redirect_conditions='successful_or_canceled', delay=0)
        payload = dict(sandbox=self.sandbox, user={'id': {'value': str(user['id'])}},
                       purchase={'items': [{'sku': pack['sku'], 'quantity': 1}]},
                       settings=settings)
        # Xsolla determines the buyer's country from the trusted client IP.
        try:
            peer = str(ipaddress.ip_address(self.http._peer(request)))
            if ipaddress.ip_address(peer).version != 4:
                raise ValueError('IPv4 required')
        except ValueError:
            raise PlatformError('PAYMENT_LOCATION', 'تعذر تحديد موقع الدفع', 400)
        try:
            async with ClientSession(timeout=ClientTimeout(total=20)) as session:
                async with session.post(
                    f'https://store.xsolla.com/api/v3/project/{self.project}/admin/payment/token',
                    auth=BasicAuth(self.project, self.api_key), json=payload,
                    headers={'X-User-Ip': peer}, allow_redirects=False,
                ) as response:
                    if response.status != 201:
                        LOG.warning('Xsolla checkout failed: HTTP %s', response.status)
                        raise ValueError('upstream')
                    data = await response.json()
                    token = data.get('token')
                    if not isinstance(token, str) or not token:
                        raise ValueError('missing token')
        except Exception:
            raise PlatformError('PAYMENT_PROVIDER', 'تعذر فتح الدفع؛ حاول بعد قليل', 502)
        host = 'sandbox-secure.xsolla.com' if self.sandbox else 'secure.xsolla.com'
        return web.json_response({'ok': True, 'url': f'https://{host}/paystation4/?'
                                  + urlencode({'token': token})},
                                 headers={'Cache-Control': 'no-store'})

    async def webhook(self, request):
        if not self.secret or not self.durable():
            return web.json_response({'error': {'code': 'SERVICE_UNAVAILABLE'}}, status=503)
        raw = await request.read()
        signature = 'Signature ' + hashlib.sha1(raw + self.secret.encode()).hexdigest()
        if not hmac.compare_digest(signature.encode(), request.headers.get('Authorization', '').encode()):
            return web.json_response({'error': {'code': 'INVALID_SIGNATURE'}}, status=400)
        try:
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise WebhookError('INVALID_PARAMETER')
            await self.process(body)
        except (ValueError, TypeError, KeyError, AttributeError, InvalidOperation):
            return web.json_response({'error': {'code': 'INVALID_PARAMETER'}}, status=400)
        except WebhookError as exc:
            return web.json_response({'error': {'code': exc.code}}, status=400)
        return web.Response(status=204)

    async def process(self, body):
        kind = body.get('notification_type')
        uid = str(body.get('user', {}).get('external_id') or body.get('user', {}).get('id') or '')
        if not uid or len(uid) > 128:
            raise WebhookError('INVALID_USER')
        if kind == 'user_validation':
            user = await self.platform.get_user(uid)
            if not user or str(user.get('banned', '0')) == '1':
                raise WebhookError('INVALID_USER')
            return
        if kind not in {'order_paid', 'order_canceled'}:
            raise WebhookError('INVALID_PARAMETER')
        order = body['order']
        mode = order.get('mode')
        if mode not in {'default', 'sandbox'}:
            raise WebhookError('INVALID_PARAMETER')
        billing = body.get('billing', {})
        if str(billing.get('settings', {}).get('project_id')) != self.project:
            raise WebhookError('INVALID_PROJECT')
        order_id = str(order['id'])
        if not order_id.isdigit() or len(order_id) > 64:
            raise WebhookError('INVALID_PARAMETER')
        items = body['items']
        if not isinstance(items, list) or not 1 <= len(items) <= 20:
            raise WebhookError('INVALID_PARAMETER')
        coins = usd = 0
        for item in items:
            pack = BY_SKU.get(item.get('sku'))
            quantity = item.get('quantity')
            if not pack or type(quantity) is not int or not 1 <= quantity <= 100:
                raise WebhookError('INVALID_PARAMETER')
            coins += pack['coins'] * quantity
            usd += pack['usd'] * quantity
        if (order.get('currency') != 'USD' or order.get('currency_type') != 'real'
                or Decimal(str(order['amount'])) != Decimal(usd)):
            raise WebhookError('INCORRECT_AMOUNT')
        # Sandbox orders are audited but never create spendable coins.
        user_key = self.platform.k_user(uid)
        ledger_key = self.platform.k_store_ledger(uid)
        key = f'{PREFIX}:store:xsolla:{self.project}:{mode}:{order_id}'
        store = self.platform.r
        async with store.transaction([key, user_key, ledger_key]):
            previous = await store.hgetall(key)
            if previous and (previous['uid'] != uid or int(previous['coins']) != coins):
                raise WebhookError('INVALID_PARAMETER')
            canceled = kind == 'order_canceled'
            old_status = previous.get('status')
            if old_status == 'canceled' or (old_status == 'paid' and not canceled):
                return
            user = await self.platform.get_user(uid)
            # Retried events for a deleted account must not recreate its wallet.
            if not user and not previous:
                raise WebhookError('INVALID_USER')
            delta = (-coins if old_status == 'paid' else 0) if canceled else coins
            if mode == 'sandbox':
                delta = 0
            if user and delta:
                balance = await store.hincrby(user_key, 'coins', delta)
                entry = dict(id=f'xsolla-{mode}-{order_id}-{kind}',
                             type='coin_refund' if canceled else 'coin_topup',
                             amount=delta, balance=balance, createdAt=now_ms(), provider='xsolla')
                await store.lpush(ledger_key, json.dumps(entry))
                await store.ltrim(ledger_key, 0, 99)
            await store.hset(key, mapping=dict(uid=uid, coins=str(coins),
                             status='canceled' if canceled else 'paid', updatedAt=str(now_ms())))
