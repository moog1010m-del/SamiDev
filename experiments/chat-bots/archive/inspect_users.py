import asyncio, asyncpg, json, sys
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/samidev')
    rows = await conn.fetch('''
        SELECT id, doc->>'username' as username, doc->>'name' as name, doc->>'displayName' as display_name
        FROM samidev_social_documents
        WHERE collection = 'users'
    ''')
    for r in rows:
        u = r['username'] or ''
        if any(b in u for b in ['x7v', 'r9k', 'v3m', 'z8q', 'k5l', 'f9x', 'd7w', 'b4y', 'm9s', 't2r']):
            print(f"ID: {r['id']} | Username: {r['username']} | Name: {r['name']} | Display: {r['display_name']}")
    await conn.close()

asyncio.run(main())
