"""Full RCAEval conventional baseline, separate from the synthetic demo.

Bounded batches process every log row. Models never receive case names, fault labels,
injection timestamps, or root-cause labels. First five minutes are a causal warm-up.
"""
import argparse
import hashlib
import json
import re
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import joblib
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, precision_recall_fscore_support

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/research/RCAEval'
DATA = ROOT / 'data/processed/rcaeval'
OUT = ROOT / 'artifacts/research'
KINDS = ['cpu', 'mem', 'diskio', 'socket', 'workload', 'error', 'latency-50', 'latency-90']
FEATURES = [f'metric_{k}_change' for k in KINDS] + ['log_volume_change', 'log_error_change', 'logs_present']
ERROR = re.compile(r'\b(error|exception|fatal|panic|timeout|timed\s+out|refused|failed|failure)\b', re.I)
WINDOW = 60
WARMUP = 5


def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, allow_nan=False), encoding='utf-8')


def bounded_cases(pool, cases):
    iterator = iter(cases)
    pending = deque()
    for _ in range(8):
        case = next(iterator, None)
        if case is not None:
            pending.append(pool.submit(process_case, case))
    while pending:
        yield pending.popleft().result()
        case = next(iterator, None)
        if case is not None:
            pending.append(pool.submit(process_case, case))


def splits(cases):
    """Stratify by published dataset, assigning whole runs once."""
    groups = defaultdict(list)
    for case in cases:
        groups[case['dataset']].append(case['case'])
    result = {}
    for names in groups.values():
        names.sort(key=lambda name: hashlib.sha256(('incidentlab-v1:' + name).encode()).hexdigest())
        a, b = int(len(names) * .6), int(len(names) * .8)
        for i, name in enumerate(names):
            result[name] = 'train' if i < a else 'validation' if i < b else 'test'
    return result


def causal_change(values):
    """Only initial warm-up values define location/scale; later values cannot affect it."""
    warm = values[:WARMUP]
    center = np.nanmedian(warm, axis=0)
    scale = np.nanstd(warm, axis=0)
    scale = np.maximum(scale, np.maximum(np.abs(center) * .05, 1e-6))
    changed = np.abs(values - center) / scale
    return np.clip(np.nan_to_num(changed, nan=0, posinf=100, neginf=0), 0, 100)


def process_case(case):
    path = RAW / case['case']
    table = pq.read_table(path / 'metrics.parquet')
    timestamps = np.asarray(table['time'].to_numpy(), dtype=float)
    if not np.isfinite(timestamps).all() or np.any(np.diff(timestamps) < 0):
        raise ValueError(f'Invalid metric time order: {path.name}')
    start = float(timestamps.min())
    bins = ((timestamps - start) // WINDOW).astype(int)
    # Ignore incomplete trailing minute; identical behavior in replay and evaluation.
    n = int((timestamps.max() - start + 1) // WINDOW)
    if n <= WARMUP:
        raise ValueError(f'Insufficient warm-up: {path.name}')
    services = {}
    for name in table.column_names:
        if name == 'time' or '_' not in name:
            continue
        service, kind = name.rsplit('_', 1)
        if kind not in KINDS:
            continue
        matrix = services.setdefault(service, np.full((n, len(KINDS)), np.nan))
        values = np.asarray(table[name].to_numpy(), dtype=float)
        valid = np.isfinite(values) & (bins < n)
        count = np.bincount(bins[valid], minlength=n)
        total = np.bincount(bins[valid], weights=values[valid], minlength=n)
        matrix[:, KINDS.index(kind)] = np.divide(total, count, out=np.full(n, np.nan), where=count > 0)
    log_counts = defaultdict(lambda: np.zeros((n, 2)))
    log_rows = outside = 0
    log_path = path / 'logs.parquet'
    if log_path.exists():
        for batch in pq.ParquetFile(log_path).iter_batches(batch_size=32768, columns=['timestamp', 'container_name', 'message']):
            times, names, messages = (batch.column(i).to_pylist() for i in range(3))
            for stamp, service, message in zip(times, names, messages):
                log_rows += 1
                index = int((stamp - start) // WINDOW)
                if not 0 <= index < n:
                    outside += 1
                    continue
                count = log_counts[service]
                count[index, 0] += 1
                count[index, 1] += bool(ERROR.search(message or ''))
    rows = []
    for service in sorted(set(services) | set(log_counts)):
        metrics = services.get(service, np.full((n, len(KINDS)), np.nan))
        missing = np.all(~np.isfinite(metrics[:WARMUP]), axis=0)
        # Missing columns remain explicit zero change, never interpreted as healthy evidence.
        with np.errstate(invalid='ignore'):
            filled = metrics.copy()
            filled[:, missing] = 0
            metric_change = causal_change(filled)
        counts = log_counts[service]
        error_rate = np.divide(counts[:, 1], counts[:, 0], out=np.zeros(n), where=counts[:, 0] > 0)
        log_features = np.column_stack([np.log1p(counts[:, 0]), error_rate])
        log_change = causal_change(log_features)
        for index in range(WARMUP, n):
            feature = np.concatenate([metric_change[index], log_change[index], [float(counts[index, 0] > 0)]])
            rows.append(dict(service=service, window=index,
                             start=start + index * WINDOW, end=start + (index + 1) * WINDOW,
                             features=feature.tolist(), metric_columns_missing=int(missing.sum())))
    return case['case'], rows, dict(log_rows_scanned=log_rows, log_rows_outside_complete_windows=outside,
                                    windows=n - WARMUP, service_rows=len(rows))


def prepare():
    if not (ROOT / 'data/research/RCAEval.provenance.json').exists():
        raise RuntimeError('Complete verified RCAEval acquisition is required')
    started = time.perf_counter()
    all_cases = pq.read_table(RAW / 'cases.parquet').to_pylist()
    excluded = [dict(case=c['case'], reason='insufficient pre-fault warm-up or post-fault observation',
                     normal_timesteps=c['normal_timesteps'], faulty_timesteps=c['faulty_timesteps'])
                for c in all_cases if c['normal_timesteps'] < WARMUP * WINDOW or c['faulty_timesteps'] < WINDOW]
    excluded_names = {c['case'] for c in excluded}
    cases = [c for c in all_cases if c['case'] not in excluded_names]
    mapping = splits(cases)
    DATA.mkdir(parents=True, exist_ok=True)
    dump(DATA / 'split_manifest.json', dict(protocol='whole-case 60/20/20 stratified by dataset',
        seed='incidentlab-v1', assignments=mapping, excluded_cases=excluded, features=FEATURES,
        window_seconds=WINDOW, warmup_seconds=WINDOW * WARMUP,
        source_revision=json.loads((ROOT / 'data/research/RCAEval.provenance.json').read_text())['revision']))
    # Labels live separately from inference features.
    pq.write_table(pa.Table.from_pylist(cases), DATA / 'evaluation_labels.parquet')
    audits = {}
    with ThreadPoolExecutor(max_workers=4) as pool:
        for i, (name, rows, audit) in enumerate(bounded_cases(pool, cases), 1):
            pq.write_table(pa.Table.from_pylist(rows), DATA / f'{name}.parquet', compression='zstd')
            audits[name] = audit
            if i % 25 == 0 or i == len(cases):
                print(f'Prepared {i}/{len(cases)} cases; scanned {sum(a["log_rows_scanned"] for a in audits.values()):,} logs', flush=True)
    report = dict(acquired_cases=len(all_cases), cases=len(cases), excluded_cases=excluded,
                  split_counts={s: sum(v == s for v in mapping.values()) for s in ['train', 'validation', 'test']},
                  log_rows_scanned=sum(a['log_rows_scanned'] for a in audits.values()),
                  service_rows=sum(a['service_rows'] for a in audits.values()),
                  seconds=round(time.perf_counter() - started, 2), cases_audit=audits,
                  limitations=['metrics/log statistical baseline; traces not yet used',
                    'five-minute initial healthy warm-up assumed; no online update',
                    'absolute changes lose direction; missing metric count recorded separately'])
    dump(OUT / 'preprocessing_report.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'cases_audit'}, indent=2))


def load(stage):
    manifest = json.loads((DATA / 'split_manifest.json').read_text())
    labels = {row['case']: row for row in pq.read_table(DATA / 'evaluation_labels.parquet').to_pylist()}
    for case, assigned in manifest['assignments'].items():
        if stage == assigned:
            yield case, pq.read_table(DATA / f'{case}.parquet').to_pylist(), labels[case]


def arrays(rows):
    return np.asarray([row['features'] for row in rows], dtype=np.float32)


def train():
    started = time.perf_counter()
    if not (OUT / 'preprocessing_report.json').exists():
        raise RuntimeError('Complete preprocessing before training')
    normal = []
    training_cases = 0
    priors = defaultdict(lambda: defaultdict(int))
    for _, rows, label in load('train'):
        training_cases += 1
        normal.append(arrays([r for r in rows if r['end'] <= label['inject_time']]))
        priors[label['system']][label['root_cause_service']] += 1
    x = np.concatenate(normal)
    model = IsolationForest(n_estimators=200, max_samples=1024, random_state=42, n_jobs=4).fit(x)
    OUT.mkdir(parents=True, exist_ok=True)
    joblib.dump(dict(model=model, features=FEATURES, priors={k: dict(v) for k, v in priors.items()},
                    split_manifest_sha256=hashlib.sha256((DATA / 'split_manifest.json').read_bytes()).hexdigest()), OUT / 'rcaeval_trained.joblib')
    dump(OUT / 'full_training_report.json', dict(normal_service_windows=len(x), trees=200,
        training_cases=training_cases, seconds=round(time.perf_counter() - started, 2),
        validation_used=False, test_used=False, labels_used='pre-fault windows only, for normal-only fit'))
    print(f'TRAIN: fitted on {len(x):,} healthy service windows', flush=True)


def window_scores(bundle, rows):
    scores = -bundle['model'].score_samples(arrays(rows))
    windows = defaultdict(list)
    for row, score in zip(rows, scores):
        windows[row['window']].append((row, float(score)))
    return windows


def validate():
    bundle = joblib.load(OUT / 'rcaeval_trained.joblib')
    if bundle['split_manifest_sha256'] != hashlib.sha256((DATA / 'split_manifest.json').read_bytes()).hexdigest():
        raise RuntimeError('Split manifest changed after training')
    normal = defaultdict(list)
    for _, rows, label in load('validation'):
        for values in window_scores(bundle, rows).values():
            if values[0][0]['end'] <= label['inject_time']:
                normal[label['system']].append(max(score for _, score in values))
    bundle['thresholds'] = {system: float(np.quantile(scores, .995)) for system, scores in normal.items()}
    bundle['split_manifest_sha256'] = hashlib.sha256((DATA / 'split_manifest.json').read_bytes()).hexdigest()
    joblib.dump(bundle, OUT / 'rcaeval_calibrated.joblib')
    dump(OUT / 'full_validation_report.json', dict(thresholds=bundle['thresholds'],
          quantile=.995, healthy_windows={k: len(v) for k, v in normal.items()}, test_used=False))
    print('VALIDATION: thresholds frozen', bundle['thresholds'], flush=True)


def summarize(results):
    truth = [r['anomalous'] for r in results]
    predicted = [r['alert'] for r in results]
    precision, recall, f1, _ = precision_recall_fscore_support(truth, predicted, average='binary', zero_division=0)
    healthy = [r for r in results if not r['anomalous']]
    hours = len(healthy) * WINDOW / 3600
    return dict(windows=len(results), precision=float(precision), recall=float(recall), f1=float(f1),
                pr_auc=float(average_precision_score(truth, [r['score'] for r in results])),
                false_alert_windows_per_healthy_hour=sum(r['alert'] for r in healthy) / hours if hours else None)


def test():
    bundle = joblib.load(OUT / 'rcaeval_calibrated.joblib')
    expected = hashlib.sha256((DATA / 'split_manifest.json').read_bytes()).hexdigest()
    if expected != bundle['split_manifest_sha256']:
        raise RuntimeError('Split manifest changed after calibration')
    results, diagnoses = [], []
    for case, rows, label in load('test'):
        first_alert = None
        for _, values in sorted(window_scores(bundle, rows).items()):
            row = values[0][0]
            # A window straddling onset has ambiguous duration; omit it from window metrics.
            if row['start'] < label['inject_time'] < row['end']:
                continue
            score = max(s for _, s in values)
            alert = score > bundle['thresholds'][label['system']]
            faulty = row['start'] >= label['inject_time']
            results.append(dict(case=case, system=label['system'], end=row['end'], score=score, alert=alert, anomalous=faulty))
            if faulty and alert and first_alert is None:
                ranked = sorted(values, key=lambda v: v[1], reverse=True)
                first_alert = dict(case=case, delay_seconds=row['end'] - label['inject_time'],
                    ranking=[r['service'] for r, _ in ranked], root_cause=label['root_cause_service'])
        prior = sorted(bundle['priors'][label['system']], key=bundle['priors'][label['system']].get, reverse=True)
        diagnoses.append(dict(case=case, detected=first_alert is not None, first_alert=first_alert,
                              prior_ranking=prior, root_cause=label['root_cause_service']))
    report = dict(overall=summarize(results), by_system={s: summarize([r for r in results if r['system'] == s]) for s in ['ob', 'ss', 'tt']},
                  test_cases=len(diagnoses), incident_recall=sum(d['detected'] for d in diagnoses) / len(diagnoses),
                  ranking_at_first_alert={f'top{k}': sum(d['detected'] and d['root_cause'] in d['first_alert']['ranking'][:k] for d in diagnoses) / len(diagnoses) for k in [1, 3, 5]},
                  prior_only={f'top{k}': sum(d['root_cause'] in d['prior_ranking'][:k] for d in diagnoses) / len(diagnoses) for k in [1, 3, 5]},
                  limitations=['controlled benchmark, not production validation', 'ranking is statistical evidence, not causal proof',
                               'false-alert rate is per window, not deduplicated incidents', 'initial healthy warm-up assumption'])
    dump(OUT / 'full_test_report.json', report)
    dump(OUT / 'full_test_predictions.json', dict(windows=results, diagnoses=diagnoses))
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage', choices=['prepare', 'train', 'validate', 'test'])
    args = parser.parse_args()
    {'prepare': prepare, 'train': train, 'validate': validate, 'test': test}[args.stage]()
