"""One Redis subscription per gateway, bounded subscriber queues, durable snapshots."""
import asyncio
import json
import logging
import secrets
import time
from contextlib import asynccontextmanager


class CommunityLive:
    def __init__(self, service, namespace="community-live"):
        self.service = service
        self.namespace = namespace
        self.listeners = {}
        self.connections = {}
        self.task = None
        self.ready = asyncio.Event()
        self.instance = secrets.token_hex(12)
        self.publish_failures = 0
        self.last_warning = float('-inf')

    def warn(self, operation, error):
        if time.monotonic() - self.last_warning >= 30:
            self.last_warning = time.monotonic()
            logging.getLogger(__name__).warning('Community live %s failed: %s', operation, type(error).__name__)

    def status(self):
        return {'node': self.instance[:8], 'crossGatewayReady': self.ready.is_set() if self.redis is not None else None,
                'publicationFailures': self.publish_failures}

    @property
    def redis(self):
        store = self.service.r
        return getattr(store, 'transient', store)

    def channel(self, cid):
        from social_platform import PREFIX
        return f'{PREFIX}:{self.namespace}:{cid}'

    def deliver(self, cid, event):
        for queue in tuple(self.listeners.get(cid, ())):
            if queue.full():
                while not queue.empty(): queue.get_nowait()
                queue.put_nowait({'type':'resync'})
            else:
                queue.put_nowait(event)

    async def publish(self, cid, event):
        self.deliver(cid, event)
        if self.redis is not None:
            # Persistence already committed. A publication outage must not make
            # the sender retry a committed message; periodic snapshots repair it.
            try: await asyncio.wait_for(self.redis.publish(self.channel(cid), json.dumps({**event, "_sender":self.instance})), 2)
            except Exception as error:
                self.publish_failures += 1
                self.warn('publication', error)

    async def run(self):
        from social_platform import PREFIX
        while True:
            try:
                async with self.redis.pubsub() as sub:
                    await sub.psubscribe(f'{PREFIX}:{self.namespace}:*')
                    async for message in sub.listen():
                        if message['type']=='psubscribe':self.ready.set();continue
                        if message['type'] != 'pmessage': continue
                        try:
                            channel=message['channel'];channel=channel.decode() if isinstance(channel,bytes) else channel
                            event=json.loads(message['data'])
                            if isinstance(event,dict) and event.get('_sender')!=self.instance:
                                event.pop('_sender',None)
                                self.deliver(channel.rsplit(':',1)[-1],event)
                        except (ValueError,TypeError): continue
            except asyncio.CancelledError: raise
            except Exception as error:
                self.ready.clear()
                self.warn('subscription', error)
                await asyncio.sleep(1)

    @asynccontextmanager
    async def subscribe(self, cid, uid=None):
        from social_platform import PlatformError
        if uid and self.connections.get(uid,0)>=4:
            raise PlatformError('STREAM_LIMIT','أغلق إحدى النوافذ المفتوحة للمحادثة',429)
        if uid:self.connections[uid]=self.connections.get(uid,0)+1
        queue=asyncio.Queue(maxsize=128)
        self.listeners.setdefault(cid,set()).add(queue)
        if self.redis is not None and self.task is None:
            self.task=asyncio.create_task(self.run(),name='community-live')
        try:
            if self.redis is not None:
                try: await asyncio.wait_for(self.ready.wait(),3)
                except TimeoutError: pass
            yield queue
        finally:
            if uid:
                self.connections[uid]-=1
                if not self.connections[uid]:self.connections.pop(uid,None)
            self.listeners.get(cid,set()).discard(queue)
            if not self.listeners.get(cid): self.listeners.pop(cid,None)

    async def close(self):
        self.ready.clear()
        for queues in tuple(self.listeners.values()):
            for queue in tuple(queues):
                while not queue.empty():queue.get_nowait()
                queue.put_nowait({'type':'closed'})
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task,return_exceptions=True)
            self.task=None
