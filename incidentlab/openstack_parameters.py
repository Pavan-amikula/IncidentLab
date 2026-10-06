"""Restore measured lifecycle parameters before text masking; development comparison.

Fits only author normal1, calibrates only the existing healthy normal2 split.
The four abnormal labels have already been inspected: this is not a fresh final test.
"""
import hashlib
import json
import re
import time
from collections import Counter, defaultdict

import joblib
import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.metrics import average_precision_score, precision_recall_fscore_support

from .openstack_schema import BASE, INSTANCE, LINE, UUID
from .research_pipeline import OUT, dump

OPERATIONS = ('spawn the instance on the hypervisor', 'build instance',
              'destroy the instance on the hypervisor', 'deallocate network for instance')
DURATION = re.compile(r'Took (\d+(?:\.\d+)?) seconds to ('+
                      '|'.join(re.escape(op) for op in OPERATIONS)+r')\.')
SCHEMA = 'openstack-lifecycle-parameters-v1'


def duration_event(line, line_number):
    instance = INSTANCE.search(line)
    measured = DURATION.search(line)
    if instance is None or measured is None or LINE.match(line) is None:
        return None
    duration = float(measured[1])
    if not np.isfinite(duration):
        raise ValueError('Nonfinite measured duration')
    return dict(instance=instance[1], operation=measured[2], duration_seconds=duration,
                line_number=line_number, observed_timestamp=' '.join(line.split()[1:3]))


def parse_parameters(path):
    sessions, audit = defaultdict(list), Counter()
    with path.open(encoding='utf-8', errors='replace') as source:
        for number, line in enumerate(source, 1):
            audit['physical_lines'] += 1
            if not LINE.match(line):
                audit['unparsed_or_continuation_lines'] += 1
                continue
            instance = INSTANCE.search(line)
            if instance is None:
                audit['unassigned_instance_events'] += 1
                continue
            audit['explicit_instance_events'] += 1
            sessions[instance[1]]  # Retain sessions with no measured durations.
            event = duration_event(line, number)
            if event:
                sessions[instance[1]].append(event)
                audit['measured_duration_events'] += 1
    audit['sessions'] = len(sessions)
    audit['sessions_with_all_four_parameters'] = sum(
        set(e['operation'] for e in events) == set(OPERATIONS) for events in sessions.values())
    return dict(sessions), dict(audit)


def vector(events):
    # Maximum of all observed measurements per operation. Missing is explicit NaN,
    # never an invented zero or a proof of failure.
    return np.asarray([max((e['duration_seconds'] for e in events if e['operation']==operation),
                           default=np.nan) for operation in OPERATIONS])


def robust_scores(matrix, center, scale):
    missing = np.isnan(matrix)
    deviation = np.where(missing, -np.inf, np.abs((matrix-center)/scale))
    scores = np.max(deviation, axis=1)
    scores[np.all(missing, axis=1)] = np.nan
    return scores


def summary(truth, score, threshold):
    eligible = np.isfinite(score)
    predicted = eligible & (score > threshold)
    precision, recall, f1, _ = precision_recall_fscore_support(
        truth, predicted, average='binary', zero_division=0)
    return dict(precision=float(precision), recall=float(recall), f1=float(f1),
        threshold=float(threshold), alerted_sessions=int(predicted.sum()),
        annotated_positive_hits=int((predicted & (truth==1)).sum()),
        average_precision_eligible=float(average_precision_score(truth[eligible], score[eligible])),
        abstained_sessions=int((~eligible).sum()),
        abstained_annotated_sessions=int(((~eligible)&(truth==1)).sum()))


def run():
    started = time.perf_counter()
    filenames = ('openstack_normal1.log','openstack_normal2.log','openstack_abnormal.log')
    sources, audits, hashes = {}, {}, {}
    for filename in filenames:
        path = BASE/filename
        sources[filename], audits[filename] = parse_parameters(path)
        hashes[filename] = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f'Preserved raw parameters: {filename}: {audits[filename]}', flush=True)
    splits = json.loads((OUT/'openstack_split_manifest.json').read_text())
    def select(filename, key):
        values = sources[filename]
        if not set(splits[key]).issubset(values):
            raise ValueError('Original split identities are missing from parameter adapter')
        return {identifier:values[identifier] for identifier in splits[key]}
    train = select(filenames[0], 'train')
    valid = select(filenames[1], 'validation')
    x_train = np.stack([vector(v) for v in train.values()])
    x_valid = np.stack([vector(v) for v in valid.values()])
    center = np.nanmedian(x_train, axis=0)
    scale = np.maximum(np.nanmedian(np.abs(x_train-center), axis=0), .01)
    if not np.isfinite(center).all():
        raise ValueError('Training is missing an entire operation parameter')
    # Missingness is retained; training medians fill values only for the finite ML input.
    def model_input(x):
        return np.column_stack([np.nan_to_num((x-center)/scale, nan=0.0), np.isnan(x).astype(float)])
    model = IsolationForest(n_estimators=200, random_state=2026).fit(model_input(x_train))
    valid_scores = dict(parameter_residual=robust_scores(x_valid, center, scale),
                        parameter_isolation_forest=-model.score_samples(model_input(x_valid)))
    thresholds = {key:float(np.nanquantile(value, .99)) for key,value in valid_scores.items()}
    bundle = dict(schema=SCHEMA, operations=OPERATIONS, center=center, scale=scale,
        thresholds=thresholds, model=model, parameter_units='seconds',
        split_sha256=hashlib.sha256((OUT/'openstack_split_manifest.json').read_bytes()).hexdigest(),
        fitting='normal1 training; same identity-disjoint healthy normal2 calibration')
    checkpoint = OUT/'openstack_parameter_models_v3.joblib'
    joblib.dump(bundle, checkpoint)
    frozen = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    # Author annotations are read only after fitting/calibration/checkpoint freeze.
    positives = set(UUID.findall((BASE/'anomaly_labels.txt').read_text()))
    tests = [(key, values, 'normal2') for key, values in select(filenames[1], 'normal2_test').items()]
    tests += [(key, values, 'abnormal') for key, values in select(filenames[2], 'abnormal_test').items()]
    truth = np.asarray([int(key in positives) for key,_,_ in tests])
    x_test = np.stack([vector(events) for _,events,_ in tests])
    scores = dict(parameter_residual=robust_scores(x_test, center, scale),
                  parameter_isolation_forest=-model.score_samples(model_input(x_test)))
    results = {key:summary(truth, value, thresholds[key]) for key,value in scores.items()}
    for name,result in results.items():
        alerted = np.isfinite(scores[name]) & (scores[name]>thresholds[name])
        result['false_alerted_normal2_sessions'] = sum(bool(p) and source=='normal2'
            for p,(_,_,source) in zip(alerted, tests))
    rows = []
    for i,(key,events,source) in enumerate(tests):
        rows.append(dict(instance=key, source=source, annotation=int(truth[i]),
            parameters={name:(float(value) if np.isfinite(value) else None)
                        for name,value in zip(OPERATIONS,x_test[i])},
            missing_operations=[name for name,value in zip(OPERATIONS,x_test[i]) if np.isnan(value)],
            scores={name:(float(value[i]) if np.isfinite(value[i]) else None) for name,value in scores.items()},
            evidence=events))
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=frozen:
        raise RuntimeError('Frozen checkpoint changed during evaluation')
    report = dict(scope='Development revision restoring numeric lifecycle durations after inspecting V1/V2 failures',
        feature_schema=SCHEMA, source_sha256=hashes, audits=audits, train_sessions=len(train),
        validation_sessions=len(valid), healthy_normal2_test_sessions=len(splits['normal2_test']),
        abnormal_test_sessions=len(splits['abnormal_test']), annotated_positive_sessions=int(truth.sum()),
        results=results, checkpoint_sha256=frozen, center_seconds=dict(zip(OPERATIONS,center.tolist())),
        scale_seconds=dict(zip(OPERATIONS,scale.tolist())), seconds=time.perf_counter()-started,
        limitations=['Four previously inspected annotated sessions; this is development evidence, not a fresh final test',
            'No label-derived thresholds: all feature normalization/training uses normal1 and calibration uses healthy normal2 only',
            'Native logs and timings are not Kubernetes operational validation',
            'Reported parameters appear at completion; do not infer early detection or fault onset from a session label',
            'Missing parameters remain explicit; incomplete sessions may be censored by capture boundaries',
            'Instance association still uses explicit IDs; no guessed cross-request association'])
    dump(OUT/'openstack_parameters_v3_predictions.json', rows)
    dump(OUT/'openstack_parameters_v3_report.json', report)
    print(json.dumps(results, indent=2), flush=True)


if __name__ == '__main__': run()
