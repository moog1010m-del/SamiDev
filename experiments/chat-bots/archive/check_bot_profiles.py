import asyncio, aiohttp, json, sys
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    b = json.load(open(r'C:\Users\Dev\.samidev\secrets\bot_sessions.json', encoding='utf-8'))
    for k, v in b.items():
        async with aiohttp.ClientSession(cookies={'samidev_session': v}) as s:
            async with s.get('http://127.0.0.1:56648/api/me') as r:
                data = await r.json()
                u = data.get('user', {})
                print(f"{k}: id={u.get('id')}, username={u.get('username')}, displayName={u.get('displayName')}, name={u.get('name')}")

asyncio.run(main())
