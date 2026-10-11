from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT/'game/platform/index.html').read_text('utf-8')
css = (ROOT/'game/platform/platform.css').read_text('utf-8')
js = (ROOT/'game/platform/platform.js').read_text('utf-8')

assert 'id="community-userbar"' not in html  # class, not duplicated id
assert 'class="community-userbar"' in html
for marker in ['community-self-profile','community-profile-page','community-profile-edit','room-theme-toggle','theme-toggle','auth-theme-toggle']:
    assert marker in html, marker
assert 'profile-card-back' not in html
assert 'html[data-theme="light"]' in css
assert 'body.community-mode .platform-topbar{display:none}' in css
assert '.community-layout{grid-template-columns:330px minmax(390px,1fr) 410px}' in css
assert "localStorage.setItem('samidev_theme'" in js
assert "document.body.classList.add('community-mode')" in js
assert "requestAnimationFrame(openProfileEditor)" in js
print('PLATFORM_UI_V18_PASS')
