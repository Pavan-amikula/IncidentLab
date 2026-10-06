"""Inspect full archives and available Parquet metadata without loading all data into RAM."""
import json
import os
import tarfile
import zipfile
from collections import Counter
from pathlib import Path
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data' / 'research'


def audit():
    report = {}
    with tarfile.open(DATA / 'OpenStack.tar.gz') as archive:
        files = []
        for member in archive.getmembers():
            if member.isfile():
                with archive.extractfile(member) as stream:
                    rows = sum(1 for _ in stream)
                files.append(dict(path=member.name, bytes=member.size, lines=rows))
        report['OpenStack'] = dict(files=files, total_log_lines=sum(f['lines'] for f in files if f['path'].endswith('.log')))
    with zipfile.ZipFile(DATA / 'AnoMod.zip') as archive:
        files = [dict(path=f.filename, bytes=f.file_size) for f in archive.infolist() if not f.is_dir()]
        report['AnoMod'] = dict(file_count=len(files), expanded_bytes=sum(f['bytes'] for f in files),
                                extensions=dict(Counter(Path(f['path']).suffix for f in files)), files=files)
        extracted = (DATA / 'AnoMod').resolve()
        if extracted.exists():
            missing = []
            for entry in files:
                path = str(extracted / entry['path'])
                if os.name == 'nt':
                    path = '\\\\?\\' + path
                if not os.path.isfile(path):
                    missing.append(entry['path'])
            report['AnoMod']['missing_extracted_files'] = missing
    parquet = []
    for path in sorted((DATA / 'RCAEval').rglob('*.parquet')):
        try:
            file = pq.ParquetFile(path)
            parquet.append(dict(path=path.relative_to(DATA / 'RCAEval').as_posix(),
                                rows=file.metadata.num_rows, columns=file.schema.names))
        except Exception as error:
            parquet.append(dict(path=str(path), error=str(error)))
    report['RCAEval'] = dict(available_parquet_files=len(parquet), files=parquet,
                             acquisition_complete=(DATA / 'RCAEval.provenance.json').exists())
    for path in (DATA / 'RCAEval').rglob('cases.parquet'):
        table = pq.read_table(path)
        report['RCAEval']['case_index'] = dict(rows=table.num_rows, columns=table.column_names,
                                              example=table.slice(0, 1).to_pylist())
        suites = {}
        for row in table.to_pylist():
            stats = suites.setdefault(row['suite'], dict(cases=0, logs=0, traces=0,
                                                        missing_logs=0, missing_traces=0))
            stats['cases'] += 1
            stats['logs'] += row['n_logs']
            stats['traces'] += row['n_traces']
            stats['missing_logs'] += not row['has_logs']
            stats['missing_traces'] += not row['has_traces']
        report['RCAEval']['index_declared_suite_totals'] = suites
        actual = {f['path']: f for f in parquet}
        missing, mismatched = [], []
        for row in table.to_pylist():
            expected = {'metrics': row['n_timesteps']}
            if row['has_logs']:
                expected['logs'] = row['n_logs']
            if row['has_traces']:
                expected['traces'] = row['n_traces']
            for modality, count in expected.items():
                name = f"{row['case']}/{modality}.parquet"
                if name not in actual:
                    missing.append(name)
                elif actual[name].get('rows') != count:
                    mismatched.append(dict(path=name, expected=count, actual=actual[name].get('rows')))
        report['RCAEval']['index_consistency'] = dict(missing_expected_files=missing,
                                                     row_count_mismatches=mismatched)
    dest = ROOT / 'artifacts' / 'research' / 'data_audit.json'
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(report, indent=2, default=str))
    print(json.dumps({k: {a: b for a, b in v.items() if a != 'files'} for k, v in report.items()}, indent=2))


if __name__ == '__main__':
    audit()
