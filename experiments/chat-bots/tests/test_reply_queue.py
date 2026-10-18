import asyncio
import time
import unittest
from types import SimpleNamespace
from reply_queue import next_reply_message


class ReplyQueueTests(unittest.IsolatedAsyncioTestCase):
    def engine(self, cooldown=.08):
        return SimpleNamespace(last_sent=time.monotonic(),
                               config={'cooldown_seconds':cooldown}, revision=1)

    async def test_message_waits_for_cooldown_instead_of_disappearing(self):
        engine=self.engine();pending=asyncio.Queue(maxsize=1)
        pending.put_nowait('hello')
        message,revision=await next_reply_message(pending,engine,.01)
        self.assertEqual((message,revision),('hello',1))
        self.assertGreaterEqual(time.monotonic()-engine.last_sent,.075)

    async def test_latest_message_replaces_pending_reply_and_resets_debounce(self):
        engine=self.engine(.01);pending=asyncio.Queue(maxsize=1)
        pending.put_nowait('first')
        task=asyncio.create_task(next_reply_message(pending,engine,.10))
        await asyncio.sleep(.03)
        engine.revision=2;pending.put_nowait('second');sent=time.monotonic()
        self.assertEqual(await task,('second',2))
        self.assertGreaterEqual(time.monotonic()-sent,.09)

    async def test_shutdown_cancels_long_wait(self):
        engine=self.engine(3600);pending=asyncio.Queue(maxsize=1)
        pending.put_nowait('hello')
        task=asyncio.create_task(next_reply_message(pending,engine,4))
        await asyncio.sleep(.01);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
