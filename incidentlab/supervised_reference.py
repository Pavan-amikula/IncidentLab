"""Non-temporal supervised reference with the same modalities and training labels."""
import json
import time

import joblib
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier

from .research_pipeline import OUT, dump
from .temporal_model import WindowDataset, calibrate, metrics


def tabular(data):
    windows, services, targets, slices = [], [], [], []
    for item in data.items:
        current = np.log1p(item['x'][:, -1].clip(min=0))
        active = item['mask']
        context = current[active].mean(0)
        windows.append(np.concatenate([context, current[active].max(0)]))
        start = len(services)
        for i in np.flatnonzero(active):
            services.append(np.concatenate([current[i], context]))
            targets.append(int(i == item['root']))
        slices.append((start, len(services), np.flatnonzero(active)))
    return np.asarray(windows), np.asarray(services), np.asarray(targets), slices


def predictions(bundle, data, prepared):
    x, services, _, slices = prepared
    detection = bundle['detector'].predict_proba(x)[:, 1]
    root = bundle['ranker'].predict_proba(services)[:, 1]
    rows = []
    for i, (start, end, active) in enumerate(slices):
        item = data.items[i]
        ranking = [item['meta']['services'][active[j]] for j in np.argsort(-root[start:end])]
        rows.append(dict(**item['meta'], score=float(detection[i]), anomalous=bool(item['y']), ranking=ranking))
    return rows


def run():
    started = time.perf_counter()
    training, validation = WindowDataset('train'), WindowDataset('validation')
    x, services, targets, slices = tabular(training)
    y = np.asarray([i['y'] for i in training.items], dtype=int)
    detector = HistGradientBoostingClassifier(max_iter=120, max_leaf_nodes=15, l2_regularization=1,
                                              early_stopping=False, random_state=42).fit(x, y)
    # Only fault-window services provide root-ranking supervision.
    keep = np.zeros(len(targets), dtype=bool)
    for item, (a, b, _) in zip(training.items, slices):
        if item['root'] >= 0:
            keep[a:b] = True
    labels = targets[keep]
    weights = np.where(labels == 1, (len(labels)-labels.sum()) / max(labels.sum(),1), 1.)
    ranker = HistGradientBoostingClassifier(max_iter=120, max_leaf_nodes=15, l2_regularization=1,
                                            early_stopping=False, random_state=42).fit(services[keep],labels,sample_weight=weights)
    bundle = dict(detector=detector, ranker=ranker)
    val_rows = predictions(bundle,validation,tabular(validation))
    bundle['thresholds'] = calibrate(val_rows)
    joblib.dump(bundle, OUT / 'supervised_reference.joblib')
    validation_report = metrics(val_rows,bundle['thresholds'])
    # Freeze training/calibration before opening development-test observations.
    testing = WindowDataset('test')
    test_rows = predictions(bundle,testing,tabular(testing))
    report = dict(model='non-temporal supervised histogram gradient boosting',
                  input='same current-window modalities and context; no temporal history or service identity',
                  validation=validation_report, development_test=metrics(test_rows,bundle['thresholds']),
                  thresholds=bundle['thresholds'], seconds=round(time.perf_counter()-started,2),
                  external_final_used=False)
    dump(OUT / 'supervised_reference_report.json',report)
    print(json.dumps(report,indent=2),flush=True)


if __name__ == '__main__':
    run()
