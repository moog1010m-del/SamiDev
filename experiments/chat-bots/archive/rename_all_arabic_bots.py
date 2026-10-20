import asyncio, asyncpg, json, random, re, redis, sys
sys.stdout.reconfigure(encoding='utf-8')

# Pool of consonants and letters for sleek gaming handles
letters = 'abcdefghijklmnopqrstuvwxyz'
digits = '23456789'

def generate_handle(length, existing_set):
    for _ in range(1000):
        # Patterns: l-d-l-l, l-l-d-l, l-d-d-l, l-l-l-d, etc.
        if length == 4:
            pattern = random.choice([
                (letters, digits, letters, letters),
                (letters, letters, digits, letters),
                (letters, digits, digits, letters),
                (letters, letters, letters, digits),
                (letters, digits, letters, digits)
            ])
            h = ''.join(random.choice(pool) for pool in pattern)
        else: # 5
            pattern = random.choice([
                (letters, digits, letters, letters, letters),
                (letters, letters, digits, letters, letters),
                (letters, letters, letters, digits, letters),
                (letters, digits, letters, digits, letters),
                (letters, letters, digits, digits, letters)
            ])
            h = ''.join(random.choice(pool) for pool in pattern)
        if h not in existing_set:
            existing_set.add(h)
            return h
    raise RuntimeError("Failed to generate unique handle")

async def main():
    conn = await asyncpg.connect('postgresql://postgres:postgres@localhost:5432/samidev')
    r = redis.Redis(host='127.0.0.1', port=6379, db=0)

    # 1. Fetch all existing usernames to avoid collisions
    all_users = await conn.fetch('''
        SELECT key, value->>'username' as username, value->>'displayName' as display_name
        FROM samidev_social_documents
        WHERE key LIKE 'sdp:user:%'
    ''')
    
    existing = set()
    targets = []
    
    for row in all_users:
        u = row['username'] or ''
        d = row['display_name'] or ''
        existing.add(u.lower())
        # Check if Arabic or transliterated Arabic like nada_k, reham_s
        is_arabic = bool(re.search(r'[\u0600-\u06ff]', u) or re.search(r'[\u0600-\u06ff]', d))
        # Don't touch our active chat bots or admin/user accounts
        if row['key'] in [
            'sdp:user:BbFUgoVkL-n5H_yi', # x7v
            'sdp:user:EPQ0mScktyP8LKnA', # r9kx
            'sdp:user:-BAZYVCRzKXi4AX7', # v3mk
            'sdp:user:-GIXXuW4rKjMQVAj', # z8qx
            'sdp:user:-NyFs95RMe1qlupO', # k5lp
            'sdp:user:0FaPqvA05EUXyxLe', # f9xr
            'sdp:user:0ouPhIKYBcH-dqH0', # d7wsx
            'sdp:user:10w2SBukmsUAPpVf', # b4yqz
            'sdp:user:1YNPETfzIHhx5lxB', # m9sra
            'sdp:user:2UsXrn59VnAKGe7B', # t2rnx
        ]:
            continue
            
        if is_arabic:
            targets.append(row)

    print(f"Found {len(targets)} bot accounts to rename to 4-char and 5-char gaming handles.")

    # Distribute targets evenly between 4-char and 5-char handles
    random.seed(42)
    updated_count = 0

    for i, target in enumerate(targets):
        user_key = target['key']
        uid = user_key.split(':')[-1]
        
        # Decide length: 4 or 5 chars
        target_len = 4 if i % 2 == 0 else 5
        new_handle = generate_handle(target_len, existing)
        
        row_doc = await conn.fetchrow('SELECT value FROM samidev_social_documents WHERE key = $1', user_key)
        val = json.loads(row_doc['value'])
        old_u = val.get('username', '')
        old_lower = val.get('usernameLower', old_u.lower())
        
        val['username'] = new_handle
        val['usernameLower'] = new_handle.lower()
        val['displayName'] = new_handle
        val['name'] = new_handle
        val['bio'] = f"Gamer | {new_handle}"
        if 'real_name' in val: del val['real_name']
        if 'realName' in val: del val['realName']

        # Update in PostgreSQL
        await conn.execute('UPDATE samidev_social_documents SET value = $1 WHERE key = $2', json.dumps(val), user_key)

        # Delete old username mapping
        if old_lower:
            await conn.execute('DELETE FROM samidev_social_documents WHERE key = $1', f'sdp:username:{old_lower}')
            r.delete(f'sdp:username:{old_lower}')

        # Add new username mapping
        await conn.execute('''
            INSERT INTO samidev_social_documents(key, kind, value)
            VALUES($1, 'string', $2)
            ON CONFLICT (key) DO UPDATE SET value = excluded.value
        ''', f'sdp:username:{new_handle.lower()}', json.dumps(uid))
        r.set(f'sdp:username:{new_handle.lower()}', uid)

        updated_count += 1
        if updated_count <= 10 or updated_count % 50 == 0:
            print(f"[{updated_count}/{len(targets)}] {old_u} -> {new_handle} (len: {len(new_handle)})")

    await conn.close()
    print(f"SUCCESS: Renamed all {updated_count} accounts to sleek 4-char and 5-char gaming handles!")

asyncio.run(main())
