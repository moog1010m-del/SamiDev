"""Small matchmaking bridge over the existing room lifecycle, not a second game service."""
from __future__ import annotations
import asyncio
from contextlib import asynccontextmanager
from store import ROOM_TTL_SECONDS, StoreError, sanitize_settings

# Only real, supported rules. Never accept ratings, rewards or arbitrary room settings.
PRESETS = {
    'pool-eight': {'gameId': 'pool', 'gameType': 0},
    'pool-nine': {'gameId': 'pool', 'gameType': 3},
    'pool-free': {'gameId': 'pool', 'gameType': 7},
    'pool-pyramid': {'gameId': 'pool', 'gameType': 8},
    'pool-scratch': {'gameId': 'pool', 'gameType': 9},
    'pool-teams': {'gameId': 'pool', 'gameType': 1},
    'pool-three': {'gameId': 'pool', 'gameType': 6},
    'carrom-classic': {'gameId': 'carrom', 'players': 0, 'gamemode': 0, 'live': 1},
    'uno-two': {'gameId': 'crazy8', 'seats': 0, 'special': 0, 'live': 1},
    'football-two': {'gameId': 'tablesoccer', 'players': 0, 'goalsToWin': 1, 'live': 0},
}

class QuickPlay:
    def __init__(self, store):
        self.store = store
        self.waiting = {}
        # Four communities x bounded preset list; do not grow locks from user input.
        self.locks = {}

    @asynccontextmanager
    async def lock(self, key):
        if self.store.distributed:
            lock = self.store.r.lock(key + ':lock', timeout=30, blocking_timeout=4)
            if not await lock.acquire():
                raise StoreError('MATCHMAKING_BUSY', 'البحث مشغول مؤقتًا، حاول مجددًا')
            try:
                # Bound all work below the lock lifetime; a lost lock never grants a seat.
                async with asyncio.timeout(8):
                    yield
            finally:
                await asyncio.shield(lock.release())
        else:
            async with self.locks.setdefault(key, asyncio.Lock()):
                yield

    async def match(self, preset, name, node_id, conn_id, account_id, community_id):
        if not account_id:
            raise StoreError('AUTH_REQUIRED', 'سجّل الدخول للبحث عن مباراة')
        if preset not in PRESETS:
            raise StoreError('UNKNOWN_QUICK_MODE', 'نمط اللعب السريع غير مدعوم')
        if community_id not in {'majlis', 'square', 'diwan', 'elite'}:
            raise StoreError('BAD_COMMUNITY', 'المساحة غير مدعومة')
        settings = sanitize_settings(PRESETS[preset])
        key = f'{getattr(self.store, "prefix", "local")}:quick:{community_id}:{preset}'
        async with self.lock(key):
            rid = await self.store.r.get(key) if self.store.distributed else self.waiting.get(key)
            data = None
            if rid:
                try:
                    room = await self.store.get_room_state(rid)
                    roster = room.get('roster') or []
                    if (room.get('settings') == settings and not room.get('started')
                            and not room.get('finished') and any(p.get('connected') for p in roster)):
                        if any(p.get('accountId') == account_id for p in roster):
                            raise StoreError('ACCOUNT_ALREADY_SEATED', 'لديك مباراة انتظار؛ عد إليها أو غادرها أولًا')
                        data = await self.store.join_room(rid, name, None, node_id, conn_id, account_id)
                except StoreError as error:
                    if error.code not in {'ROOM_NOT_FOUND', 'ROOM_FULL', 'MATCH_STARTED'}:
                        raise
            created = data is None
            if created:
                data = await self.store.create_room(name, settings, node_id, conn_id, account_id, community_id)
            # Waiting rooms are real rooms and keep their usual TTL/reconnect/disconnect rules.
            if self.store.distributed:
                if data.get('started'):
                    await self.store.r.delete(key)
                else:
                    await self.store.r.set(key, data['roomId'], ex=ROOM_TTL_SECONDS)
            elif data.get('started'):
                self.waiting.pop(key, None)
            else:
                self.waiting[key] = data['roomId']
            return data, created
