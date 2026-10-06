"""Read-only real-data benchmark and chronological replay of held-out telemetry."""
import json
import hashlib
from functools import lru_cache

import joblib
import pyarrow.parquet as pq
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse

from .research_pipeline import ROOT, DATA, OUT, FEATURES, WINDOW, window_scores
from .streaming import FeatureWindow, StreamStore

app = FastAPI(title='IncidentLab full-data research', version='0.3')
from .live_api import router as live_router
app.include_router(live_router)
from .parameter_serving import router as parameter_router
app.include_router(parameter_router)
from .dashboard_api import router as dashboard_router
app.include_router(dashboard_router)


@app.get('/api/kubernetes/status')
def kubernetes_status():
    directory=ROOT/'artifacts/kubernetes'
    def read(name):
        path=directory/name
        return json.loads(path.read_text(encoding='utf-8')) if path.exists() else None
    return dict(progress=read('progress.json'),report=read('latest_report.json'),
        boundary='Separate laptop kind experiment; no cluster result is inferred from native HTTP trials',
        status='not_executed' if not (directory/'progress.json').exists() else 'see_progress')


@app.get('/api/content/evidence')
def content_evidence(case: str, limit: int = Query(default=20,ge=1,le=100)):
    path=OUT/'log_content_evidence.json'
    if not path.exists():
        raise HTTPException(503,'Log-content evaluation is not complete')
    report=json.loads((OUT/'log_content_development_report.json').read_text())
    if case not in {r['case'] for r in report['cases']}:
        raise HTTPException(404,'Choose a documented content-evaluation case')
    matches=[r for r in json.loads(path.read_text()) if r['case']==case]
    return dict(case=case,total_findings=len(matches),findings=matches[:limit],
                interpretation='Evidence of lexical log drift, not confirmed fault or causal diagnosis')


@lru_cache(maxsize=1)
def stream_store():
    return StreamStore(ROOT/'artifacts/streaming.sqlite3')


@app.post('/api/stream/windows')
def analyze_stream(request: FeatureWindow):
    model, checkpoint = temporal_bundle()
    try:
        return stream_store().analyze(request, model, checkpoint)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc


@app.get('/api/stream/{stream}/history')
def stream_history(stream: str):
    return dict(results=stream_store().history(stream))


@app.get('/api/stream/schema')
def stream_schema():
    from .trace_features import V2
    names=json.loads((V2/'split_manifest.json').read_text())['features']
    return dict(feature_schema='rcaeval-multimodal-v2', features=names+['missing_metric_fraction'],
                window_seconds=60, history_windows=5, profiles=['ob','ss','tt'],
                boundary='Normalized research features. Raw logs/metrics/spans are not accepted by this endpoint.')


@app.get('/research')
def index():
    return FileResponse(ROOT / 'web/research.html')


@app.get('/api/status')
def status():
    reports = {}
    for name, filename in [('preprocessing', 'preprocessing_report.json'), ('training', 'full_training_report.json'),
                           ('validation', 'full_validation_report.json'), ('testing', 'full_test_report.json')]:
        path = OUT / filename
        if path.exists():
            report = json.loads(path.read_text())
            report.pop('cases_audit', None)
            reports[name] = report
    for name, filename in [('trace_preparation','trace_preparation_report.json'),
                           ('temporal_training','temporal_training_report.json'),
                           ('temporal_testing','temporal_test_report.json'),
                           ('supervised_reference','supervised_reference_report.json'),
                           ('external_transfer','anomod_external_report.json'),
                           ('development_monitor','anomod_development_v2_report.json'),
                           ('log_content','log_content_development_report.json'),
                           ('semantic_log_content','semantic_log_content_report.json'),
                           ('openstack_initial','openstack_full_report.json'),
                           ('openstack_sequence','openstack_full_v2_report.json'),
                           ('openstack_parameters','openstack_parameters_v3_report.json'),
                           ('parameter_calibration','openstack_parameters_v4_report.json')]:
        path = OUT / filename
        if path.exists():
            report = json.loads(path.read_text())
            report.pop('cases_audit',None)
            reports[name] = report
    for name, filename in [('input_shift_guardrail','input_shift_guardrail.json'),
                           ('external_score_diagnostics','anomod_score_diagnostics.json')]:
        path=OUT/filename
        if path.exists():reports[name]=json.loads(path.read_text())
    manifest = DATA / 'split_manifest.json'
    cases = []
    if manifest.exists():
        cases = sorted(name for name, split in json.loads(manifest.read_text())['assignments'].items() if split == 'test')
    return dict(reports=reports, test_cases=cases, replay_available=(OUT / 'rcaeval_calibrated.joblib').exists(),
                source='complete author-published RCAEval release', mode='historical telemetry replay; live collectors not connected')


@lru_cache(maxsize=1)
def bundle():
    path = OUT / 'rcaeval_calibrated.joblib'
    if not path.exists():
        raise HTTPException(503, 'Validation must complete before replay')
    return joblib.load(path)


@app.get('/api/replay/{case}')
def replay(case: str, model: str = 'baseline'):
    manifest = json.loads((DATA / 'split_manifest.json').read_text())
    if manifest['assignments'].get(case) != 'test':
        raise HTTPException(404, 'Choose a held-out test case')
    if model == 'temporal':
        return temporal_replay(case)
    if model != 'baseline':
        raise HTTPException(422,'Unknown model')
    model = bundle()
    rows = pq.read_table(DATA / f'{case}.parquet').to_pylist()
    # The system identity selects a validation-calibrated threshold, never a fault label.
    system = case[3:5]
    if system not in model['thresholds']:
        raise HTTPException(422, 'Unsupported system')
    windows = []
    for _, values in sorted(window_scores(model, rows).items()):
        ranked = sorted(values, key=lambda v: v[1], reverse=True)
        candidates = []
        for row, score in ranked[:5]:
            changes = sorted(zip(FEATURES, row['features']), key=lambda v: v[1], reverse=True)
            candidates.append(dict(service=row['service'], score=score,
                                   changes=[dict(feature=k, value=v) for k, v in changes[:3]],
                                   missing_metric_columns=row['metric_columns_missing']))
        windows.append(dict(start=ranked[0][0]['start'], end=ranked[0][0]['end'],
                            alert=ranked[0][1] > model['thresholds'][system],
                            score=ranked[0][1], threshold=model['thresholds'][system], candidates=candidates))
    return dict(case=case, windows=windows, mode='historical replay',
                disclaimer='Statistical service ranking, not confirmed causal diagnosis; ground truth is excluded from scoring.')


@lru_cache(maxsize=1)
def temporal_bundle():
    import torch
    from .temporal_model import TemporalFusion, DEVICE
    from .trace_features import V2
    checkpoint = torch.load(OUT/'temporal_best.pt',map_location=DEVICE,weights_only=True)
    if checkpoint['manifest_sha256'] != hashlib.sha256((V2/'split_manifest.json').read_bytes()).hexdigest():
        raise HTTPException(503,'Temporal feature manifest changed')
    model = TemporalFusion(checkpoint['hidden']).to(DEVICE).eval()
    model.load_state_dict(checkpoint['state'])
    return model,checkpoint


def temporal_replay(case):
    import numpy as np
    import torch
    from .temporal_model import collate, HISTORY, DEVICE
    from .trace_features import V2
    model,checkpoint = temporal_bundle()
    rows = pq.read_table(V2/f'{case}.parquet').to_pylist()
    services=sorted({r['service'] for r in rows})
    ids={s:i for i,s in enumerate(services)}
    first=min(r['window'] for r in rows)
    n=max(r['window'] for r in rows)-first+1
    raw=np.zeros((n,len(services),18),dtype=np.float32)
    observed=np.zeros((n,len(services)),dtype=bool)
    for row in rows:
        w,s=row['window']-first,ids[row['service']]
        raw[w,s,:17]=row['features'];raw[w,s,17]=row['metric_columns_missing']/8
        observed[w,s]=row['metric_columns_missing']<8 or row['features'][10]>0 or row['features'][15]>0
    items=[]
    for w in range(n):
        history=np.zeros((len(services),HISTORY,18),dtype=np.float32)
        segment=raw[max(0,w-HISTORY+1):w+1].transpose(1,0,2)
        history[:,-segment.shape[1]:]=segment
        items.append(dict(x=history,mask=observed[w],y=0,root=-1,meta={}))
    x,mask,_,_,_=collate(items)
    with torch.inference_mode():
        detection,ranking=model(x.to(DEVICE),mask.to(DEVICE))
        probabilities=detection.sigmoid().cpu().numpy()
        ranks=ranking.cpu().numpy()
        weights=ranking.softmax(-1).cpu().numpy()
    names=json.loads((V2/'split_manifest.json').read_text())['features']
    windows=[]
    threshold=checkpoint['thresholds'][case[3:5]]
    for w in range(n):
        candidates=[]
        for s in np.argsort(-ranks[w]):
            if not observed[w,s] or ranks[w,s]<=-9999:
                continue
            changes=sorted(zip(names,raw[w,s,:17].tolist()),key=lambda p:p[1],reverse=True)
            candidates.append(dict(service=services[s],score=float(weights[w,s]),
                changes=[dict(feature=k,value=v) for k,v in changes[:3]],
                missing_metric_columns=int(raw[w,s,17]*8)))
            if len(candidates)==5:
                break
        windows.append(dict(start=rows[0]['start']+w*WINDOW,end=rows[0]['start']+(w+1)*WINDOW,
            alert=bool(probabilities[w]>threshold) and bool(candidates),score=float(probabilities[w]),
            threshold=threshold,candidates=candidates,abstained=not bool(candidates)))
    return dict(case=case,model='temporal gated multimodal GRU',windows=windows,mode='historical replay',
        disclaimer='Ranking weights are not calibrated causal probabilities; no ground-truth labels used during replay.')
