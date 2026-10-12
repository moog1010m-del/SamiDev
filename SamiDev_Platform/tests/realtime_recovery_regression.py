"""Real cross-gateway Redis loss, reconnect fencing and authority heartbeat recovery."""
import asyncio
import json
import time
import aiohttp
from realtime_cluster_fixture import Cluster, receive


async def main():
    cluster = Cluster()
    sockets = []
    try:
        await cluster.start()
        cookies = await cluster.seed(2)
        async with aiohttp.ClientSession() as session:
            for i in range(2):
                sockets.append(await session.ws_connect(cluster.urls[i]+'/ws', headers=cookies[i]))
            a, b = sockets
            await a.send_json({'type':'create_room','settings':{'gameId':'carrom','players':0,'live':1}})
            created = await receive(a, {'created'})
            rid = created['roomId']
            clients = await cluster.r.client_list()
            owner_listener = next(c for c in clients if c.get('name') == f'samidev:{cluster.prefix}r:node:{cluster.prefix}-0')
            await cluster.r.client_kill_filter(_id=owner_listener['id'])
            await b.send_json({'type':'join_room','roomId':rid})
            await receive(b, {'joined'})
            await receive(a, {'sync_required'})
            await a.send_json({'type':'ping','waiting':True})
            for ws in sockets: await receive(ws, {'start'})
            for ws in sockets: await ws.send_json({'type':'runtime_ready'})
            for ws in sockets: await receive(ws, {'begin_match'})
            # Kill precisely this fixture's subscriber, never every Redis subscriber.
            clients = await cluster.r.client_list()
            target = next(c for c in clients if c.get('name') == f'samidev:{cluster.prefix}r:node:{cluster.prefix}-1')
            started = time.monotonic()
            await cluster.r.client_kill_filter(_id=target['id'])
            await a.send_json({'type':'move','packet':{'n':0,'i':'recovery-start','m':{'m':0}}})
            await receive(a, {'move'})
            await receive(b, {'sync_required'})
            await b.send_json({'type':'resync'})
            recovered = await receive(b, {'resync_state'})
            assert recovered['sequence'][0] == 1
            assert recovered['turn'] == [0]
            recovery_ms = (time.monotonic()-started)*1000
            await b.send_json({'type':'ping','authority':True,'t':42})
            pong = await receive(b, {'pong'})
            assert pong['authority']['sequence'][0] == 1 and pong['authority']['turn'] == [0]
            assert 'snapshot' not in pong['authority'] and 'reveal' not in pong['authority']
            assert 'shard' not in pong['authority']
            # Rejoin on the other gateway: old generation is closed, new one acts.
            new = await session.ws_connect(cluster.urls[1]+'/ws', headers=cookies[0])
            sockets.append(new)
            await new.send_json({'type':'join_room','roomId':rid,'token':created['token']})
            joined = await receive(new, {'joined'})
            assert joined['connectionEpoch'] == 2
            await receive(new, {'start'})
            async with asyncio.timeout(5):
                while not a.closed:
                    message = await a.receive()
                    if message.type in {aiohttp.WSMsgType.CLOSE,aiohttp.WSMsgType.CLOSED}: break
            assert message.type == aiohttp.WSMsgType.CLOSE and message.data == 4001, message
            await new.send_json({'type':'move','packet':{'n':1,'i':'recovery-striker','m':{'m':6,'ps':.4}}})
            assert (await receive(new, {'move'}))['packet']['i'] == 'recovery-striker'
            assert (await receive(b, {'move'}))['packet']['i'] == 'recovery-striker'
            async with session.get(cluster.urls[1]+'/health') as response:
                assert response.status == 200 and (await response.json())['dependencies']['redisSubscription']
            print(json.dumps({'ok':True,'recoveryMs':round(recovery_ms,1),
                'checks':['authenticated Redis/PostgreSQL gateways','lost subscription reconnects',
                    'lost waiting/start notification recovered by direct room probe',
                    'missed move restored from live snapshot','public heartbeat invariants',
                    'cross-node reconnect fences old socket','new socket and peer receive next move'],
                'logs':str(cluster.folder)}))
    finally:
        for ws in sockets:
            if not ws.closed: await ws.close()
        await cluster.close()

asyncio.run(main())
