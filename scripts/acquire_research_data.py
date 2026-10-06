"""Acquire complete author-published benchmarks; preserve provenance and checksums."""
import hashlib
import json
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from huggingface_hub import HfApi, snapshot_download

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'data' / 'research'


def archive(name, url, expected_md5):
    path = DEST / name
    if not path.exists():
        partial = path.with_suffix(path.suffix + '.partial')
        urllib.request.urlretrieve(url, partial)
        partial.replace(path)
    digest = hashlib.md5(path.read_bytes()).hexdigest()
    if digest != expected_md5:
        raise ValueError(f'Checksum mismatch for {name}: {digest}')
    result = dict(name=name, url=url, bytes=path.stat().st_size, md5=digest)
    (DEST / f'{name}.provenance.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result), flush=True)
    return result


def rcaeval():
    repo = 'phamquiluan/RCAEval'
    revision = HfApi().dataset_info(repo).sha
    target = DEST / 'RCAEval'
    print(f'Downloading complete RCAEval at {revision}', flush=True)
    snapshot_download(repo, repo_type='dataset', revision=revision,
                      local_dir=target, max_workers=4)
    files = []
    for path in sorted(target.rglob('*')):
        if not path.is_file() or '.cache' in path.relative_to(target).parts:
            continue
        digest = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                digest.update(chunk)
        files.append(dict(path=path.relative_to(target).as_posix(),
                          bytes=path.stat().st_size, sha256=digest.hexdigest()))
    result = dict(repository=repo, revision=revision, files=files,
                  total_bytes=sum(f['bytes'] for f in files))
    (DEST / 'RCAEval.provenance.json').write_text(json.dumps(result, indent=2))
    print(f"RCAEval verified: {len(files)} files, {result['total_bytes']} bytes", flush=True)
    return result


if __name__ == '__main__':
    DEST.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(rcaeval),
                   pool.submit(archive, 'OpenStack.tar.gz',
                     'https://zenodo.org/api/records/8196385/files/OpenStack.tar.gz/content',
                     '66bd42c07837a094d9b0ea2d036b5713'),
                   pool.submit(archive, 'AnoMod.zip',
                     'https://zenodo.org/api/records/18342898/files/AnoMod.zip/content',
                     '30c5835190c3550c5efc34d6be4f9238')]
        for future in futures:
            future.result()
