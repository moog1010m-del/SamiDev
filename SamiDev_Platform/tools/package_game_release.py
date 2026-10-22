"""Build, verify and package protected games without publishing or changing sources."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import zipfile

from protect_game_release import ROOT, SOURCE, build


def main():
    output = ROOT / 'build/protected-game'
    for test in ('properties.test.cjs', 'pipeline.test.cjs'):
        subprocess.run(['node', str(ROOT/'tools/js-protection'/test)], check=True)
    build(output, realtime=True)
    subprocess.run([sys.executable, str(ROOT/'tests/protected_release.py'), str(output)], check=True)
    for path in SOURCE.rglob('*'):
        if path.is_file() and path.suffix.lower() in {'.png', '.webp', '.jpg', '.svg', '.atlas', '.mp3', '.ogg', '.wav'}:
            relative = path.relative_to(SOURCE)
            if path.read_bytes() != (output/relative).read_bytes():
                raise RuntimeError('Art/audio asset changed: '+str(relative))
    def runtime(test, directory):
        result = subprocess.run(['node', str(ROOT/'tests'/test)], cwd=ROOT,
                                env=dict(os.environ, SAMIDEV_GAME_DIR=str(directory)),
                                capture_output=True, text=True, timeout=180, check=True)
        print(result.stdout, flush=True)
        return result.stdout
    baseline = runtime('pool_runtime.js', SOURCE)
    protected = runtime('pool_runtime.js', output)
    def shot_ms(log):
        return next(json.loads(line)['localBreakMs'] for line in log.splitlines()
                    if line.startswith('{') and 'localBreakMs' in line)
    original_ms, protected_ms = shot_ms(baseline), shot_ms(protected)
    if protected_ms > max(100, original_ms*3):
        raise RuntimeError(f'Pool performance regression: {protected_ms:.1f}ms vs {original_ms:.1f}ms')
    for test in ('multigame_runtime.js', 'crazy8_runtime.js'):
        runtime(test, output)
    archive = ROOT / 'build/plazr-protected-games.zip'
    # The private seed/property report is a sibling of output and stays outside ZIP.
    temporary = archive.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temporary, 'w', compression=zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(output.rglob('*')):
            if path.is_file() and not path.name.startswith('.'):
                bundle.write(path, path.relative_to(output).as_posix())
    temporary.replace(archive)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n', encoding='utf-8')
    print('Verified release archive: '+str(archive))


if __name__ == '__main__':
    main()
