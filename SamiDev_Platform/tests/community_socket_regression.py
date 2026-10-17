"""Real HTTP/WS authorization, persistence and recovery for community chat."""
import asyncio
import json
import os
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

os.environ.update(SAMIDEV_STORE='memory', SAMIDEV_PLATFORM_STORE='memory',
                  SAMIDEV_FIREBASE_AUTH='0', SAMIDEV_PRODUCTION='0',
                  SAMIDEV_ALLOWED_ORIGINS='http://localhost',
                  SAMIDEV_ADMIN_USERNAME='', SAMIDEV_ADMIN_PASSWORD='')
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
import app
from aiohttp import ClientSession, WSMsgType, WSServerHandshakeError, web


class CommunitySocketTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.gateway = app.SamiDevRealtime()
        app.SERVICE = self.gateway
        self.service = self.gateway.platform
        self.users = [await self.service.accounts.guest() for _ in range(3)]
        self.tokens = [await self.service.create_session(user['id']) for user in self.users]
        self.client = ClientSession()
        self.sockets = []
        application = app.make_app()
        application.on_startup.clear()
        application.on_shutdown.clear()
        application.on_cleanup.clear()
        application.on_shutdown.append(lambda _: self.service.live.close())
        self.runner = web.AppRunner(application)
        await self.runner.setup()
        site = web.TCPSite(self.runner, '127.0.0.1', 0)
        await site.start()
        self.base = f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}'

    async def asyncTearDown(self):
        for socket in self.sockets:
            await socket.close()
        await self.client.close()
        await self.runner.cleanup()
        self.assertFalse(self.service.live.connections, 'stream ownership must be released on disconnect')
        self.assertFalse(self.service.live.listeners, 'closed sockets must not retain subscriber queues')

    def headers(self, index=0):
        return {'Origin': 'http://localhost', 'Cookie': 'samidev_session=' + self.tokens[index]}

    async def connect(self, index=0, cid='majlis'):
        socket = await self.client.ws_connect(self.base + '/ws/community/' + cid, headers=self.headers(index))
        self.sockets.append(socket)
        self.assertEqual((await socket.receive_json(timeout=2))['type'], 'snapshot')
        return socket

    async def receive(self, socket, kind):
        async with asyncio.timeout(2):
            while True:
                event = await socket.receive_json()
                if event['type'] == kind:
                    return event

    async def test_origin_session_https_and_connection_limits(self):
        for headers, status in [({'Origin': 'http://localhost'}, 401),
                                ({**self.headers(), 'Origin': 'https://unrelated.test'}, 403),
                                ({**self.headers(), 'Sec-Fetch-Site': 'cross-site'}, 403)]:
            with self.assertRaises(WSServerHandshakeError) as raised:
                await self.client.ws_connect(self.base + '/ws/community/majlis', headers=headers)
            self.assertEqual(raised.exception.status, status)
        with patch.object(app, 'PRODUCTION_MODE', True):
            with self.assertRaises(WSServerHandshakeError) as raised:
                await self.client.ws_connect(self.base + '/ws/community/majlis', headers=self.headers())
            self.assertEqual(raised.exception.status, 426)
        for _ in range(4):
            await self.connect()
        with self.assertRaises(WSServerHandshakeError) as raised:
            await self.client.ws_connect(self.base + '/ws/community/majlis', headers=self.headers())
        self.assertEqual(raised.exception.status, 429)

    async def test_ban_is_scoped_and_blocks_existing_and_new_sockets(self):
        sender = await self.connect()
        uid = self.users[0]['id']
        self.service.mem_users[self.users[2]['id']]['role'] = 'admin'
        await self.service.community_rules.moderate(self.users[2]['id'], 'majlis', uid, 'ban')
        await sender.send_json({'type': 'chat_send', 'text': 'banned', 'clientMessageId': 'banned_send_123'})
        self.assertEqual((await self.receive(sender, 'error'))['error'], 'COMMUNITY_BANNED')
        self.assertEqual((await sender.receive(timeout=2)).type, WSMsgType.CLOSE)
        with self.assertRaises(WSServerHandshakeError) as raised:
            await self.client.ws_connect(self.base + '/ws/community/majlis', headers=self.headers())
        self.assertEqual(raised.exception.status, 403)
        other = await self.connect(cid='diwan')
        await other.send_json({'type': 'chat_send', 'text': 'other room allowed', 'clientMessageId': 'scoped_send_123'})
        self.assertEqual((await self.receive(other, 'ack'))['message']['communityId'], 'diwan')

    async def test_identity_room_scope_and_http_retry_are_authoritative(self):
        sender, peer, other = await self.connect(), await self.connect(1), await self.connect(2, 'diwan')
        body = {'type': 'chat_send', 'text': 'socket delivery', 'clientMessageId': 'socket_retry_123',
                'userId': self.users[1]['id'], 'username': 'Admin', 'communityId': 'diwan',
                'chatBubble': 'chat_ember', 'stickerAsset': 'https://unrelated.test/x'}
        await sender.send_json(body)
        entry = (await self.receive(peer, 'message'))['message']
        self.assertEqual(entry['userId'], self.users[0]['id'])
        self.assertEqual(entry['username'], self.users[0]['username'])
        self.assertEqual(entry['communityId'], 'majlis')
        self.assertNotIn('stickerAsset', entry)
        self.assertNotEqual(entry.get('chatBubble'), 'chat_ember')
        self.assertEqual((await self.receive(sender, 'ack'))['message']['id'], entry['id'])
        async with self.client.post(self.base + '/api/communities/majlis/chat', headers=self.headers(), json=body) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual((await response.json())['message']['id'], entry['id'])
        rows = await self.service.community_chat_history('majlis')
        self.assertEqual(sum(row['id'] == entry['id'] for row in rows), 1)
        await sender.send_json({**body, 'text': 'conflicting retry'})
        self.assertEqual((await self.receive(sender, 'error'))['error'], 'MESSAGE_ID_CONFLICT')
        self.assertEqual(await self.service.community_chat_history('diwan'), [])
        await other.send_json({'type': 'ping'})
        self.assertEqual((await other.receive_json(timeout=2))['type'], 'pong', 'another room must not receive this message')
        await sender.close()
        restored = await self.client.ws_connect(self.base + '/ws/community/majlis', headers=self.headers())
        self.sockets.append(restored)
        snapshot = await restored.receive_json(timeout=2)
        self.assertEqual([row['id'] for row in snapshot['messages']], [entry['id']])

    async def test_malformed_messages_sticker_ownership_and_shared_rate_limit(self):
        sender = await self.connect()
        for body, code in [('not json', 'BAD_JSON'), ('[]', 'BAD_JSON'),
                           (json.dumps({'type': 'chat_send', 'text': 'x'}), 'BAD_MESSAGE_ID'),
                           (json.dumps({'type': 'unsupported'}), 'UNKNOWN_MESSAGE'),
                           (json.dumps({'type': 'chat_send', 'stickerId': 'badge_crown', 'clientMessageId': 'not_owned_123'}), 'STICKER_NOT_OWNED')]:
            await sender.send_str(body)
            self.assertEqual((await self.receive(sender, 'error'))['error'], code)
        self.service.mem_inventory.setdefault(self.users[0]['id'], set()).add('badge_crown')
        await sender.send_json({'type': 'chat_send', 'stickerId': 'badge_crown', 'clientMessageId': 'owned_sticker_123'})
        self.assertEqual((await self.receive(sender, 'ack'))['message']['stickerId'], 'badge_crown')
        from social_platform import COMMUNITY_CHAT_USER_RATE
        key = 'community-chat:' + self.users[0]['id'] + ':majlis'
        self.service.mem_rate[key] = (COMMUNITY_CHAT_USER_RATE - 1, time.monotonic() + 12)
        await sender.send_json({'type': 'chat_send', 'text': 'last allowed', 'clientMessageId': 'rate_last_123'})
        await self.receive(sender, 'ack')
        async with self.client.post(self.base + '/api/communities/majlis/chat', headers=self.headers(), json={'text': 'over limit'}) as response:
            self.assertEqual(response.status, 429)
        await sender.send_json({'type': 'chat_send', 'text': 'still limited', 'clientMessageId': 'rate_denied_123'})
        self.assertEqual((await self.receive(sender, 'error'))['error'], 'RATE_LIMIT')

    async def test_moderation_and_revocation_apply_to_already_open_sockets(self):
        sender = await self.connect()
        uid = self.users[0]['id']
        self.service.mem_users[self.users[2]['id']]['role'] = 'admin'
        await self.service.community_rules.moderate(self.users[2]['id'], 'majlis', uid, 'mute')
        await sender.send_json({'type': 'chat_send', 'text': 'muted', 'clientMessageId': 'muted_send_123'})
        self.assertEqual((await self.receive(sender, 'error'))['error'], 'COMMUNITY_MUTED')
        await self.service.community_rules.moderate(self.users[2]['id'], 'majlis', uid, 'unmute')
        await sender.send_json({'type': 'chat_send', 'text': 'allowed', 'clientMessageId': 'unmuted_send_123'})
        await self.receive(sender, 'ack')
        await self.service.delete_session(self.tokens[0])
        await sender.send_json({'type': 'chat_send', 'text': 'revoked', 'clientMessageId': 'revoked_send_123'})
        self.assertEqual((await self.receive(sender, 'error'))['error'], 'AUTH_REQUIRED')
        self.assertEqual((await sender.receive(timeout=2)).type, WSMsgType.CLOSE)
        self.assertFalse(any(row['text'] == 'revoked' for row in await self.service.community_chat_history('majlis')))

    async def test_publication_outage_is_visible_and_preserves_local_delivery(self):
        from community_live import CommunityLive
        from types import SimpleNamespace
        class FailedRedis:
            async def publish(self, *args):
                raise OSError('simulated publication outage')
        live = CommunityLive(SimpleNamespace(r=FailedRedis()))
        queue = asyncio.Queue()
        live.listeners['majlis'] = {queue}
        event = {'type': 'message', 'message': {'id': 'already-committed'}}
        with self.assertLogs('community_live', level='WARNING') as logs:
            await live.publish('majlis', event)
        self.assertEqual(queue.get_nowait(), event)
        self.assertEqual(live.status()['publicationFailures'], 1)
        self.assertIn('publication failed: OSError', logs.output[0])


if __name__ == '__main__':
    unittest.main()
