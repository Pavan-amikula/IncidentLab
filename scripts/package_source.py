"""Build a source-only handoff archive; excludes data, models, artifacts and secrets."""
import hashlib
import json
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def package():
    files = []
    for name in ('incidentlab','scripts','tests','web','docs','deployment','.vscode'):
        for path in (ROOT/name).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts and path.suffix in (
                    '.py','.ps1','.html','.md','.json','.yaml','.yml'):
                files.append(path)
    files.extend(path for path in ROOT.iterdir() if path.is_file() and (
        path.name.startswith('requirements') or path.name in ('README.md','.gitignore','.dockerignore')
        or path.suffix == '.ps1'))
    for path in (ROOT/'deployment').glob('Dockerfile*'):
        if path not in files: files.append(path)
    manifest = {str(path.relative_to(ROOT)):hashlib.sha256(path.read_bytes()).hexdigest() for path in sorted(set(files))}
    output = ROOT/'artifacts/release'
    output.mkdir(parents=True, exist_ok=True)
    archive = output/'IncidentLab-source.zip'
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED) as bundle:
        for path in sorted(set(files)):
            bundle.write(path, 'IncidentLab/'+str(path.relative_to(ROOT)).replace('\\','/'))
        bundle.writestr('IncidentLab/source_manifest.json', json.dumps(manifest, indent=2))
    with zipfile.ZipFile(archive) as bundle:
        if bundle.testzip() is not None:
            raise RuntimeError('Archive checksum validation failed')
        for name in manifest:
            actual = hashlib.sha256(bundle.read('IncidentLab/'+name.replace('\\','/'))).hexdigest()
            if actual != manifest[name]: raise RuntimeError('Source archive differs from manifest')
    (output/'source_manifest.json').write_text(json.dumps(manifest,indent=2))
    print(f'{archive}: {len(manifest)} verified source files, {archive.stat().st_size:,} bytes')


if __name__ == '__main__': package()
