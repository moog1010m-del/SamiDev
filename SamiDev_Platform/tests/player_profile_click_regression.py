from pathlib import Path
root=Path(__file__).resolve().parents[1]
main=(root/'game/main.js').read_text('utf-8',errors='replace')
runtime=(root/'game/browser-runtime.js').read_text('utf-8',errors='replace')
ui=(root/'game/player-profile-ui.js').read_text('utf-8',errors='replace')

# Native game owns the avatar interaction. Keep the original handler and add a
# dedicated large native hit node because ImageNode's exact circle hit area is
# unreliable in the web build/layout.
assert 's.onTap(o._onImageTap.bind(o))' in main
assert 'SamiDev.showProfile(this.seat)' in main
assert 'o.profileTapTarget=new lc.Node' in main
assert 'o.profileTapTarget.resize(180,180)' in main
assert 'o.profileTapTarget.onDrag(function(v,g){g&&g.status==="end"&&o._onImageTap()})' in main
assert 'o.addChild(o.profileTapTarget)' in main

# Host bridge must forward the native callback into the real social profile UI.
assert 'showProfile:(seat)=>' in runtime
assert 'window.SamiDevPlayerProfileUI?.openSeat?.(seat)' in runtime
assert "type:'open_player_profile',userId:player.accountId" in runtime
assert 'openSeat' in ui

# Old external geometry overlays must stay removed.
assert 'updateAvatarTargets' not in ui
assert 'sdpp-avatar-target' not in ui
print('player profile native hit-target regression: OK')
