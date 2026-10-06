"""Refresh the explicit publication inventory after intentional source edits."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'repository_manifest.json'
manifest=json.loads(p.read_text(encoding='utf-8'))
names=set(manifest['files'])|{'.gitattributes','scripts/refresh_repository_manifest.py'}
manifest['files']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sorted(names)}
p.write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('Publication file hashes refreshed.')
