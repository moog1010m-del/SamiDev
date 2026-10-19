"""Create a separate protected distribution tree; never mutate source engines.

Install tools/js-protection dependencies with npm ci --ignore-scripts first.
The same output must serve the backend and supply the Flutter runtime bundle.
"""
import argparse, hashlib, importlib.util, json, shutil, subprocess
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'game'
ENGINES = {'carrom': 'main.js', 'pool': 'games/pool/main.js',
           'crazy8': 'games/crazy8/main.js', 'tablesoccer': 'games/tablesoccer/main.js'}

def build(output):
    output = Path(output).resolve()
    if output == SOURCE or output in SOURCE.parents or SOURCE in output.parents:
        raise ValueError('Distribution must be separate from the source game tree')
    package = ROOT/'tools/js-protection/node_modules/javascript-obfuscator/package.json'
    if not package.is_file():
        raise RuntimeError('Run npm ci --ignore-scripts in tools/js-protection first')
    if json.loads(package.read_text())['version'] != '4.1.1':
        raise RuntimeError('Unexpected obfuscator version; restore dependencies with npm ci --ignore-scripts')
    marker = output / '.plazr-generated-distribution'
    if output.exists():
        if not marker.is_file():
            raise ValueError('Refusing to replace an output directory without the generation marker')
        shutil.rmtree(output)
    shutil.copytree(SOURCE, output, ignore=shutil.ignore_patterns('*.map', '.*'))
    marker.touch()
    digest = lambda p, algorithm='sha256': hashlib.new(algorithm, p.read_bytes()).hexdigest()
    report = {'tool': 'javascript-obfuscator@4.1.1', 'profile': 'local-identifiers-v1', 'engines': {}}
    for game, relative in ENGINES.items():
        path = output/relative
        subprocess.run(['node', str(ROOT/'tools/js-protection/protect.cjs'), str(path)], check=True)
        subprocess.run(['node', '--check', str(path)], check=True, capture_output=True)
        report['engines'][game] = {'sourceSha256': digest(SOURCE/relative), 'sha256': digest(path),
                                 'sourceBytes': (SOURCE/relative).stat().st_size, 'bytes': path.stat().st_size}
        index = path.parent/'__assets.json'
        data = json.loads(index.read_text())
        for name in data:
            data[name] = digest(path.parent/name.removeprefix(game+'/'), 'sha1')
        index.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    integrity = json.loads((output/'samidev-integrity.json').read_text())
    for game, relative in ENGINES.items():
        integrity['games'][game]['sha256'] = digest(output/relative)
    (output/'samidev-integrity.json').write_text(json.dumps(integrity, indent=2)+'\n')
    # Regenerate the worker contract from the protected bytes, not original bytes.
    spec = importlib.util.spec_from_file_location('release_asset_cache', ROOT/'tools/build_asset_cache.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.GAME = output; module.build()
    path = output/'platform/build.json'; data = json.loads(path.read_text())
    data['files'] = {name: digest(output/name) for name in data['files']}
    data['buildId'] = 'plazr-protected-'+hashlib.sha256(json.dumps(data['files'],sort_keys=True).encode()).hexdigest()[:16]
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    for game, relative in ENGINES.items():
        path = (output/relative).parent/'attestation.json'
        data = json.loads(path.read_text()); data['signed'] = False
        data['files'] = {name: digest(path.parent/name) for name in data['files']}
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n')
    report_path = output.parent/(output.name+'-protection-report.json')
    report_path.write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps({'output': str(output), 'report': str(report_path), 'engines': len(ENGINES)}))
    return output

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/protected-game')
    build(parser.parse_args().output)
