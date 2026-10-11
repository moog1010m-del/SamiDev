from pathlib import Path
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
ASSET=ROOT/'game/platform/assets/profile/raster'
expected={
 'palm-swords.webp':(320,320),
 'reputation-flame.webp':(256,256),
 'star.webp':(192,192),
 'trophy.webp':(256,256),
 'prestige.webp':(256,256),
}
for name,size in expected.items():
 p=ASSET/name
 assert p.is_file(), name
 im=Image.open(p)
 assert im.size==size,(name,im.size)
 assert 'A' in im.getbands(),(name,im.mode)
 assert im.getchannel('A').getextrema()==(0,255),name
css=(ROOT/'game/platform/platform.css').read_text('utf-8')
js=(ROOT/'game/player-profile-ui.js').read_text('utf-8')
for name in ['palm-swords.webp','reputation-flame.webp','star.webp','trophy.webp']:
 assert name in css,name
 assert name in js,name
for sel in ['#profile-user','.lobby-profile-handle','.community-public-profile-handle','.community-user-copy small','.community-member-meta','.community-chat-profile-name']:
 assert sel in css,sel
assert 'color:#111111!important' in css
print('profile_raster_assets_v22_regression: OK')
