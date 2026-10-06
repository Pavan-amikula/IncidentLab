"""Append causal trace aggregates without changing the preserved v1 baseline."""
import json
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

from .research_pipeline import ROOT, RAW, DATA, OUT, WINDOW, WARMUP, FEATURES, causal_change, dump

V2 = ROOT / 'data/processed/multimodal'
TRACE_FEATURES = ['trace_volume_change', 'trace_mean_duration_change', 'trace_max_duration_change',
                  'trace_status_change', 'traces_present', 'trace_status_available']


def aggregate_trace(batch, start, n):
    """Vectorized grouping, keeping RAM bounded to one Arrow batch."""
    encoded = pc.dictionary_encode(pc.fill_null(batch.column('serviceName'), '<unknown>'))
    services = encoded.dictionary.to_pylist()
    ids = np.asarray(encoded.indices.to_numpy())
    seconds = np.asarray(batch.column('startTimeMillis').to_numpy(zero_copy_only=False), dtype=float) / 1000
    durations = np.asarray(batch.column('duration').to_numpy(zero_copy_only=False), dtype=float)
    status = np.asarray(batch.column('statusCode').to_numpy(zero_copy_only=False), dtype=float)
    bins = np.floor((seconds - start) / WINDOW).astype(int)
    valid = (bins >= 0) & (bins < n) & np.isfinite(durations)
    key = ids[valid] * n + bins[valid]
    size = len(services) * n
    count = np.bincount(key, minlength=size).reshape(-1, n)
    total = np.bincount(key, weights=durations[valid], minlength=size).reshape(-1, n)
    # A status-change indicator, not a claim about one universal protocol's error codes.
    unusual = ((status[valid] != 0) & ((status[valid] < 200) | (status[valid] >= 400))).astype(float)
    codes = np.bincount(key, weights=unusual, minlength=size).reshape(-1, n)
    known = np.bincount(key, weights=np.isfinite(status[valid]).astype(float), minlength=size).reshape(-1, n)
    maximum = np.zeros(size)
    np.maximum.at(maximum, key, durations[valid])
    maximum = maximum.reshape(-1, n)
    return services, count, total, maximum, codes, known, int((~valid).sum())


def append_case(name):
    rows = pq.read_table(DATA / f'{name}.parquet').to_pylist()
    start = rows[0]['start'] - WARMUP * WINDOW
    n = max(r['window'] for r in rows) + 1
    grouped = defaultdict(lambda: np.zeros((n, 5)))
    candidate_services = {r['service'] for r in rows}
    aliases = {}
    scanned = outside = 0
    path = RAW / name / 'traces.parquet'
    if path.exists():
        for batch in pq.ParquetFile(path).iter_batches(batch_size=131072,
                    columns=['serviceName', 'startTimeMillis', 'duration', 'statusCode']):
            services, count, total, maximum, codes, known, ignored = aggregate_trace(batch, start, n)
            scanned += batch.num_rows
            outside += ignored
            for i, service in enumerate(services):
                # Online Boutique exposes this frontend under two documented source names.
                if service == 'frontendservice' and 'frontend' in candidate_services and service not in candidate_services:
                    aliases[service] = 'frontend'
                    service = 'frontend'
                values = grouped[service]
                values[:, 0] += count[i]
                values[:, 1] += total[i]
                values[:, 2] = np.maximum(values[:, 2], maximum[i])
                values[:, 3] += codes[i]
                values[:, 4] += known[i]
    normalized = {}
    for service, values in grouped.items():
        count = values[:, 0]
        mean = np.divide(values[:, 1], count, out=np.zeros(n), where=count > 0)
        rate = np.divide(values[:, 3], values[:, 4], out=np.zeros(n), where=values[:, 4] > 0)
        available = np.divide(values[:, 4], count, out=np.zeros(n), where=count > 0)
        normalized[service] = np.column_stack([causal_change(np.column_stack([
            np.log1p(count), mean, values[:, 2], rate])), (count > 0).astype(float), available])
    for row in rows:
        values = normalized.get(row['service'])
        row['features'] += values[row['window']].tolist() if values is not None else [0.] * len(TRACE_FEATURES)
        row['trace_source_available'] = path.exists()
    pq.write_table(pa.Table.from_pylist(rows), V2 / f'{name}.parquet', compression='zstd')
    return dict(case=name, trace_rows=scanned, outside_window_rows=outside,
                traced_services=len(grouped), resolved_aliases=aliases,
                unmatched_traced_services=sorted(set(grouped) - {r['service'] for r in rows}))


def prepare():
    started = time.perf_counter()
    manifest = json.loads((DATA / 'split_manifest.json').read_text())
    manifest['features'] = FEATURES + TRACE_FEATURES
    manifest['version'] = 'multimodal-v2'
    manifest['evaluation_note'] = 'RCAEval test is development comparison; AnoMod reserved for final external evaluation'
    V2.mkdir(parents=True, exist_ok=True)
    dump(V2 / 'split_manifest.json', manifest)
    audits = []
    with ThreadPoolExecutor(max_workers=4) as pool:
        # Map returns only tiny audit objects; batch telemetry never accumulates across cases.
        for i, result in enumerate(pool.map(append_case, manifest['assignments']), 1):
            audits.append(result)
            if i % 40 == 0 or i == len(manifest['assignments']):
                print(f'TRACES {i}/{len(manifest["assignments"])} cases, {sum(a["trace_rows"] for a in audits):,} spans', flush=True)
    dump(OUT / 'trace_preparation_report.json', dict(cases=len(audits),
        spans_scanned=sum(a['trace_rows'] for a in audits), seconds=round(time.perf_counter() - started, 2),
        features=manifest['features'], cases_audit=audits,
        limitations=['no dependency graph yet', 'max duration sensitive to outliers',
                      'missing sources explicit; trace-status indicator requires protocol-specific review']))


if __name__ == '__main__':
    prepare()
