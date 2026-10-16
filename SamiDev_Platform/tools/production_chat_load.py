#!/usr/bin/env python3
"""Real authenticated community chat load. No game moves or admin policy changes.
Prepare inside a gateway container (existing production environment), then run
HTTP/SSE traffic against --url. Session file is secret; reports contain no tokens.
"""
import argparse
import asyncio
from collections import Counter
import json
import os
from pathlib import Path
import random
import secrets
import sys
import time
from urllib.parse import quote, urlsplit

import aiohttp


async def prepare(args):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'backend'))
    from app import SERVICE
    from social_platform import COMMUNITIES
    if SERVICE.platform.r is None:
        raise RuntimeError('Preparation requires shared production storage, not memory')
    path = Path(args.sessions)
    # Never overwrite a prior run's credentials or silently create more accounts.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    users = []
    try:
        await SERVICE.platform.start()
        for room in args.rooms:
            if room not in COMMUNITIES:
                raise ValueError('Unknown room: ' + room)
            for _ in range(args.per_room):
                user = await SERVICE.platform.accounts.guest()
                token = await SERVICE.platform.create_session(user['id'], metadata={'userAgent': 'SamiDevChatLoad/1'})
                users.append({'room': room, 'userId': user['id'], 'token': token})
                # Checkpoint credentials so a failed preparation can be inspected.
                os.lseek(fd, 0, os.SEEK_SET)
                os.ftruncate(fd, 0)
                os.write(fd, json.dumps(users).encode())
            print(f'Prepared {room}: {args.per_room} test guests', flush=True)
    finally:
        os.close(fd)
        if hasattr(SERVICE.platform, 'close'):
            await SERVICE.platform.close()
        await SERVICE.store.r.aclose()
    print(f'Saved {len(users)} sessions to {path}. Keep this file private. Test guest accounts remain in the database.')


class Load:
    def __init__(self, args, users):
        self.args, self.users = args, users
        self.run_id = secrets.token_hex(6)
        self.count = Counter()
        self.records = {}
        self.connected = set()
        self.clients = []
        self.tasks = []
        self.stop = asyncio.Event()
        self.sending = asyncio.Event()
        self.pace = asyncio.Lock()
        self.next_request = 0.0
        self.started = time.monotonic()
        self.live = set()

    async def request(self, session, method, path, **kwargs):
        async with self.pace:
            now = time.monotonic()
            await asyncio.sleep(max(0, self.next_request - now))
            self.next_request = time.monotonic() + 1 / self.args.rps
        try:
            async with session.request(method, self.args.url + path, allow_redirects=False, **kwargs) as response:
                self.count[f'http_{response.status}'] += 1
                body = await response.json(content_type=None)
                if response.status >= 400:
                    self.count['error_' + str(body.get('error', response.status))[:80]] += 1
                    return None
                if response.status >= 300:
                    self.count['unexpected_redirect'] += 1
                    return None
                return body
        except (aiohttp.ClientError, TimeoutError, ValueError):
            self.count['request_errors'] += 1
            return None

    def receive(self, index, room, event):
        kind = event.get('type')
        rows = [event.get('message')] if kind == 'message' else event.get('messages', [])
        for row in rows:
            if not isinstance(row, dict):
                continue
            record = self.records.get(row.get('clientMessageId'))
            if record is None:
                continue  # Never record real users' messages.
            if record['room'] != room:
                self.count['cross_room_deliveries'] += 1
                continue
            if index not in record['targets']:
                continue
            if index in record['seen']:
                if kind == 'message' and index in record['events']:
                    self.count['duplicate_live_events'] += 1
            else:
                record['seen'][index] = (time.monotonic() - record['at']) * 1000
                if kind != 'message':
                    self.count['recovered_by_snapshot'] += 1
            if kind == 'message':
                record['events'].add(index)

    async def stream(self, index, user, session, ready):
        room = user['room']
        while not self.stop.is_set():
            try:
                async with session.get(self.args.url + '/api/communities/' + quote(room) + '/events',
                                       timeout=aiohttp.ClientTimeout(total=None, sock_connect=15, sock_read=35),
                                       allow_redirects=False) as response:
                    if response.status != 200 or 'text/event-stream' not in response.headers.get('Content-Type', ''):
                        self.count[f'stream_http_{response.status}'] += 1
                        if response.status in (401, 403):
                            return
                        await asyncio.sleep(15)
                        continue
                    self.live.add(index)
                    data = []
                    async for raw in response.content:
                        line = raw.decode('utf-8').rstrip('\r\n')
                        if line.startswith('data:'):
                            data.append(line[5:].lstrip())
                        elif not line and data:
                            event = json.loads('\n'.join(data)); data = []
                            if event.get('type') == 'access_denied':
                                self.count['stream_access_denied'] += 1
                                return
                            self.receive(index, room, event)
                            if event.get('type') == 'snapshot':
                                self.connected.add(index)
                                ready.set()
            except (aiohttp.ClientError, TimeoutError, ValueError):
                self.count['stream_errors'] += 1
            finally:
                self.live.discard(index)
            if not self.stop.is_set():
                self.count['stream_reconnects'] += 1
                await asyncio.sleep(random.uniform(2, 5))

    async def maintain(self, session, room):
        while not self.stop.is_set():
            await asyncio.sleep(random.uniform(45, 60))
            # Refresh community presence too, not just global heartbeat.
            await self.request(session, 'GET', '/api/communities/' + quote(room) + '?chat=0')

    async def sender(self, index, user, session):
        await self.sending.wait()
        while not self.stop.is_set():
            try:
                await asyncio.wait_for(self.stop.wait(), random.uniform(self.args.min_interval, self.args.max_interval))
                break
            except TimeoutError:
                pass
            if index not in self.live:
                continue
            nonce = self.run_id + '-' + secrets.token_hex(12)
            room = user['room']
            record = {'room': room, 'at': time.monotonic(), 'accepted': False,
                      'targets': {i for i, u in enumerate(self.users) if u['room'] == room},
                      'seen': {}, 'events': set()}
            self.records[nonce] = record
            try:
                body = await self.request(session, 'POST', '/api/communities/' + quote(room) + '/chat', json={
                    'text': f'[LOAD TEST {self.run_id}] اختبار شات {random.randrange(1000000)}',
                    'clientMessageId': nonce})
            except asyncio.CancelledError:
                self.count['unconfirmed_sends'] += 1
                raise
            if body and body.get('ok') and isinstance(body.get('message'), dict):
                record['accepted'] = True
                self.count['accepted_messages'] += 1
            else:
                self.count['unconfirmed_sends'] += 1

    async def connect(self, index, user):
        session = aiohttp.ClientSession(
            cookies={'samidev_session': user['token']},
            headers={'Origin': self.args.url, 'User-Agent': 'SamiDevChatLoad/1'},
            timeout=aiohttp.ClientTimeout(total=20),
            connector=aiohttp.TCPConnector(limit=4), read_bufsize=512 * 1024)
        self.clients.append((session, user))
        me = await self.request(session, 'GET', '/api/me')
        if not me or str(me.get('user', {}).get('id')) != str(user['userId']):
            raise RuntimeError(f'Test session {index} is expired or belongs to another account')
        entered = await self.request(session, 'POST', '/api/communities/' + quote(user['room']) + '/enter', json={})
        if not entered or not entered.get('ok'):
            raise RuntimeError(f'Cannot enter room {user["room"]} for test user {index}; check capacity and HTTP counters')
        ready = asyncio.Event()
        self.tasks.append(asyncio.create_task(self.stream(index, user, session, ready)))
        await asyncio.wait_for(ready.wait(), 45)
        self.tasks.extend([asyncio.create_task(self.sender(index, user, session)),
                           asyncio.create_task(self.maintain(session, user['room']))])

    def report(self, completed, failure):
        accepted = [r for r in self.records.values() if r['accepted']]
        expected = sum(len(r['targets']) for r in accepted)
        received = sum(len(r['seen']) for r in accepted)
        latencies = sorted(ms for r in accepted for ms in r['seen'].values())
        def percentile(p):
            return round(latencies[min(len(latencies)-1, int((len(latencies)-1)*p))], 2) if latencies else None
        return {'runId': self.run_id, 'completed': completed, 'failure': failure,
                'elapsedSeconds': round(time.monotonic()-self.started, 1),
                'rooms': dict(Counter(u['room'] for u in self.users)),
                'clientsWithInitialSnapshot': len(self.connected),
                'expectedDeliveries': expected, 'uniqueDeliveries': received,
                'missingAtEnd': expected-received,
                'latencyMs': {'p50': percentile(.5), 'p95': percentile(.95), 'p99': percentile(.99)},
                'counters': dict(self.count),
                'scope': 'HTTP/SSE delivery only; not browser rendering, Flutter, or server CPU metrics. Latency includes request queueing. Unconfirmed sends are not assumed rejected.'}

    async def run(self):
        completed, failure = False, None
        try:
            # Five new streams/second at most; HTTP operations use global pacing.
            for index, user in enumerate(self.users):
                await self.connect(index, user)
                if (index+1) % 25 == 0:
                    print(f'Connected {index+1}/{len(self.users)}', flush=True)
                await asyncio.sleep(.2)
            self.sending.set()
            deadline = time.monotonic() + self.args.duration
            while time.monotonic() < deadline:
                await asyncio.sleep(min(10, max(0, deadline-time.monotonic())))
                print(f'live={len(self.live)} accepted={self.count["accepted_messages"]} errors={self.count["request_errors"]}', flush=True)
            # Stop sending, keep receiving for the final SSE snapshot recovery.
            self.stop.set()
            for task in self.tasks:
                if task.get_coro().__name__ == 'maintain':
                    task.cancel()
            senders = [t for t in self.tasks if t.get_coro().__name__ == 'sender']
            await asyncio.wait_for(asyncio.gather(*senders), 30)
            await asyncio.sleep(self.args.drain)
            completed = True
        except Exception as exc:
            failure = type(exc).__name__ + ': ' + str(exc)
        finally:
            self.stop.set()
            for task in self.tasks:
                task.cancel()
            await asyncio.gather(*self.tasks, return_exceptions=True)
            # Close streams first, then remove only our own community presence.
            for session, user in self.clients:
                await self.request(session, 'POST', '/api/communities/' + quote(user['room']) + '/leave', json={})
                await session.close()
            report = self.report(completed, failure)
            Path(self.args.report).write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
            print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if completed and self.count['accepted_messages'] and not report['missingAtEnd'] and not self.count['unconfirmed_sends'] and not self.count['cross_room_deliveries'] and not any(v for k, v in self.count.items() if k.startswith('http_') and int(k[5:]) >= 400) else 1


def arguments():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--prepare', action='store_true', help='Run inside gateway with production storage environment; creates test guests only')
    p.add_argument('--url', help='Production origin, e.g. https://your-domain.example')
    p.add_argument('--rooms', default='majlis,square,diwan,elite')
    p.add_argument('--per-room', type=int, default=150)
    p.add_argument('--duration', type=int, default=600, help='Sending seconds AFTER all users connect')
    p.add_argument('--min-interval', type=float, default=40)
    p.add_argument('--max-interval', type=float, default=80)
    p.add_argument('--rps', type=float, default=20, help='Global maximum REST requests/sec; does not bypass edge rate limits')
    p.add_argument('--drain', type=int, default=20)
    p.add_argument('--sessions', default='chat-load-sessions.json')
    p.add_argument('--report', default='chat-load-report.json')
    args = p.parse_args()
    args.rooms = [x.strip() for x in args.rooms.split(',') if x.strip()]
    if not args.rooms or len(args.rooms) != len(set(args.rooms)) or args.per_room < 1 or args.per_room > 200:
        p.error('Choose unique rooms and 1..200 users/room')
    if args.duration < 1 or args.min_interval < 1 or args.max_interval < args.min_interval or args.rps <= 0 or args.drain < 0:
        p.error('Invalid timing/rate arguments')
    if not args.prepare:
        u = urlsplit(args.url or '')
        if u.scheme not in ('http', 'https') or not u.netloc or u.username or u.password or u.query or u.fragment or u.path not in ('', '/'):
            p.error('--url must be an HTTP(S) origin without a path or credentials')
        args.url = args.url.rstrip('/')
    return args


async def main():
    args = arguments()
    if args.prepare:
        await prepare(args)
        return 0
    rows = json.loads(Path(args.sessions).read_text())
    users = []
    for room in args.rooms:
        group = [u for u in rows if u.get('room') == room][:args.per_room]
        if len(group) != args.per_room:
            raise ValueError('Not enough prepared sessions for ' + room)
        users.extend(group)
    if len({u['userId'] for u in users}) != len(users) or len({u['token'] for u in users}) != len(users):
        raise ValueError('Each virtual user must have a separate account and session')
    return await Load(args, users).run()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
