"""Regenerate SamiDev's unsigned integrity inventory after an intentional build."""
from pathlib import Path
import hashlib,json
ROOT=Path(__file__).resolve().parent.parent
games={"carrom":ROOT/"game", "tablesoccer":ROOT/"game/games/tablesoccer", "crazy8":ROOT/"game/games/crazy8", "pool":ROOT/"game/games/pool"}
manifest={"publisher":"SamiDev", "algorithm":"sha256", "games":{}}
for gid,directory in games.items():
    digest=hashlib.sha256((directory/"main.js").read_bytes()).hexdigest()
    manifest["games"][gid]={"sha256":digest,"main":str((directory/"main.js").relative_to(ROOT/"game"))}
    files={}
    for p in sorted(directory.rglob('*')):
        if not p.is_file() or (gid=="carrom" and 'games' in p.relative_to(directory).parts):continue
        if p.name in {'attestation.json','samidev-integrity.json','__assets.json'}:continue
        files[str(p.relative_to(directory))]=hashlib.sha256(p.read_bytes()).hexdigest()
    (directory/"attestation.json").write_text(json.dumps({"publisher":"SamiDev","algorithm":"sha256","signed":False,"files":files},indent=2)+"\n")
(ROOT/"game/samidev-integrity.json").write_text(json.dumps(manifest,indent=2)+"\n")
print(json.dumps(manifest,indent=2))
