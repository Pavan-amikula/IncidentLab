"""Independent healthy-fitted native telemetry detector; no RCAEval schema reuse."""
import json
import time
from collections import defaultdict
from pathlib import Path

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest

SERVICES = ('frontend', 'checkout', 'inventory')
FEATURES = ('p95_latency_ms', 'error_fraction', 'requests_per_second', 'max_active_requests')


def aggregate(events, start, end):
    groups = defaultdict(list)
    for event in events:
        if start <= event['end'] < end:
            groups[event['service']].append(event)
    rows = []
    for service in SERVICES:
        observed = groups[service]
        rows.append(dict(service=service, start=start, end=end, count=len(observed),
            features=[float(np.quantile([e['duration_ms'] for e in observed], .95)) if observed else 0,
                      sum(e['status'] >= 400 for e in observed)/max(1, len(observed)),
                      len(observed)/(end-start),
                      max([e['active_requests'] for e in observed], default=0)],
            evidence=[dict(span_id=e['span_id'], trace_id=e['trace_id'], message=e['message'],
                           status=e['status'], duration_ms=e['duration_ms'], dependency=e['dependency'],
                           dependency_status=e['dependency_status'])
                      for e in sorted(observed, key=lambda e: (e['status'] >= 400, e['duration_ms']), reverse=True)[:3]]))
    return rows


def fit(training, validation, output):
    bundle = {'schema': 'incidentlab-http-v1', 'features': FEATURES, 'services': {},
              'policy': 'Healthy training and separate healthy validation only; no fault outcomes used'}
    for service in SERVICES:
        train = np.asarray([r['features'] for r in training if r['service'] == service and r['count']])
        valid = np.asarray([r['features'] for r in validation if r['service'] == service and r['count']])
        if len(train) < 10 or len(valid) < 10:
            raise ValueError('At least ten healthy train and validation windows per service are required')
        scale = np.maximum(np.median(np.abs(train-np.median(train, axis=0)), axis=0), [1, .01, 1, 1])
        center = np.median(train, axis=0)
        model = IsolationForest(n_estimators=150, random_state=81).fit((train-center)/scale)
        scores = -model.score_samples((valid-center)/scale)
        bundle['services'][service] = dict(model=model, center=center, scale=scale,
            threshold=float(np.quantile(scores, .99)),
            latency_limit=float(max(np.quantile(valid[:, 0], .99)*2, 50)),
            error_limit=float(max(np.quantile(valid[:, 1], .99)+.05, .05)))
    joblib.dump(bundle, output)
    return bundle


def score(rows, bundle):
    began = time.perf_counter()
    findings = []
    for row in rows:
        fitted = bundle['services'][row['service']]
        value = np.asarray(row['features'])
        anomaly = float(-fitted['model'].score_samples(((value-fitted['center'])/fitted['scale'])[None])[0]) if row['count'] else None
        reasons = []
        if not row['count']:
            reasons.append('no completed service requests; check dependency and collection')
        if value[0] > fitted['latency_limit']:
            reasons.append('request latency exceeds healthy validation envelope')
        if value[1] > fitted['error_limit']:
            reasons.append('HTTP error fraction exceeds healthy validation envelope')
        # Trace evidence distinguishes a locally returned error from propagated failures.
        local_errors = [e for e in row['evidence'] if e['status'] >= 400 and e['dependency'] is None]
        failed_edges = [e for e in row['evidence'] if e['dependency_status'] not in (None, 200)]
        findings.append(dict(service=row['service'], count=row['count'], features=row['features'],
            ml_score=anomaly, ml_alert=anomaly is not None and anomaly > fitted['threshold'],
            operational_alert=bool(reasons), reasons=reasons, evidence=row['evidence'],
            hypothesis_priority=3 if local_errors else 2 if not row['count'] else 1 if reasons else 0,
            dependency_edges=[dict(source=row['service'], target=e['dependency'], status=e['dependency_status'],
                                   span_id=e['span_id']) for e in failed_edges]))
    affected = {f['service'] for f in findings if f['operational_alert']}
    # Do not rank an upstream slow caller above its slow observed dependency simply
    # because end-to-end latency contains the downstream wait.
    for finding in findings:
        dependencies = {e['dependency'] for e in finding['evidence'] if e['dependency']}
        finding['affected_dependencies'] = sorted(dependencies & affected)
        if finding['operational_alert'] and not (dependencies & affected):
            finding['hypothesis_priority'] = max(3, finding['hypothesis_priority'])
    ranked = sorted(findings, key=lambda f: (f['hypothesis_priority'], f['features'][0]), reverse=True)
    return dict(start=rows[0]['start'], end=rows[0]['end'],
        ml_alert=any(f['ml_alert'] for f in findings), operational_alert=any(f['operational_alert'] for f in findings),
        candidates=ranked, inference_ms=(time.perf_counter()-began)*1000,
        interpretation='Service hypotheses with measured HTTP trace evidence; not confirmed causal probabilities')


def read_events(directory: Path):
    events = []
    for service in SERVICES:
        path = directory / f'{service}.jsonl'
        if path.exists():
            for line in path.read_text(encoding='utf-8').splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    # An in-progress final append is retried at the next observation window.
                    continue
    return events
