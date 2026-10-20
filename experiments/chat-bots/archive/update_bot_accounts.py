import asyncio, asyncpg, json, redis, sys
sys.stdout.reconfigure(encoding='utf-8')

new_handles = {
    'BbFUgoVkL-n5H_yi': 'x7v',    # 3 chars (THE ONLY 3-character handle)
    'EPQ0mScktyP8LKnA': 'r9kx',   # 4 chars
    '-BAZYVCRzKXi4AX7': 'v3mk',   # 4 chars
    '-GIXXuW4rKjMQVAj': 'z8qx',   # 4 chars
    '-NyFs95RMe1qlupO': 'k5lp',   # 4 chars
    '0FaPqvA05EUXyxLe': 'f9xr',   # 4 chars
    '0ouPhIKYBcH-dqH0': 'd7wsx',  # 5 chars
    '10w2SBukmsUAPpVf': 'b4yqz',  # 5 chars
    '1YNPETfzIHhx5lxB': 'm9sra',  # 5 chars
    '2UsXrn59VnAKGe7B': 't2rnx'   # 5 chars
}

async def main():
    conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/samidev')
    r = redis.Redis(host='127.0.0.1', port=6379, db=0)

    # 1. Fetch current user documents
    for uid, handle in new_handles.items():
        user_key = f'sdp:user:{uid}'
        row = await conn.fetchrow('SELECT value FROM samidev_social_documents WHERE key = $1', user_key)
        if not row:
            print(f'User not found: {uid}')
            continue
        val = json.loads(row['value'])
        old_username = val.get('username')
        old_lower = val.get('usernameLower') or (old_username.lower() if old_username else '')

        # Update fields: NO ARABIC NAMES ANYWHERE!
        val['username'] = handle
        val['usernameLower'] = handle.lower()
        val['displayName'] = handle
        val['name'] = handle
        if 'real_name' in val: del val['real_name']
        if 'realName' in val: del val['realName']

        # Update PostgreSQL
        await conn.execute('UPDATE samidev_social_documents SET value = $1 WHERE key = $2', json.dumps(val), user_key)

        # Delete old username key if changed
        if old_lower and old_lower != handle.lower():
            await conn.execute('DELETE FROM samidev_social_documents WHERE key = $1', f'sdp:username:{old_lower}')
            r.delete(f'sdp:username:{old_lower}')

        # Insert new username key
        await conn.execute('''
            INSERT INTO samidev_social_documents(key, kind, value)
            VALUES($1, 'string', $2)
            ON CONFLICT (key) DO UPDATE SET value = excluded.value
        ''', f'sdp:username:{handle.lower()}', json.dumps(uid))

        r.set(f'sdp:username:{handle.lower()}', uid)
        print(f"Updated user {uid}: {old_username} -> {handle} (len: {len(handle)})")

    await conn.close()
    print("Database updates complete!")

asyncio.run(main())
