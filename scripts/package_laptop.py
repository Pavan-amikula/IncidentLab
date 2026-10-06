"""Create a bounded CPU handoff with trained artifacts and hash-verified contents."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUTPUT=ROOT/'artifacts/release'


def files():
    found=set()
    for name in ('incidentlab','scripts','tests','web','docs','deployment','.vscode'):
        for path in (ROOT/name).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and (path.suffix in
                ('.py','.ps1','.html','.md','.json','.yaml','.yml') or path.name.startswith('Dockerfile')):
                found.add(path)
    for path in ROOT.iterdir():
        if path.is_file() and (path.name.startswith('requirements') or path.suffix in ('.md','.ps1')
            or path.name in ('.gitignore','.dockerignore')):found.add(path)
    for name in ('data/processed','artifacts/research','artifacts/live','artifacts/live_runtime'):
        for path in (ROOT/name).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix.lower() in (
                '.json','.jsonl','.parquet','.joblib','.pt','.png','.py','.stderr','.log','.txt','.md'):
                found.add(path)
    for cpu_report in (ROOT/'artifacts/handoff').glob('college_cpu*.json'):
        if cpu_report.is_file():found.add(cpu_report)
    return sorted(found)


def package():
    selected=files();manifest={}
    for path in selected:
        relative=path.relative_to(ROOT).as_posix()
        manifest[relative]=dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),bytes=path.stat().st_size)
    payload=dict(format='incidentlab-cpu-handoff-v1',platform='Windows x64 / Python 3.14',
        files=manifest,training_required=False,llm_generation_default=False,
        exclusions=['raw research datasets','virtual environments','CUDA','large neural weights','serving databases','credentials'],
        cluster_execution='Pending actual laptop execution; unit checks only on college PC')
    OUTPUT.mkdir(parents=True,exist_ok=True);archive=OUTPUT/'IncidentLab-laptop.zip'
    with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED,compresslevel=4) as bundle:
        for path in selected:bundle.write(path,'IncidentLab/'+path.relative_to(ROOT).as_posix())
        bundle.writestr('IncidentLab/handoff_manifest.json',json.dumps(payload,indent=2))
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:raise RuntimeError('Archive CRC verification failed')
        for name,entry in manifest.items():
            if hashlib.sha256(bundle.read('IncidentLab/'+name)).hexdigest()!=entry['sha256']:
                raise RuntimeError('Archive hash mismatch: '+name)
    digest=hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest+'  '+archive.name+'\n')
    report=dict(status='archive_verified',archive=str(archive),sha256=digest,files=len(manifest),
        compressed_bytes=archive.stat().st_size,uncompressed_bytes=sum(r['bytes'] for r in manifest.values()),
        trained_checkpoints=sum(name.endswith(('.joblib','.pt')) for name in manifest),
        processed_files=sum(name.startswith('data/processed/') for name in manifest),
        remaining='Extracted CPU runtime verification followed by real laptop Docker/Kubernetes execution')
    (OUTPUT/'laptop_package_report.json').write_text(json.dumps(report,indent=2));print(json.dumps(report,indent=2))


if __name__=='__main__':package()
