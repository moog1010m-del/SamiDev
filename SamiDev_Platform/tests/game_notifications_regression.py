"""Table pushes must survive offline clients without repeating each revision."""
import asyncio
import os
import sys
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
from game_notifications import GameNotifications

class GamePushTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.env = patch.dict(os.environ, {'SAMIDEV_PUSH_ENABLED':'1'}); self.env.start()
        self.room = {'begun':True, 'finished':False, 'roster':[{'seat':0,'accountId':'alice','connected':False},{'seat':1,'accountId':'bob','connected':True}]}
        self.store = SimpleNamespace(get_room_state=AsyncMock(side_effect=lambda rid:self.room))
        self.platform = SimpleNamespace(get_user=AsyncMock(return_value={'id':'alice'}), direct=SimpleNamespace(devices=AsyncMock(return_value={})))
        self.push = GameNotifications(self.platform,self.store)
        self.push.deliver = AsyncMock()
    async def asyncTearDown(self):
        await self.push.close(); self.env.stop()
    async def drain(self): await self.push.queue.join()
    async def test_begin_and_turns_notify_offline_seats_once(self):
        await self.push.observe('ROOM', started=True); await self.drain()
        self.assertEqual([c.args[1] for c in self.push.deliver.call_args_list],['alice','bob'])
        await self.push.observe('ROOM', started=True); await self.drain()
        self.assertEqual(self.push.deliver.await_count,2)
        await self.push.observe('ROOM',turn=[0]); await self.drain()
        await self.push.observe('ROOM',turn=[0]); await self.drain()
        self.assertEqual(self.push.deliver.await_count,3)
        await self.push.observe('ROOM',turn=[1]); await self.drain()
        await self.push.observe('ROOM',turn=[0]); await self.drain()
        self.assertEqual(self.push.deliver.await_count,5)
    async def test_waiting_finished_disabled_and_spectators(self):
        self.room['begun']=False
        await self.push.observe('ROOM',started=True)
        self.room['begun']=True; self.room['finished']=True
        await self.push.observe('ROOM',turn=[0])
        self.room['finished']=False
        with patch.dict(os.environ,{'SAMIDEV_PUSH_ENABLED':'0'}): await self.push.observe('ROOM',started=True)
        await self.push.observe('ROOM',turn=[9]); await self.drain()
        self.push.deliver.assert_not_awaited()
    async def test_stale_turn_or_departed_player_is_not_delivered(self):
        actual = GameNotifications(self.platform,self.store)
        actual.memory['sd:game-push:turn:ROOM']='1'
        await actual.deliver('ROOM','alice',0,False,time.monotonic())
        self.platform.get_user.assert_not_awaited()
        self.room['roster']=[]
        await actual.deliver('ROOM','alice',0,True,time.monotonic())
        self.platform.get_user.assert_not_awaited()
        await actual.deliver('ROOM','alice',0,True,time.monotonic()-31)
        self.platform.get_user.assert_not_awaited()
    async def test_devices_require_current_own_session(self):
        actual = GameNotifications(self.platform,self.store)
        self.platform.direct.devices.return_value={'a':{'at':time.time(),'session':'revoked','fid':'do-not-send'}}
        self.platform.resolve_session_key=AsyncMock(return_value={'id':'different-account'})
        await actual.deliver('ROOM','alice',0,True,time.monotonic())
        self.platform.resolve_session_key.assert_awaited_once_with('revoked')

    async def test_os_payload_uses_high_priority_and_short_expiry(self):
        from firebase_admin import messaging
        actual = GameNotifications(self.platform,self.store)
        self.platform.direct.devices.return_value={'a':{'at':time.time(),'session':'valid','fid':'example-device'}}
        self.platform.resolve_session_key=AsyncMock(return_value={'id':'alice'})
        async def work(fn): return fn()
        self.platform.firebase=SimpleNamespace(_sdk=lambda:None,_app=None,_work=work)
        with patch.object(messaging,'send_each_for_multicast') as send:
            await actual.deliver('ROOM','alice',0,True,time.monotonic())
            message=send.call_args.args[0]
            self.assertEqual(message.data,{'type':'game_started','roomId':'ROOM','accountId':'alice'})
            self.assertEqual(message.android.priority,'high')
            self.assertEqual(message.android.notification.channel_id,'plazr_games')
            self.assertEqual(message.android.ttl,30)
            actual.memory['sd:game-push:turn:ROOM']='0'
            await actual.deliver('ROOM','alice',0,False,time.monotonic())
            self.assertEqual(send.call_args.args[0].data['type'],'game_turn')

if __name__ == '__main__': unittest.main()
