"""Verify publication hashes and CPU replay; no training or raw downloads."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
manifest=json.loads((ROOT/'repository_manifest.json').read_text(encoding='utf-8'))
for name,digest in manifest['files'].items():
    p=(ROOT/name).resolve()
    if not p.is_relative_to(ROOT) or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=digest:
        raise ValueError('Publication file missing or changed: '+name)
from scripts.verify_laptop import verify
result=verify()
result['repository_files_verified']=len(manifest['files'])
print(json.dumps(result,indent=2))
