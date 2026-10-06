"""Hash local code, manifests and deployable checkpoints without touching held-out raw data."""
import hashlib
import json
import platform
from importlib.metadata import version
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
paths=list((ROOT/'incidentlab').glob('*.py'))+list((ROOT/'scripts').glob('*.py'))
paths += [ROOT/'data/processed/multimodal/split_manifest.json',
          ROOT/'data/processed/rcaeval/split_manifest.json']
paths += list((ROOT/'artifacts/research').glob('*.pt'))+list((ROOT/'artifacts/research').glob('*.joblib'))
report=dict(python=platform.python_version(),packages={p:version(p) for p in
            ['torch','numpy','pyarrow','scikit-learn','fastapi','uvicorn']},
            files={p.relative_to(ROOT).as_posix():dict(bytes=p.stat().st_size,
                   sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in sorted(paths)},
            scope='Local snapshot; processed file contents and raw provenance are separate audits')
(ROOT/'artifacts/research/experiment_snapshot.json').write_text(json.dumps(report,indent=2))
print(f'Frozen {len(paths)} source/manifest/checkpoint hashes; external final data not read.')
