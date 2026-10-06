"""Versioned early-window and availability diagnostics; AnoMod is development data now."""
import json
import time
from concurrent.futures import ThreadPoolExecutor

import joblib
import pyarrow.parquet as pq
import torch

from .anomod_healthy import BASE,DEST
from .coverage_guard import CoverageGuard,fit_inventory
from .external_evaluation import freeze,sha,prepare_case,evaluate_case
from .research_pipeline import ROOT,OUT,dump
from .temporal_model import DEVICE,TemporalFusion

V2=DEST.parent/'anomod-development-v2'


def run():
    started=time.perf_counter();V2.mkdir(parents=True,exist_ok=True)
    baseline=freeze();bundles={}
    for system in ['TT_data','SN_data']:
        bundles[system]=fit_inventory(pq.read_table(DEST/f'{system}-healthy-windows.parquet').to_pylist())
    protocol=dict(status='Development revision after inspecting original AnoMod results; not final held-out accuracy',
        base_policy_sha256=sha(OUT/'anomod_external_policy.json'),models=baseline['models'],
        alert_thresholds=baseline['thresholds'],startup_exclusion_seconds=0,
        sources={name:sha(ROOT/'incidentlab'/name) for name in
                 ['external_evaluation.py','coverage_guard.py','development_monitor.py']},
        changes=['retain expected healthy services even when observations vanish',
                 'do not discard five minutes at the start of a fault run',
                 'independent expected-metric-availability guard; no root-cause or down-service claim'],
        inventories=bundles,no_model_retraining=True,no_threshold_tuning=True)
    dump(OUT/'anomod_development_v2_protocol.json',protocol)
    checkpoint=torch.load(OUT/'temporal_best.pt',map_location=DEVICE,weights_only=True)
    model=TemporalFusion(checkpoint['hidden']).to(DEVICE).eval();model.load_state_dict(checkpoint['state'])
    boosting=joblib.load(OUT/'supervised_reference.joblib')
    tasks=[(s,p) for s in ['TT_data','SN_data'] for p in sorted((BASE/s/'metric_data').iterdir())
           if p.is_dir() and not p.name.startswith('Normal')]
    summaries=[];predictions=[];audits=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(prepare_case,s,p,startup_seconds=0,destination=V2,include_expected=True) for s,p in tasks]
        for i,future in enumerate(futures,1):
            audit=future.result();audits.append(audit)
            if 'excluded' in audit:
                print(audit['case']+' excluded: '+audit['excluded'],flush=True);continue
            summary,rows=evaluate_case(audit,model,boosting,baseline,destination=V2)
            grouped={}
            for row in pq.read_table(V2/audit['file']).to_pylist():
                group=grouped.setdefault(row['window'],set())
                if row['features'][17]<1:group.add(row['service'])
            guard=CoverageGuard(bundles[audit['system']]);warning_windows=0;insufficient=0;services=set()
            for row in rows:
                coverage=guard.step(row['end'],grouped[row['window']]);row['coverage']=coverage
                warning_windows+=bool(coverage['issues']);insufficient+=coverage['state']=='insufficient_telemetry'
                services.update(issue['service'] for issue in coverage['issues'])
            summary.update(coverage_warning_windows=warning_windows,coverage_warning_services=sorted(services),
                           insufficient_coverage_windows=insufficient)
            summaries.append(summary);predictions.extend(rows)
            print(f"Development monitor {i}/24: {audit['case']} ({audit['windows']} windows)",flush=True)
    original=json.loads((OUT/'anomod_external_report.json').read_text())
    report=dict(protocol=protocol,designed_fault_runs=len(tasks),evaluated_runs=len(summaries),windows=len(predictions),
        excluded_runs=[a for a in audits if 'excluded' in a],cases=summaries,
        models={name:dict(alerted_fault_runs=sum(c[name]['fault_run_alerted'] for c in summaries),
                         alert_windows=sum(c[name]['alert_windows'] for c in summaries),
                         original_alerted_fault_runs=original['models'][name]['alerted_fault_runs'])
                for name in ['temporal','boosting']},
        coverage=dict(runs_with_warnings=sum(c['coverage_warning_windows']>0 for c in summaries),
                      warning_windows=sum(c['coverage_warning_windows'] for c in summaries),
                      insufficient_windows=sum(c['insufficient_coverage_windows'] for c in summaries)),
        checkpoints_unchanged=all(sha(OUT/name)==digest for name,digest in baseline['models'].items()),
        limitations=['More windows create more opportunities to alert; counts are not directly comparable recall',
                     'Coverage warnings indicate missing metric samples, not confirmed service outages',
                     'Cases and startup timestamps lack independent active-fault interval labels',
                     'Underlying trained-model transfer limitations remain; six metric categories and TT logs missing',
                     'Fresh controls and unseen data needed before reliability or improvement claims'],
        seconds=round(time.perf_counter()-started,2))
    dump(OUT/'anomod_development_v2_predictions.json',predictions)
    dump(OUT/'anomod_development_v2_report.json',report)
    dump(OUT/'anomod_development_v2_preparation.json',audits)
    print(json.dumps({k:report[k] for k in ['evaluated_runs','windows','models','coverage','checkpoints_unchanged','seconds']},indent=2))


if __name__=='__main__':run()
