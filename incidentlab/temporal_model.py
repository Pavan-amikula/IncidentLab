"""Validation-selected multimodal GRU for detection and service localization.

Uses only causal service histories. No case/system/service identity is a learned input.
RCAEval test is explicitly a development comparison; external final data stays reserved.
"""
import argparse
import hashlib
import json
import random
import time
from collections import defaultdict

import numpy as np
import pyarrow.parquet as pq
import torch
from torch import nn
from torch.utils.data import Dataset, DataLoader

from .research_pipeline import DATA, OUT, WINDOW, dump, summarize
from .trace_features import V2

HISTORY = 5
DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'


class WindowDataset(Dataset):
    def __init__(self, stage):
        manifest = json.loads((V2 / 'split_manifest.json').read_text())
        labels = {r['case']: r for r in pq.read_table(DATA / 'evaluation_labels.parquet').to_pylist()}
        self.items = []
        self.cases = 0
        for name, assigned in manifest['assignments'].items():
            if assigned != stage:
                continue
            self.cases += 1
            rows = pq.read_table(V2 / f'{name}.parquet').to_pylist()
            label = labels[name]
            services = sorted({r['service'] for r in rows})
            ids = {s: i for i, s in enumerate(services)}
            first = min(r['window'] for r in rows)
            count = max(r['window'] for r in rows) - first + 1
            x = np.zeros((count, len(services), 18), dtype=np.float32)
            observed = np.zeros((count, len(services)), dtype=bool)
            for row in rows:
                w, s = row['window'] - first, ids[row['service']]
                x[w, s, :17] = row['features']
                x[w, s, 17] = row['metric_columns_missing'] / 8
                observed[w, s] = row['metric_columns_missing'] < 8 or row['features'][10] > 0 or row['features'][15] > 0
            for w in range(count):
                start = rows[0]['start'] + w * WINDOW
                end = start + WINDOW
                if start < label['inject_time'] < end or not observed[w].any():
                    continue
                fault = start >= label['inject_time']
                root = ids.get(label['root_cause_service'], -1) if fault else -1
                if root >= 0 and not observed[w, root]:
                    root = -1
                history = np.zeros((len(services), HISTORY, 18), dtype=np.float32)
                segment = x[max(0, w - HISTORY + 1):w + 1].transpose(1, 0, 2)
                history[:, -segment.shape[1]:] = segment
                self.items.append(dict(x=history, mask=observed[w].copy(), y=float(fault), root=root,
                    meta=dict(case=name, system=label['system'], start=start, end=end,
                              inject_time=label['inject_time'], root_cause=label['root_cause_service'], services=services)))

    def __len__(self):
        return len(self.items)

    def __getitem__(self, index):
        return self.items[index]


def collate(items):
    n = max(len(item['mask']) for item in items)
    x = torch.zeros(len(items), n, HISTORY, 18)
    mask = torch.zeros(len(items), n, dtype=torch.bool)
    for i, item in enumerate(items):
        k = len(item['mask'])
        x[i, :k] = torch.from_numpy(item['x'])
        mask[i, :k] = torch.from_numpy(item['mask'])
    return x, mask, torch.tensor([i['y'] for i in items]), torch.tensor([i['root'] for i in items]), [i['meta'] for i in items]


class TemporalFusion(nn.Module):
    def __init__(self, hidden=32):
        super().__init__()
        self.encoders = nn.ModuleList([nn.GRU(9, hidden, batch_first=True),
                                       nn.GRU(3, hidden, batch_first=True), nn.GRU(6, hidden, batch_first=True)])
        self.gates = nn.ModuleList([nn.Linear(hidden, 1) for _ in range(3)])
        self.root_head = nn.Sequential(nn.Linear(hidden * 2, hidden), nn.ReLU(), nn.Linear(hidden, 1))
        self.detect_head = nn.Sequential(nn.Linear(hidden * 2, hidden), nn.ReLU(), nn.Linear(hidden, 1))

    def forward(self, raw, mask, drop=None):
        b, s, t, _ = raw.shape
        x = torch.log1p(raw.clamp(min=0))
        modalities = [torch.cat([x[..., :8], x[..., 17:18]], dim=-1), x[..., 8:11], x[..., 11:17]]
        available = torch.stack([raw[:, :, -1, 17] < 1,
                                 raw[..., 10].amax(dim=-1) > 0, raw[..., 15].amax(dim=-1) > 0], dim=-1)
        if drop is not None:
            available[..., drop] = False
        if self.training:
            # Keep metric availability; randomly omit logs/traces to learn partial-source behavior.
            keep = torch.rand(b, s, 3, device=raw.device) > .15
            keep[..., 0] = True
            original = available.clone()
            available = available & keep
            empty = ~available.any(-1) & original.any(-1)
            available[..., 0] |= empty & original[..., 0]
            empty = ~available.any(-1) & original.any(-1)
            available[..., 1] |= empty & original[..., 1]
            empty = ~available.any(-1) & original.any(-1)
            available[..., 2] |= empty & original[..., 2]
        mask = mask & available.any(-1)
        vectors, gates = [], []
        for i, (encoder, values) in enumerate(zip(self.encoders, modalities)):
            _, h = encoder(values.reshape(b * s, t, -1))
            v = h[-1].reshape(b, s, -1)
            vectors.append(v)
            gates.append(self.gates[i](v).squeeze(-1))
        weights = torch.stack(gates, dim=-1).masked_fill(~available, -1e4).softmax(-1)
        weights = weights * available
        weights = weights / weights.sum(-1, keepdim=True).clamp(min=1e-6)
        fused = (torch.stack(vectors, dim=-2) * weights.unsqueeze(-1)).sum(-2)
        valid = mask.unsqueeze(-1)
        mean = (fused * valid).sum(1) / valid.sum(1).clamp(min=1)
        maximum = fused.masked_fill(~valid, -1e4).amax(1)
        maximum = torch.where(mask.any(-1).unsqueeze(-1), maximum, torch.zeros_like(maximum))
        context = mean.unsqueeze(1).expand(-1, s, -1)
        rank = self.root_head(torch.cat([fused, context], dim=-1)).squeeze(-1).masked_fill(~mask, -1e4)
        detect = self.detect_head(torch.cat([mean, maximum], dim=-1)).squeeze(-1).masked_fill(~mask.any(-1), -1e4)
        return detect, rank


@torch.inference_mode()
def predict(model, data, drop=None):
    model.eval()
    result = []
    for x, mask, y, _, meta in DataLoader(data, batch_size=64, collate_fn=collate):
        detect, rank = model(x.to(DEVICE), mask.to(DEVICE), drop=drop)
        probabilities = detect.sigmoid().cpu().numpy()
        ranks = rank.cpu().numpy()
        for i, m in enumerate(meta):
            ranking = [m['services'][j] for j in np.argsort(-ranks[i, :len(m['services'])]) if mask[i, j] and ranks[i,j] > -9999]
            result.append(dict(**m, score=float(probabilities[i]), anomalous=bool(y[i]), ranking=ranking,
                               abstained=not bool(ranking)))
    return result


def metrics(rows, thresholds):
    annotated = [dict(r, alert=r['score'] > thresholds[r['system']]) for r in rows]
    cases = defaultdict(list)
    for row in annotated:
        cases[row['case']].append(row)
    hits, top1, top3, delays = 0, 0, 0, []
    for events in cases.values():
        first = next((r for r in sorted(events, key=lambda r:r['end']) if r['anomalous'] and r['alert']), None)
        if first:
            hits += 1
            top1 += first['root_cause'] in first['ranking'][:1]
            top3 += first['root_cause'] in first['ranking'][:3]
            delays.append(first['end'] - first['inject_time'])
    return dict(overall=summarize(annotated), cases=len(cases), incident_recall=hits / len(cases),
                top1_at_first_alert=top1 / len(cases), top3_at_first_alert=top3 / len(cases),
                median_detection_delay_seconds=float(np.median(delays)) if delays else None,
                by_system={s:summarize([r for r in annotated if r['system'] == s]) for s in ['ob', 'ss', 'tt']})


def calibrate(rows):
    return {s:float(np.quantile([r['score'] for r in rows if r['system'] == s and not r['anomalous']], .995)) for s in ['ob', 'ss', 'tt']}


def train(epochs=12):
    if not (OUT / 'trace_preparation_report.json').exists():
        raise RuntimeError('Finish trace preprocessing before model training')
    random.seed(42); np.random.seed(42); torch.manual_seed(42)
    torch.set_num_threads(4)
    started = time.perf_counter()
    training, validation = WindowDataset('train'), WindowDataset('validation')
    model = TemporalFusion().to(DEVICE)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-4)
    positives = sum(i['y'] for i in training.items)
    criterion = nn.BCEWithLogitsLoss(pos_weight=torch.tensor((len(training)-positives)/max(positives,1), device=DEVICE))
    loader = DataLoader(training, batch_size=32, shuffle=True, collate_fn=collate, generator=torch.Generator().manual_seed(42))
    history, best, stale = [], -1., 0
    OUT.mkdir(parents=True, exist_ok=True)
    for epoch in range(1, epochs + 1):
        model.train(); total = 0
        for x, mask, y, root, _ in loader:
            x, mask, y, root = x.to(DEVICE), mask.to(DEVICE), y.to(DEVICE), root.to(DEVICE)
            optimizer.zero_grad(set_to_none=True)
            detect, rank = model(x, mask)
            loss = criterion(detect, y)
            eligible = root >= 0
            if eligible.any():
                loss = loss + .5 * nn.functional.cross_entropy(rank[eligible], root[eligible])
            loss.backward(); nn.utils.clip_grad_norm_(model.parameters(), 1.); optimizer.step()
            total += float(loss.detach()) * len(y)
        rows = predict(model, validation)
        thresholds = calibrate(rows)
        report = metrics(rows, thresholds)
        # Both objectives chosen using validation; no development-test lookup.
        objective = (report['overall']['pr_auc'] + report['top1_at_first_alert']) / 2
        history.append(dict(epoch=epoch, training_loss=total/len(training), validation=report, objective=objective))
        print(f'EPOCH {epoch:02d} loss={total/len(training):.4f} val_PR_AUC={report["overall"]["pr_auc"]:.4f} val_top1={report["top1_at_first_alert"]:.4f}', flush=True)
        if objective > best:
            best, stale = objective, 0
            torch.save(dict(state=model.state_dict(), hidden=32, thresholds=thresholds,
                manifest_sha256=hashlib.sha256((V2 / 'split_manifest.json').read_bytes()).hexdigest(),
                epoch=epoch, features=18, history=HISTORY), OUT / 'temporal_best.pt')
        else:
            stale += 1
        dump(OUT / 'temporal_training_report.json', dict(device=DEVICE, epochs=history, training_cases=training.cases,
            validation_cases=validation.cases, training_windows=len(training), validation_windows=len(validation),
            checkpoint_selection='validation PR-AUC and alert-triggered localization only', test_used=False,
            seconds=round(time.perf_counter()-started,2), parameters=sum(p.numel() for p in model.parameters())))
        if stale >= 4:
            break
    print(f'TRAIN finished: checkpoint {OUT / "temporal_best.pt"}', flush=True)


def evaluate():
    checkpoint = torch.load(OUT / 'temporal_best.pt', map_location=DEVICE, weights_only=True)
    if checkpoint['manifest_sha256'] != hashlib.sha256((V2 / 'split_manifest.json').read_bytes()).hexdigest():
        raise RuntimeError('Manifest changed since training')
    model = TemporalFusion(checkpoint['hidden']).to(DEVICE)
    model.load_state_dict(checkpoint['state'])
    data = WindowDataset('test')
    started = time.perf_counter()
    rows = predict(model, data)
    report = dict(protocol='RCAEval development-test; external final holdout not evaluated',
        checkpoint_epoch=checkpoint['epoch'], thresholds=checkpoint['thresholds'],
        full=metrics(rows, checkpoint['thresholds']),
        missing_logs=metrics(predict(model,data,drop=1),checkpoint['thresholds']),
        missing_traces=metrics(predict(model,data,drop=2),checkpoint['thresholds']),
        seconds=round(time.perf_counter()-started,2),
        limitations=['aggregate log indicators, not semantic text encoder', 'no graph message passing yet',
                     'first five minutes assumed healthy', 'controlled failures; no production pilot'])
    dump(OUT / 'temporal_test_report.json', report)
    dump(OUT / 'temporal_test_predictions.json', rows)
    print(json.dumps(report,indent=2),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('stage',choices=['train','evaluate'])
    parser.add_argument('--epochs',type=int,default=12)
    args = parser.parse_args()
    train(args.epochs) if args.stage == 'train' else evaluate()
