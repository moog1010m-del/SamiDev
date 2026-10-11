from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
html=(ROOT/'game/platform/index.html').read_text(encoding='utf-8')
js=(ROOT/'game/platform/platform.js').read_text(encoding='utf-8')
for token in ['id="room-filter"','id="room-mode"','id="stat-rooms"','id="stat-waiting"','id="stat-playing"','id="stat-seats"']:
    assert token not in html, token
for token in ["$('#room-filter')","$('#room-mode')","$('#stat-rooms')","$('#stat-waiting')","$('#stat-playing')","$('#stat-seats')"]:
    assert token not in js, token
assert 'const rooms=state.rooms;' in js
assert 'id="rooms"' in html
print('community rooms V17 cleanup regression: OK')
