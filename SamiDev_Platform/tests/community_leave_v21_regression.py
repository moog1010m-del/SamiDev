from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
html = (ROOT / "game/platform/index.html").read_text(encoding="utf-8")
js = (ROOT / "game/platform/platform.js").read_text(encoding="utf-8")
backend = (ROOT / "backend/social_platform.py").read_text(encoding="utf-8")
app = (ROOT / "backend/app.py").read_text(encoding="utf-8")

assert 'id="exit-community"' in html
assert "exitCommunity.onclick=leaveCommunity" in js
assert "/leave`,{method:'POST'" in js
assert "async def leave_community" in backend
assert "async def community_leave" in backend
assert '/api/communities/{community_id}/leave' in app
assert "p.srem(self.k_community_members(target), uid)" in backend
assert "p.delete(active_key)" in backend
print("community_leave_v21_regression: OK")
