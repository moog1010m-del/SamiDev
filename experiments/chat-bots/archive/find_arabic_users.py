import asyncio, asyncpg, json, re, sys
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/samidev')
    rows = await conn.fetch('''
        SELECT key, value->>'username' as username, value->>'displayName' as display_name
        FROM samidev_social_documents
        WHERE key LIKE 'sdp:user:%'
    ''')
    arabic_count = 0
    for r in rows:
        u = r['username'] or ''
        d = r['display_name'] or ''
        if re.search(r'[\u0600-\u06ff]', u) or re.search(r'[\u0600-\u06ff]', d):
            arabic_count += 1
            if arabic_count <= 25:
                print(f"{r['key']}: username='{u}', displayName='{d}'")
    print(f"Total users with Arabic in username or displayName: {arabic_count}")
    await conn.close()

asyncio.run(main())
