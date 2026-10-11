from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
js = (ROOT / 'game/platform/platform.js').read_text('utf-8')
css = (ROOT / 'game/platform/platform.css').read_text('utf-8')

# The current account must not be rendered in the community members list.
assert 'function visibleCommunityMembers()' in js
assert "String(u?.id||'')!==selfId" in js
assert 'const members=visibleCommunityMembers();' in js
assert "community-member-count').textContent=String(visibleCommunityMembers().length)" in js

# Desktop rooms use roster-backed horizontal rows, while mobile keeps cards.
for token in ['function roomSeatsMarkup(r)', 'room-player-slot', 'room-game-identity', 'room-desktop-state', 'room-mobile-meta']:
    assert token in js or token in css, token
assert '@media(min-width:821px)' in css
assert 'grid-template-areas:"action state roster identity"' in css
assert '@media(max-width:820px)' in css
assert '.room-game-identity,.room-roster,.room-desktop-state{display:none}' in css

print('LOBBY_ROOMS_V15_REGRESSION_PASS')
