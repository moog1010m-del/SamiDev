from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
platform=(ROOT/'game/platform/platform.js').read_text('utf-8')
css=(ROOT/'game/platform/platform.css').read_text('utf-8')
chat=(ROOT/'game/chat-ui.js').read_text('utf-8')
runtime=(ROOT/'game/browser-runtime.js').read_text('utf-8')
profile=(ROOT/'game/player-profile-ui.js').read_text('utf-8')
avatar=ROOT/'game/images/default-avatar.png'

assert avatar.is_file(), 'default avatar asset missing'
with Image.open(avatar) as im:
    assert im.size == (320,320), im.size
    assert im.format == 'PNG', im.format

assert "const DEFAULT_AVATAR_URL='/images/default-avatar.png'" in platform
assert 'community-member-title' in platform and 'community-member-stars' in platform
assert 'profile-sprite-emblem community-member-emblem' in platform
assert 'فوز ${formatProfileStat(u.wins)}' in platform
assert 'سمعة ${formatProfileStat(u.reputation)}' in platform
assert 'wireAvatarImages(box);' in platform
assert '.community-member-copy{display:flex' in css, 'mobile connected list compact row missing'
assert '.community-layout{grid-template-columns:330px' in css, 'desktop members panel not widened'
assert "const DEFAULT_AVATAR_URL = '/images/default-avatar.png';" in chat
assert 'sd-chat-avatar img' in chat
assert "return await fetchImage('/images/default-avatar.png');" in runtime
assert "const cacheKey = id || '__samidev_default_avatar__';" in runtime
assert "const DEFAULT_AVATAR_URL = '/images/default-avatar.png';" in profile
assert 'onerror=' not in profile, 'inline image error handler should not be used'
print('PASS community members + unified avatar V16 regression')
