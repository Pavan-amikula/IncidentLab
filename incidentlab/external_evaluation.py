"""Frozen-model AnoMod transfer evaluation with declared healthy-reference adaptation."""
import hashlib
import json
import math
import re
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime,timezone

import joblib
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
import torch

from .anomod_healthy import BASE,DEST,tt_metrics,sn_metrics,sn_logs
from .anomod_adapter import normalize_tt_span,normalize_sn_span
from .anomod_windows import complete_bounds,change
from .research_pipeline import OUT,dump
from .temporal_model import TemporalFusion,DEVICE,HISTORY,collate

EXTERNAL=DEST.parent/'anomod-external';POLICY=OUT/'anomod_external_policy.json'


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def freeze():
    model_paths=[OUT/'temporal_best.pt',OUT/'supervised_reference.joblib']
    checkpoint=torch.load(model_paths[0],map_location='cpu',weights_only=True)
    reference=joblib.load(model_paths[1])
    policy=dict(version='anomod-transfer-v1',models={p.name:sha(p) for p in model_paths},
        references={s:sha(DEST/f'{s}-healthy-reference.json') for s in ['TT_data','SN_data']},
        reference_access='Whole author-designated healthy run only; fixed robust scaling; no model retraining',
        thresholds=dict(temporal={'TT_data':checkpoint['thresholds']['tt'],'SN_data':max(checkpoint['thresholds'].values())},
                        boosting={'TT_data':reference['thresholds']['tt'],'SN_data':max(reference['thresholds'].values())}),
        unseen_system_policy='SN uses maximum existing RCAEval system threshold, chosen before fault inference',
        interval_policy='Complete minutes within metric coverage; begin at least 300 seconds after nominal case-start timestamp',
        labels='Case directories denote designed fault runs. Per-window active-fault ground truth not available.',
        scoring='Fault-run alert coverage and window alert fraction; no precision, F1, detection-delay or healthy false-alert claims',
        sources='CPU/memory and traces; SocialNetwork logs. TrainTicket logs excluded for unresolved timezone.',
        unsupported_service='No healthy reference => all sources unavailable and service excluded from ranking',
        source_changes='Synthetic SkyWalking error indicator; six unmapped metric kinds explicit missing',
        no_external_tuning=True)
    if POLICY.exists():
        if json.loads(POLICY.read_text())!=policy:
            raise RuntimeError('Existing external policy differs; preserve its results rather than silently re-tune')
    else:dump(POLICY,policy)
    return policy


def run_key(system,name):
    return name.split('_metrics_')[0] if system=='SN_data' else name


def case_start(name):
    match=re.search(r'(\d{8})[T_](\d{6})',name)
    if not match:raise ValueError('Case-start timestamp missing')
    return datetime.strptime(''.join(match.groups()),'%Y%m%d%H%M%S').replace(tzinfo=timezone.utc).timestamp()


def modality_directory(system,modality,key):
    matches=[p for p in (BASE/system/modality).iterdir() if p.is_dir() and p.name.startswith(key)]
    if len(matches)!=1:raise ValueError(f'Ambiguous or missing modality directory: {system}/{modality}/{key}')
    return matches[0]


def prepare_case(system,path,startup_seconds=300,destination=None,include_expected=False):
    key=run_key(system,path.name);case=f'{system}:{key}'
    metrics,audit=(tt_metrics if system=='TT_data' else sn_metrics)(path)
    if not metrics:raise ValueError('No supported application metrics')
    start,end=complete_bounds([r['timestamp'] for r in metrics])
    start=max(start,int(math.ceil((case_start(key)+startup_seconds)/60)*60));n=(end-start)//60
    if n<1:return dict(case=case,system=system,excluded='no complete windows after fixed startup exclusion',metric_audit=audit)
    grouped=defaultdict(lambda:defaultdict(list))
    for row in metrics:
        w=int((row['timestamp']-start)//60)
        if 0<=w<n:grouped[row['service']][(w,row['kind'])].append(row['value'])
    logs=defaultdict(lambda:np.zeros((n,2)));log_audit={}
    if system=='SN_data':
        values,log_audit=sn_logs(modality_directory(system,'log_data',key))
        for row in values:
            w=int((row['timestamp']-start)//60)
            if 0<=w<n:logs[row['service']][w]+=[1,row['error_indicator']]
        del values
    traces=defaultdict(lambda:np.zeros((n,5)));outside=unresolved=trace_rows=0
    td=modality_directory(system,'trace_data',key)
    if system=='TT_data':
        files=list(td.glob('*.json'))
        if len(files)!=1:raise ValueError('Unexpected trace file count')
        obj=json.loads(files[0].read_text())
        iterator=(normalize_tt_span(s) for t in obj['traces'] for s in t['spans']);handle=None
    else:
        # Exact raw epochs avoid extrapolating the healthy collector timezone to fault runs.
        obj=json.loads((td/'all_traces.json').read_text())
        epochs={(t['traceID'],s['spanID']):s['startTime']/1e6 for t in obj['data'] for s in t['spans']}
        import csv
        handle=(td/'all_traces.csv').open(newline='',encoding='utf-8')
        def iterator_sn():
            for r in csv.DictReader(handle):
                value=normalize_sn_span(r)
                value['timestamp_epoch_seconds']=epochs[(r['trace_id'],r['span_id'])]
                yield value
        iterator=iterator_sn()
    try:
        for row in iterator:
            trace_rows+=1
            w=int((row['timestamp_epoch_seconds']-start)//60)
            if not 0<=w<n:outside+=1;continue
            v=traces[row['service']][w];v[0]+=1;v[1]+=row['duration_us'];v[2]=max(v[2],row['duration_us'])
            if row['status_code'] is not None:
                v[4]+=1;v[3]+=row['status_code']!=0 and not 200<=row['status_code']<400
    finally:
        if handle:handle.close()
    refs=json.loads((DEST/f'{system}-healthy-reference.json').read_text())['services']
    rows=[];unreferenced=[]
    inventory=set(grouped)|set(logs)|set(traces)
    if include_expected:inventory|=set(refs)
    for service in sorted(inventory):
        if service not in refs:unreferenced.append(service)
        r=refs.get(service,dict(center=[None]*14,scale=[None]*14))
        center=np.asarray(r['center'],dtype=float);scale=np.asarray(r['scale'],dtype=float)
        log=logs[service];trace=traces[service]
        for w in range(n):
            raw=np.full(14,np.nan)
            for j,kind in enumerate(['cpu','mem']):
                values=grouped[service].get((w,kind),[])
                if values:raw[j]=np.mean(values)
            lp=system=='SN_data' and log[w,0]>0 and np.isfinite(center[8:10]).all()
            if lp:raw[8]=np.log1p(log[w,0]);raw[9]=log[w,1]/log[w,0]
            tp=trace[w,0]>0 and np.isfinite(center[10:13]).all()
            if tp:
                raw[10]=np.log1p(trace[w,0]);raw[11]=trace[w,1]/trace[w,0];raw[12]=trace[w,2]
                if trace[w,4]>0:raw[13]=trace[w,3]/trace[w,4]
            values=change(raw,center,scale)
            missing=(~np.isfinite(raw[:8])|~np.isfinite(center[:8])).sum()/8
            feature=np.concatenate([values[:8],values[8:10],[float(lp)],values[10:14],
                [float(tp),trace[w,4]/trace[w,0] if tp else 0],[missing]])
            rows.append(dict(service=service,window=w,start=start+w*60,end=start+(w+1)*60,features=feature.tolist()))
    filename=(destination or EXTERNAL)/(system+'-'+key+'.parquet')
    pq.write_table(pa.Table.from_pylist(rows),filename,compression='zstd')
    return dict(case=case,system=system,file=filename.name,windows=n,start=start,end=end,
                metric_audit=audit,log_audit=log_audit,trace_rows=trace_rows,trace_rows_outside_interval=outside,
                unsupported_services=unreferenced)


def items(audit,destination=None):
    rows=pq.read_table((destination or EXTERNAL)/audit['file']).to_pylist();services=sorted({r['service'] for r in rows})
    ids={name:i for i,name in enumerate(services)};n=audit['windows']
    raw=np.zeros((n,len(services),18),dtype=np.float32)
    for row in rows:raw[row['window'],ids[row['service']]]=row['features']
    result=[]
    for w in range(n):
        history=np.zeros((len(services),HISTORY,18),dtype=np.float32)
        segment=raw[max(0,w-HISTORY+1):w+1].transpose(1,0,2);history[:,-segment.shape[1]:]=segment
        active=(raw[w,:,17]<1)|(raw[w,:,10]>0)|(raw[w,:,15]>0)
        result.append(dict(x=history,mask=active,y=0,root=-1,meta={}))
    return services,result


def evaluate_case(audit,temporal,boosting,policy,destination=None):
    services,data=items(audit,destination);x,mask,_,_,_=collate(data)
    with torch.inference_mode():
        detect,rank=temporal(x.to(DEVICE),mask.to(DEVICE));scores=detect.sigmoid().cpu().numpy();ranks=rank.cpu().numpy()
    predictions=[]
    for w,item in enumerate(data):
        active=np.flatnonzero(item['mask'])
        result=dict(case=audit['case'],window=w,end=audit['start']+(w+1)*60,abstained=len(active)==0)
        if not len(active):result.update(temporal=None,boosting=None)
        else:
            current=np.log1p(item['x'][:,-1].clip(min=0));context=current[active].mean(0)
            features=np.concatenate([context,current[active].max(0)])[None]
            bscore=float(boosting['detector'].predict_proba(features)[0,1])
            rfeatures=np.concatenate([current[active],np.tile(context,(len(active),1))],axis=1)
            root=boosting['ranker'].predict_proba(rfeatures)[:,1]
            trank=[services[j] for j in np.argsort(-ranks[w]) if item['mask'][j] and ranks[w,j]>-9999][:3]
            brank=[services[active[j]] for j in np.argsort(-root)[:3]]
            result.update(temporal=dict(score=float(scores[w]),alert=bool(scores[w]>policy['thresholds']['temporal'][audit['system']]),ranking=trank),
                          boosting=dict(score=bscore,alert=bscore>policy['thresholds']['boosting'][audit['system']],ranking=brank))
        predictions.append(result)
    summary=dict(case=audit['case'],system=audit['system'],windows=len(data),abstained_windows=sum(p['abstained'] for p in predictions))
    for name in ['temporal','boosting']:
        alerts=[p for p in predictions if p[name] and p[name]['alert']]
        summary[name]=dict(alert_windows=len(alerts),fault_run_alerted=bool(alerts),
            first_alert_candidates=alerts[0][name]['ranking'] if alerts else [])
    return summary,predictions


def run():
    started=time.perf_counter();EXTERNAL.mkdir(parents=True,exist_ok=True);policy=freeze()
    print('External protocol frozen before fault telemetry and predictions.',flush=True)
    tasks=[(s,p) for s in ['TT_data','SN_data'] for p in sorted((BASE/s/'metric_data').iterdir())
           if p.is_dir() and not p.name.startswith('Normal')]
    audits=[]
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures=[pool.submit(prepare_case,s,p) for s,p in tasks]
        for i,future in enumerate(futures,1):
            try:audit=future.result()
            except Exception as exc:audit=dict(case=f'{tasks[i-1][0]}:{tasks[i-1][1].name}',excluded=str(exc))
            audits.append(audit);print(f'External preparation {i}/{len(tasks)}: '+audit['case']+(' EXCLUDED '+audit['excluded'] if 'excluded' in audit else f" {audit['windows']} windows"),flush=True)
    dump(OUT/'anomod_external_preparation.json',dict(policy_sha256=sha(POLICY),cases=audits))
    checkpoint=torch.load(OUT/'temporal_best.pt',map_location=DEVICE,weights_only=True)
    model=TemporalFusion(checkpoint['hidden']).to(DEVICE).eval();model.load_state_dict(checkpoint['state'])
    boosting=joblib.load(OUT/'supervised_reference.joblib');summaries=[];predictions=[]
    for audit in audits:
        if 'excluded' in audit:continue
        summary,rows=evaluate_case(audit,model,boosting,policy);summaries.append(summary);predictions.extend(rows)
        print('Evaluated '+audit['case'],flush=True)
    totals={name:dict(eligible_fault_runs=len(summaries),alerted_fault_runs=sum(s[name]['fault_run_alerted'] for s in summaries),
                      alert_windows=sum(s[name]['alert_windows'] for s in summaries)) for name in ['temporal','boosting']}
    for path,expected in policy['models'].items():
        if sha(OUT/path)!=expected:raise RuntimeError('Checkpoint changed during external evaluation')
    report=dict(protocol=policy,policy_sha256=sha(POLICY),designed_fault_runs=len(tasks),evaluated_runs=len(summaries),
        excluded_runs=[a for a in audits if 'excluded' in a],windows=len(predictions),models=totals,cases=summaries,
        seconds=round(time.perf_counter()-started,2),
        limitations=['Fault-run alerts are not verified incident recall; active-fault timestamps and recovery labels unavailable',
                     'No independent healthy run: precision/F1/false alerts per hour and onset delay not calculated',
                     'No verified service ground truth used: candidate rankings are reported without root-cause accuracy',
                     'Sparse modalities and healthy-reference distribution adaptation differ from original RCAEval protocol',
                     'External data now evaluated; future tuning requires a fresh final holdout'])
    dump(OUT/'anomod_external_predictions.json',predictions);dump(OUT/'anomod_external_report.json',report)
    print(json.dumps({k:report[k] for k in ['designed_fault_runs','evaluated_runs','windows','models','seconds']},indent=2))


if __name__=='__main__':run()
