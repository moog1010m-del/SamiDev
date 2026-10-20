import asyncio, aiohttp, json, sys
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    b = json.load(open(r'C:\Users\Dev\.samidev\secrets\bot_sessions.json', encoding='utf-8'))
    tok = b['PLAZR_BOT_X7V_SESSION']
    async with aiohttp.ClientSession(cookies={'samidev_session': tok}) as s:
        async with s.get('http://127.0.0.1:56648/api/communities/majlis?chat=15') as r:
            data = await r.json()
            msgs = data.get('messages', [])
            print(f"Total messages returned: {len(msgs)}")
            for m in msgs[-10:]:
                handle = m.get('username') or m.get('displayName') or m.get('userId')
                print(f"[{handle}] {m.get('text')}")

asyncio.run(main())
