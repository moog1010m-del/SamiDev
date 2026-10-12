"""Isolated local PostgreSQL/Redis gateways; never restart shared/production services."""
import asyncio
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import sys
import tempfile
from urllib.parse import urlparse

import aiohttp
import asyncpg
import redis.asyncio as redis

ROOT = Path(__file__).resolve().parents[1]


def port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class Cluster:
    def __init__(self, gateways=2, hosts=1):
        self.db = os.environ['SAMIDEV_TEST_DATABASE_URL']
        self.redis_url = os.environ['SAMIDEV_TEST_REDIS_URL']
        assert urlparse(self.db).hostname in {'127.0.0.1', 'localhost'}
        assert urlparse(self.redis_url).hostname in {'127.0.0.1', 'localhost'}
        self.prefix = 'rtfix' + secrets.token_hex(6)
        self.secret = secrets.token_urlsafe(32)
        self.urls = [f'http://127.0.0.1:{port()}' for _ in range(gateways)]
        self.hosts = [f'http://127.0.0.1:{port()}' for _ in range(hosts)]
        self.processes = []
        self.logs = []
        self.folder = Path(tempfile.mkdtemp(prefix='samidev-realtime-'))
        self.r = redis.from_url(self.redis_url, decode_responses=True)
        self.base_headers = {'Origin': 'https://game.example.test', 'X-Forwarded-Proto': 'https'}

    async def start(self):
        env = dict(os.environ, SAMIDEV_PRODUCTION='1', SAMIDEV_REQUIRE_GAME_AUTH='1',
            SAMIDEV_STORE='redis', SAMIDEV_PLATFORM_STORE='postgres',
            SAMIDEV_DATABASE_URL=self.db, SAMIDEV_REDIS_URL=self.redis_url,
            SAMIDEV_PLATFORM_PREFIX=self.prefix, SAMIDEV_REALTIME_PREFIX=self.prefix+'r',
            SAMIDEV_GAMEHOST_SERVICE_KEY=self.secret, SAMIDEV_ALLOWED_ORIGINS='https://game.example.test',
            SAMIDEV_TRUST_PROXY='1', SAMIDEV_GAMEHOST_URLS=','.join(self.hosts),
            SAMIDEV_ADMIN_USERNAME='', SAMIDEV_ADMIN_PASSWORD='')
        # Fixture source addresses are distinct simulated clients. Production rate
        # limits remain enabled; no anonymous authentication bypass is used.
        for i, url in enumerate(self.hosts):
            await self.spawn(['node', str(ROOT/'gamehost/server.js')], dict(env,
                SAMIDEV_GAMEHOST_HOST='127.0.0.1', SAMIDEV_GAMEHOST_PORT=str(urlparse(url).port)), f'host-{i}')
        await self.ready(self.hosts)
        for i, url in enumerate(self.urls):
            await self.spawn([sys.executable, str(ROOT/'backend/app.py')], dict(env,
                SAMIDEV_HOST='127.0.0.1', SAMIDEV_PORT=str(urlparse(url).port), SAMIDEV_NODE_ID=self.prefix+f'-{i}'), f'gateway-{i}')
        await self.ready(self.urls)

    async def spawn(self, command, env, label):
        handle = (self.folder/(label+'.log')).open('w')
        proc = await asyncio.create_subprocess_exec(*command, cwd=ROOT, env=env, stdout=handle, stderr=handle)
        self.processes.append(proc)
        self.logs.append(handle)

    async def ready(self, urls):
        async with aiohttp.ClientSession() as session:
            for url in urls:
                async with asyncio.timeout(45):
                    while True:
                        try:
                            async with session.get(url+'/health') as response:
                                if response.status == 200: break
                        except (aiohttp.ClientError, OSError): pass
                        if any(p.returncode is not None for p in self.processes):
                            raise RuntimeError(f'fixture process exited; logs: {self.folder}')
                        await asyncio.sleep(.1)

    async def seed(self, count):
        """Existing-account load: seed fixtures, then use real session validation.

        Registration/password hashing is intentionally outside the realtime benchmark.
        Fixture hashes cannot be used to log in through the password endpoint.
        """
        conn = await asyncpg.connect(self.db)
        records, cookies = [], []
        pipe = self.r.pipeline(transaction=False)
        try:
            for i in range(count):
                uid = f'{self.prefix}_{i}'
                user = dict(id=uid, username=uid, usernameLower=uid.lower(), displayName=f'Load {i}',
                    passwordHash='disabled-load-fixture', role='user', banned='0', authVersion='0',
                    createdAt='0', starsCount='0', coins='0', wins='0', reputation='0')
                records.append((f'{self.prefix}:user:{uid}', json.dumps(user)))
                token = secrets.token_urlsafe(32)
                key = hashlib.sha256(token.encode()).hexdigest()
                pipe.set(f'{self.prefix}:session:{key}', json.dumps({'uid':uid,'version':'0'}), ex=3600)
                cookies.append({'Cookie':'samidev_session='+token, **self.base_headers,
                    'X-Real-IP':f'10.{i//65536%256}.{i//256%256}.{i%256}'})
            await conn.executemany("INSERT INTO samidev_social_documents(key,kind,value) VALUES($1,'hash',$2::jsonb)", records)
            await pipe.execute()
        finally: await conn.close()
        return cookies

    async def close(self):
        for proc in reversed(self.processes):
            if proc.returncode is None: proc.terminate()
        for proc in reversed(self.processes):
            try: await asyncio.wait_for(proc.wait(), 5)
            except TimeoutError: proc.kill(); await proc.wait()
        for handle in self.logs: handle.close()
        conn = await asyncpg.connect(self.db)
        try: await conn.execute('DELETE FROM samidev_social_documents WHERE key LIKE $1', self.prefix+':%')
        finally: await conn.close()
        keys = [key async for key in self.r.scan_iter(match=self.prefix+'*')]
        if keys: await self.r.delete(*keys)
        await self.r.aclose()


async def receive(ws, wanted, timeout=15):
    async with asyncio.timeout(timeout):
        while True:
            packet = await ws.receive_json()
            if packet.get('type') == 'error': raise AssertionError(packet)
            if packet.get('type') in wanted: return packet
