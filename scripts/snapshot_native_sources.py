"""Archive only source files that still match a native run's recorded hashes."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ALLOWED = {'native_service.py', 'native_experiment.py', 'live_monitor.py', 'raw_telemetry.py'}


def snapshot(run_id):
    import re
    if not re.fullmatch(r'\d{8}T\d{6}-[0-9a-f]{6}', run_id):
        raise ValueError('Invalid run identifier')
    directory = ROOT/'artifacts/live'/run_id
    manifest = json.loads((directory/'source.json').read_text())
    sources = manifest['code_sha256']
    if not set(sources).issubset(ALLOWED):
        raise ValueError('Unexpected source name')
    for name, expected in sources.items():
        raw = (ROOT/'incidentlab'/name).read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValueError(f'{name} changed; cannot honestly reconstruct this historical source snapshot')
    target = directory/'source_snapshot'
    target.mkdir(exist_ok=True)
    for name in sources:
        (target/name).write_bytes((ROOT/'incidentlab'/name).read_bytes())
    print(f'Archived matching source files: {target}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('run_id')
    snapshot(parser.parse_args().run_id)
