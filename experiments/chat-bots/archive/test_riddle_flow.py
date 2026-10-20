import asyncio, json, sys
from pathlib import Path
from core import Coordinator, Memory, Message, load_config

sys.stdout.reconfigure(encoding='utf-8')

cfg = load_config(r'C:\Users\Dev\Desktop\مجلد جديد (10)\SamiDev_V36\experiments\chat-bots\config.json')
mem = Memory(':memory:')
coord = Coordinator(cfg, mem, [])

print(f"Active bots count: {len(coord.active())}")
assert len(coord.active()) == 10

# Test choose alternation
s1 = coord.choose()
coord.sent(s1['id'])
s2 = coord.choose()
coord.sent(s2['id'])
s3 = coord.choose()
coord.sent(s3['id'])
print(f"Alternation check: {s1['id']} -> {s2['id']} -> {s3['id']}")
assert s1['id'] != s2['id']
assert s2['id'] != s3['id']

for m in [0, 1, 2]:
    print(f"\n--- Testing Mode {m} ---")
    coord.current_riddle = None
    coord.riddle_index = m
    r_start = coord.start_riddle()
    coord.sent(r_start.speaker)
    speakers = [r_start.speaker]
    for step in range(8):
        if not coord.current_riddle:
            print(f"Riddle ended at step {step}")
            break
        coord.current_riddle['next_stage_time'] = 0
        coord.last_sent = -1e9
        reply = coord.riddle_tick()
        if not reply:
            break
        print(f"Stage {step+1}: Speaker={reply.speaker}, Reason={reply.reason}, Text={reply.text[:40]}...")
        coord.sent(reply.speaker)
        speakers.append(reply.speaker)
    for i in range(len(speakers)-1):
        assert speakers[i] != speakers[i+1], f"Consecutive duplicate: {speakers[i]}"
    print("Sequence:", " -> ".join(speakers))
print("UNIT_TEST_PASS: Multi-persona rotation and riddle separation verified successfully!")
