"""Real SSE disconnect/reconnect must trigger recovery, not silently lose a turn."""
import asyncio
import json
import sys
from pathlib import Path
from aiohttp import web
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'backend'))
from gamehost_client import GameHostClient


async def main():
    subscriptions = 0
    reconnected = asyncio.Event()
    received = asyncio.Event()
    async def events(request):
        nonlocal subscriptions
        subscriptions += 1
        response = web.StreamResponse(headers={'Content-Type':'text/event-stream'})
        await response.prepare(request)
        await response.write(b'data: {"type":"hello"}\n\n')
        if subscriptions == 1:
            # Lost transport; the intervening state cannot be replayed by SSE.
            request.transport.close()
        else:
            await response.write(b'data: {"type":"authority_state","turn":[1],"sequence":[1,0]}\n\n')
            await asyncio.sleep(1)
        return response
    app = web.Application()
    app.router.add_get('/health', lambda request:web.json_response({'ok':True}))
    app.router.add_get('/events', events)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner,'127.0.0.1',0)
    await site.start()
    client = GameHostClient(f'http://127.0.0.1:{site._server.sockets[0].getsockname()[1]}')
    async def on_reconnect(): reconnected.set()
    async def on_event(event):
        assert event['turn'] == [1]
        received.set()
    client.on_reconnect = on_reconnect
    try:
        await client.start(on_event)
        await asyncio.wait_for(reconnected.wait(),5)
        await asyncio.wait_for(received.wait(),5)
        assert any(client.event_connected.values())
        print(json.dumps({'ok':True,'subscriptions':subscriptions,'lostSseConnectionTriggersRecovery':True}))
    finally:
        await client.close()
        await runner.cleanup()

asyncio.run(main())
