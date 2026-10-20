"""OS notifications from authoritative events, independent of client sockets."""
import asyncio
import logging
import os
import time


class GameNotifications:
    def __init__(self, platform, store):
        self.platform, self.store = platform, store
        self.queue = asyncio.Queue(maxsize=128)
        self.task = None
        self.memory = {}

    async def observe(self, rid, turn=None, started=False, finished=False):
        if os.getenv('SAMIDEV_PUSH_ENABLED') != '1': return
        try:
            room = await self.store.get_room_state(rid)
            if finished or room.get('finished') or not room.get('begun'): return
            value = 'started' if started else ','.join(map(str, sorted(set(turn or []))))
            key = f'sd:game-push:{"begin" if started else "turn"}:{rid}'
            redis = getattr(self.store, 'r', None)
            if redis is not None:
                if started: changed = await redis.set(key, value, nx=True, ex=86400)
                else:
                    old = await redis.set(key, value, get=True, ex=86400)
                    if isinstance(old, bytes): old = old.decode()
                    changed = old != value
            else:
                changed = self.memory.get(key) != value
                self.memory[key] = value
                while len(self.memory) > 2048: self.memory.pop(next(iter(self.memory)))
            if not changed: return
            for player in room.get('roster', []):
                uid = player.get('accountId')
                if not uid or (not started and player.get('seat') not in (turn or [])): continue
                try: self.queue.put_nowait((rid, uid, player['seat'], started, time.monotonic()))
                except asyncio.QueueFull: logging.getLogger(__name__).warning('Game notification queue full')
            if self.task is None: self.task = asyncio.create_task(self.worker(), name='game-push')
        except Exception: logging.getLogger(__name__).warning('Game notification unavailable')

    async def worker(self):
        while True:
            item = await self.queue.get()
            try: await self.deliver(*item)
            except asyncio.CancelledError: raise
            except Exception: logging.getLogger(__name__).warning('Game push delivery unavailable')
            finally: self.queue.task_done()

    async def deliver(self, rid, uid, seat, started, queued_at):
        if time.monotonic() - queued_at > 30: return
        room = await self.store.get_room_state(rid)
        if room.get('finished') or not room.get('begun') or not any(p.get('accountId') == uid and p.get('seat') == seat for p in room.get('roster', [])): return
        if not started:
            redis = getattr(self.store, 'r', None)
            key = f'sd:game-push:turn:{rid}'
            current = await redis.get(key) if redis is not None else self.memory.get(key)
            if isinstance(current, bytes): current = current.decode()
            if str(seat) not in (current or '').split(','): return
        user = await self.platform.get_user(uid)
        if not user or user.get('banned') == '1' or user.get('deleting') == '1': return
        tokens = set()
        for device in (await self.platform.direct.devices(uid)).values():
            if device.get('at', 0) < time.time() - 30 * 86400: continue
            owner = await self.platform.resolve_session_key(device['session'])
            if owner and owner['id'] == uid: tokens.add(device['fid'])
        if not tokens: return
        from firebase_admin import messaging
        self.platform.firebase._sdk()
        def send():
            return messaging.send_each_for_multicast(messaging.MulticastMessage(
                fids=list(tokens), notification=messaging.Notification(title='Plazr', body='بدأت مباراتك — ارجع للطاولة' if started else 'دورك الآن — ارجع للطاولة'),
                data={'type': 'game_started' if started else 'game_turn', 'roomId': rid, 'accountId': uid},
                android=messaging.AndroidConfig(priority='high', ttl=30, collapse_key=f'table:{rid}', notification=messaging.AndroidNotification(channel_id='plazr_games', tag=f'table:{rid}')),
                apns=messaging.APNSConfig(headers={'apns-expiration': str(int(time.time()) + 30), 'apns-collapse-id': f'table:{rid}'}, payload=messaging.APNSPayload(aps=messaging.Aps(sound='default')))), app=self.platform.firebase._app)
        await self.platform.firebase._work(send)

    async def close(self):
        if self.task:
            self.task.cancel()
            await asyncio.gather(self.task, return_exceptions=True)
            self.task = None
