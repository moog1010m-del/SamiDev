"""Runtime release gate tests; audit vocabulary is deliberately not bundled."""
import importlib.util
from pathlib import Path
import tempfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('runtime_branding', ROOT/'tools/check_runtime_branding.py')
branding = importlib.util.module_from_spec(spec)
spec.loader.exec_module(branding)

result = branding.audit(ROOT/'game')
assert result['ok'], result['findings']
with tempfile.TemporaryDirectory() as directory:
    root = Path(directory)
    (root/'samidev-games.js').write_text('const uNodeWidth=48; // Copyright and license notices stay intact.\n')
    assert branding.audit(root)['ok']
    examples = [b'const title="Ocho";', b'const title="\\u0050lato";', b'const title="%50lato";',
                'title: أُوتشو'.encode(), 'PLATO'.encode('utf-16le')]
    for payload in [*examples, 'أوتشـو'.encode()]:
        path = root/'metadata.json';path.write_bytes(payload)
        assert not branding.audit(root)['ok'], payload
        assert path.read_bytes()==payload, 'Audit must never silently rewrite source'
        path.unlink()
    path = root/'ocho-old.json';path.write_text('{}');assert not branding.audit(root)['ok'];path.unlink()
    original = ROOT/'game/games/pool/scene-ui/ShopWidget/shop_widget_coin.webp'
    shared = ROOT/'game/scene-ui/ShopWidget/shop_widget_coin.webp'
    assert original.read_bytes()==shared.read_bytes(), 'Keep the reviewed same-size project currency icon'
print(f"PASS: {result['filesScanned']} runtime files; escaped/UTF-16/path markers block; shader uniforms and notices preserved; currency artwork matches project asset")
