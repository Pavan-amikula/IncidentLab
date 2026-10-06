"""Inspect transfer failure without changing checkpoints, mappings or thresholds."""
import csv
import hashlib
import json
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'artifacts/research'
external=json.loads((OUT/'anomod_external_report.json').read_text())
preparation=json.loads((OUT/'anomod_external_preparation.json').read_text())
predictions=json.loads((OUT/'anomod_external_predictions.json').read_text())
diagnostics={}
for system in ['TT_data','SN_data']:
    rows=[];window_sources={};unknown=set()
    for case in preparation['cases']:
        if case.get('system')!=system or 'excluded' in case:continue
        unknown.update(case['unsupported_services'])
        for row in pq.read_table(ROOT/'data/processed/anomod-external'/case['file']).to_pylist():
            rows.append(row['features']);key=(case['case'],row['window'])
            state=window_sources.setdefault(key,[False]*3)
            for i,condition in enumerate([row['features'][17]<1,row['features'][10]>0,row['features'][15]>0]):
                state[i]|=condition
    x=np.asarray(rows)
    diagnostics[system]=dict(service_rows=len(rows),windows=len(window_sources),
        windows_with_metrics=sum(v[0] for v in window_sources.values()),
        windows_with_logs=sum(v[1] for v in window_sources.values()),
        windows_with_traces=sum(v[2] for v in window_sources.values()),
        missing_metric_fraction_median=float(np.median(x[:,17])),
        feature_p50=np.median(x,axis=0).tolist(),feature_p95=np.percentile(x,95,axis=0).tolist(),
        unsupported_services=sorted(unknown))

# Audit the fixed UTC collector assumption on each SN run using exact original IDs.
clock_audit=[]
for directory in sorted((ROOT/'data/research/AnoMod/SN_data/trace_data').iterdir()):
    if not directory.is_dir() or directory.name.startswith('Normal'):continue
    obj=json.loads((directory/'all_traces.json').read_text())
    raw={(t['traceID'],s['spanID']):s['startTime']/1e6 for t in obj['data'] for s in t['spans']}
    offsets=Counter()
    with (directory/'all_traces.csv').open() as f:
        for row in csv.DictReader(f):
            stamp=datetime.fromisoformat(row['start_time']).replace(tzinfo=timezone.utc).timestamp()
            offsets[round(stamp-raw[(row['trace_id'],row['span_id'])],3)]+=1
    if any(offset!=0 for offset in offsets):raise ValueError('External clock policy violated')
    clock_audit.append(dict(run=directory.name,paired_spans=sum(offsets.values()),zero_offset_verified=True))

report=dict(modality_coverage=diagnostics,clock_audit=clock_audit,
    conclusions=['Only CPU/memory transferred among eight metric kinds; disk/network/request-latency evidence is absent from those slots',
                 'TrainTicket log modality deliberately omitted; diagnosis under this source gap is not the original all-source experiment',
                 'Short trace collection periods and unreferenced services reduce usable evidence',
                 'Healthy full-run scaling differs from five-minute warm-up; reference policy and system shifts are confounded',
                 'Frozen supervised models do not establish cross-system robustness from the RCAEval results',
                 'No new external tuning; these cases become development evidence for future work'],
    checkpoints_unchanged=all(hashlib.sha256((OUT/name).read_bytes()).hexdigest()==digest
                              for name,digest in external['protocol']['models'].items()))
(OUT/'anomod_transfer_analysis.json').write_text(json.dumps(report,indent=2))
lines=['# AnoMod frozen-model transfer results','',
    'All 24 designed fault runs were processed: 12 TrainTicket and 12 SocialNetwork, totaling 355 complete windows. No runs were silently excluded. Models and healthy-reference statistics were fixed before fault inference. No model was retrained or threshold tuned on the external outcomes.','',
    '| Model | Fault runs with alerts | Alert windows |', '|---|---:|---:|']
for name in ['temporal','boosting']:
    v=external['models'][name];lines.append(f"| {name} | {v['alerted_fault_runs']}/24 | {v['alert_windows']}/355 |")
lines += ['', '**Transfer performance is poor.** These are fault-run alert coverage counts, not verified incident recall. Designed faults are run-level annotations; independently reviewed active-fault window labels, recovery times and a separate healthy test run are unavailable. Precision, F1, false alerts/hour, onset delay and root-cause accuracy are therefore not reported.','',
    'The temporal alerts occur in the three SocialNetwork code-stop runs. Boosting alerts occur in two TrainTicket runs. A code-stop alert is not proof the ranked service is the true cause.','',
    '## Source coverage','', '| System | Windows | Metrics present | Logs present | Traces present |', '|---|---:|---:|---:|---:|']
for system,v in diagnostics.items():
    lines.append(f"| {system} | {v['windows']} | {v['windows_with_metrics']} | {v['windows_with_logs']} | {v['windows_with_traces']} |")
lines += ['', 'Coverage means at least one eligible service in that minute, not complete service coverage. Six metric kinds remain missing. Trace presence requires a usable healthy service reference.','',
    '## Interpretation and next experiments','']+['- '+c for c in report['conclusions']]
lines += ['', 'SocialNetwork clock audit verified zero offset for every matched raw/CSV span across all 12 fault runs. TrainTicket logs stay excluded. Its error boolean uses a documented synthetic status indicator; this differs from HTTP codes.','',
    'Next implement portable workload/latency/dependency evidence, a trained log semantic baseline, and service-level evidence retrieval. Validate feature equivalence before further learning. Future model selection must use a fresh held-out dataset or new controlled trials, since these AnoMod results have now been inspected. Lowering thresholds to improve these counts would require an independent healthy test to assess the added alert burden.','',
    '## Reproduce and inspect','', '```powershell', '.\\.venv\\Scripts\\python.exe -m incidentlab.external_evaluation',
    '.\\.venv\\Scripts\\python.exe scripts\\analyze_external_transfer.py','```','',
    'The external protocol refuses silent changes to its thresholds or checkpoint/reference hashes. Raw policy, case preparation audits, predictions, results and source diagnostics are saved under `artifacts/research/anomod_external_*.json` and `anomod_transfer_analysis.json`. Repeating evaluation is verification, not a fresh holdout.']
(ROOT/'docs/external_transfer_results.md').write_text('\n'.join(lines),encoding='utf-8')
print(json.dumps({system:{k:v for k,v in data.items() if k in ['windows','windows_with_metrics','windows_with_logs','windows_with_traces','missing_metric_fraction_median']} for system,data in diagnostics.items()},indent=2))
print('Diagnostic report saved; checkpoints unchanged:',report['checkpoints_unchanged'])
