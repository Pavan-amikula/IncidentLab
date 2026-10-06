"""Extract verified archives into separate, bounded dataset directories."""
import hashlib
import json
import os
import stat
import tarfile
import zipfile
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / 'data' / 'research'


def verified(name):
    path = BASE / name
    record = json.loads((BASE / f'{name}.provenance.json').read_text())
    if hashlib.md5(path.read_bytes()).hexdigest() != record['md5']:
        raise ValueError(f'Archive checksum mismatch: {name}')
    return path


def bounded(root, name):
    resolved = (root / name).resolve()
    if not resolved.is_relative_to(root.resolve()):
        raise ValueError(f'Unsafe archive path: {name}')


if __name__ == '__main__':
    target = BASE / 'OpenStack'
    target.mkdir(exist_ok=True)
    with tarfile.open(verified('OpenStack.tar.gz')) as archive:
        for member in archive.getmembers():
            bounded(target, member.name)
        archive.extractall(target, filter='data')
    print(f'Extracted full OpenStack to {target}', flush=True)
    target = BASE / 'AnoMod'
    target.mkdir(exist_ok=True)
    with zipfile.ZipFile(verified('AnoMod.zip')) as archive:
        for member in archive.infolist():
            bounded(target, member.filename)
            if stat.S_ISLNK(member.external_attr >> 16):
                raise ValueError(f'Archive symlink rejected: {member.filename}')
        # Code-coverage filenames exceed legacy Windows MAX_PATH.
        output_path = '\\\\?\\' + str(target.resolve()) if os.name == 'nt' else str(target)
        archive.extractall(output_path)
    print(f'Extracted full AnoMod to {target}', flush=True)
