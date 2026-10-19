"""Exercise private boundaries, durable namespaces, retries and account erasure."""
import asyncio
import os
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
os.environ['SAMIDEV_FIREBASE_AUTH'] = '0'
from social_platform import PlatformService, PlatformError
from postgres_store import durable_key

class DirectTest(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.s = PlatformService()
        self.a, self.b, self.c = [await self.s.accounts.guest() for _ in range(3)]
        await self.s.send_friend_request(self.a, self.b['username'])
        await self.s.respond_friend_request(self.b, self.a['id'], True)
        self.d = self.s.direct

    async def asyncTearDown(self):
        await self.d.live.close()

    async def test_friend_only_retry_mute_read(self):
        a,b,c = [u['id'] for u in (self.a,self.b,self.c)]
        body={'text':'السلام عليكم 8 سلندر <img src=x>', 'clientMessageId':'a'*16}
        with self.assertRaises(PlatformError): await self.d.send(a,c,body)
        msg=await self.d.send(a,b,body)
        self.assertEqual(msg,await self.d.send(a,b,body))
        self.assertEqual(len((await self.d.history(b,a))['messages']),1)
        self.assertEqual((await self.d.inbox(self.b))['threads'][0]['unread'],1)
        await self.d.read(b,a,0)
        self.assertEqual((await self.d.inbox(self.b))['threads'][0]['unread'],1)
        await self.d.read(b,a,msg['seq'])
        await self.d.read(b,a,0)
        self.assertEqual((await self.d.inbox(self.b))['threads'][0]['unread'],0)
        await self.d.mute(b,a,True)
        self.assertTrue((await self.d.history(b,a))['muted'])
        with self.assertRaises(PlatformError): await self.d.mute(b,a,'false')
        await self.s.safety.update(b,a,True)
        with self.assertRaises(PlatformError): await self.d.history(b,a)
        with self.assertRaises(PlatformError): await self.d.send(a,b,body)

    async def test_link_rotates_expires_and_delete(self):
        link=(await self.d.invite(self.a['id']))['url'].split('friend=')[1]
        await self.d.redeem(self.c,link)
        self.assertIn(self.c['id'],self.s.mem_requests[self.a['id']])
        await self.d.invite(self.a['id'])
        with self.assertRaises(PlatformError): await self.d.redeem(self.c,link)
        await self.d.send(self.a['id'],self.b['id'],{'text':'private', 'clientMessageId':'b'*16})
        await self.d.mute(self.b['id'],self.a['id'],True)
        self.assertTrue(await self.s.deletions.request(self.a))
        self.assertFalse(any(self.a['id'] in k.split(':') for k in self.d.memory))

    async def test_push_session_mute_and_minimal_payload(self):
        from unittest.mock import patch
        a,b = self.a['id'],self.b['id']
        session=await self.s.create_session(b)
        await self.d.device(b,self.s.token_key(session),{'deviceId':'test_device_12345','fid':'abcdefghijklmnopqrstuv'})
        def sdk(): return None
        async def work(callback): return callback()
        self.s.firebase._sdk=sdk
        self.s.firebase._work=work
        with patch.dict(os.environ,{'SAMIDEV_PUSH_ENABLED':'1'}), patch('firebase_admin.messaging.send_each_for_multicast') as deliver:
            await self.d.push(b,a,'message-id')
            self.assertEqual(deliver.call_count,1)
            payload=deliver.call_args.args[0]
            self.assertEqual(payload.data['accountId'],b)
            self.assertEqual(set(payload.data),{'type','peerId','accountId','messageId'})
            self.assertNotIn('text',payload.data)
            await self.d.mute(b,a,True)
            await self.d.push(b,a,'next')
            self.assertEqual(deliver.call_count,1)
            await self.d.mute(b,a,False)
            await self.s.delete_session(session)
            await self.d.push(b,a,'revoked')
            self.assertEqual(deliver.call_count,1)

    async def test_isolated_and_durable(self):
        self.assertNotEqual(self.d.live.channel(self.a['id']),self.s.live.channel(self.a['id']))
        for kind in ('direct','direct-mute','friend-link','push-devices'):
            self.assertTrue(durable_key(self.d.key(kind,self.a['id'])))
        with self.assertRaises(PlatformError):
            await self.d.send(self.a['id'],self.b['id'],{'text':'hello','clientMessageId':'bad'})

if __name__=='__main__': unittest.main()
