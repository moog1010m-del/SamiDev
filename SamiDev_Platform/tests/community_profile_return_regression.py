from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
platform_js = (ROOT / 'game/platform/platform.js').read_text('utf-8')
platform_html = (ROOT / 'game/platform/index.html').read_text('utf-8')
profile_js = (ROOT / 'game/player-profile-ui.js').read_text('utf-8')
room_menu = (ROOT / 'game/room-menu.js').read_text('utf-8')
network_js = (ROOT / 'game/samidev-network.js').read_text('utf-8')

# Full public profile is part of community-room UI, not the compact lobby card.
for token in [
    'community-profile-modal',
    'community-profile-avatar-image',
    'community-profile-since',
    'community-profile-wins',
    'community-profile-reputation',
    'community-profile-friend',
    'community-profile-reputation-btn',
    'community-profile-report',
]:
    assert token in platform_html, token

assert "data-public-profile" in platform_js
assert "/api/public-profile/" in platform_js
assert "openCommunityProfile" in platform_js
assert "communityProfileFriendAction" in platform_js
assert "communityProfileReputationAction" in platform_js
assert "communityProfileReportAction" in platform_js

# Community identity survives entering a game and is restored on return.
assert "samidev_return_community" in platform_js
assert "restoreCommunityFromLocation" in platform_js
assert "communityId: null" in network_js
assert "state.communityId = msg.communityId" in network_js
assert "samidev_return_community" in network_js
assert "returnToCommunity" in profile_js
assert "/platform/?community=" in profile_js
assert "platformReturnUrl" in room_menu
assert "/platform/?community=" in room_menu

print('COMMUNITY_PROFILE_RETURN_REGRESSION_PASS')
