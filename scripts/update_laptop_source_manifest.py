"""Record deliberate local runtime amendments without rewriting transferred evidence."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    original=json.loads((ROOT/'handoff_manifest.json').read_text())['files']
    amendments={}
    for name,entry in original.items():
        path=ROOT/name
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        if digest==entry['sha256']:continue
        source=(name.startswith(('incidentlab/','scripts/','Setup-Laptop.ps1')) and name.endswith(('.py','.ps1')))
        web=name.startswith('web/') and name.endswith(('.html','.js','.css'))
        if not (source or web):raise ValueError('Unexpected evidence change: '+name)
        amendments[name]=dict(original_sha256=entry['sha256'],sha256=digest)
    value=dict(format='incidentlab-laptop-source-amendments-v1',
        reason='Measured HTTP framing fix and authorized guided dashboard/source changes; research evidence and immutable handoff manifest retained.',files=amendments)
    (ROOT/'laptop_patch_manifest.json').write_text(json.dumps(value,indent=2),encoding='utf-8')
    print(json.dumps(dict(source_amendments=len(amendments),research_evidence_unchanged=True)))


if __name__=='__main__':main()
