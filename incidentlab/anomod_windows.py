"""Complete healthy windows and reference statistics; no fault predictions."""
import json
import warnings
from collections import defaultdict

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from .anomod_healthy import DEST
from .research_pipeline import OUT,dump


def complete_bounds(timestamps):
    return int(np.ceil(min(timestamps)/60)*60),int(np.floor(max(timestamps)/60)*60)


def reference(values):
    """Only supplied healthy-reference values. Preserve missingness explicitly."""
    counts=np.isfinite(values).sum(0)
    with warnings.catch_warnings():
        warnings.simplefilter('ignore',RuntimeWarning)
        center=np.nanmedian(values,axis=0);scale=np.nanstd(values,axis=0)
    scale=np.maximum(scale,np.maximum(np.abs(center)*.05,1e-6))
    return center,scale,counts


def change(row,center,scale):
    result=np.abs(row-center)/scale
    return np.clip(np.nan_to_num(result,nan=0,posinf=100,neginf=0),0,100)


def prepare(system):
    metrics=pq.read_table(DEST/f'{system}-metrics.parquet').to_pylist()
    start,end=complete_bounds([m['timestamp'] for m in metrics]);n=(end-start)//60
    grouped=defaultdict(lambda: defaultdict(list))
    for row in metrics:
        w=int((row['timestamp']-start)//60)
        if 0<=w<n:grouped[row['service']][(w,row['kind'])].append(row['value'])
    log_path=DEST/f'{system}-logs.parquet'
    counts=defaultdict(lambda:np.zeros((n,2)))
    if log_path.exists():
        for batch in pq.ParquetFile(log_path).iter_batches(batch_size=32768):
            for row in batch.to_pylist():
                w=int((row['timestamp']-start)//60)
                if 0<=w<n:
                    counts[row['service']][w]+=[1,row['error_indicator']]
    trace_path=DEST/(f'{system}-spans-aligned.parquet' if system=='SN_data' else f'{system}-spans.parquet')
    spans=pq.read_table(trace_path).to_pylist()
    traces=defaultdict(lambda:np.zeros((n,5)))
    for row in spans:
        if row['timestamp_epoch_seconds'] is None:raise ValueError('Unresolved trace epoch')
        w=int((row['timestamp_epoch_seconds']-start)//60)
        if 0<=w<n:
            v=traces[row['service']][w];v[0]+=1;v[1]+=row['duration_us'];v[2]=max(v[2],row['duration_us'])
            if row['status_code'] is not None:
                v[4]+=1;v[3]+=row['status_code']!=0 and not 200<=row['status_code']<400
    rows=[];refs={};coverage={}
    for service in sorted(set(grouped)|set(counts)|set(traces)):
        raw=np.full((n,14),np.nan)
        for w in range(n):
            for j,kind in enumerate(['cpu','mem']):
                vals=grouped[service].get((w,kind),[])
                if vals:raw[w,j]=np.mean(vals)
        log=counts[service];trace=traces[service]
        if log_path.exists() and service in counts and log[:,0].sum()>0:
            raw[:,8]=np.log1p(log[:,0]);raw[:,9]=np.divide(log[:,1],log[:,0],out=np.zeros(n),where=log[:,0]>0)
        active=trace[:,0]>0
        raw[active,10]=np.log1p(trace[active,0]);raw[active,11]=trace[active,1]/trace[active,0]
        raw[active,12]=trace[active,2]
        known=trace[:,4]>0;raw[known,13]=trace[known,3]/trace[known,4]
        center,scale,observations=reference(raw)
        refs[service]=dict(center=[None if not np.isfinite(v) else float(v) for v in center],
            scale=[None if not np.isfinite(v) else float(v) for v in scale],observations=observations.tolist())
        coverage[service]=dict(cpu_windows=int(observations[0]),memory_windows=int(observations[1]),
                              log_windows=int((log[:,0]>0).sum()),trace_windows=int(active.sum()))
        for w in range(n):
            v=change(raw[w],center,scale)
            features=np.concatenate([v[:8],v[8:10],[float(log[w,0]>0)],v[10:14],
                [float(active[w]),trace[w,4]/trace[w,0] if active[w] else 0],
                [float(np.isnan(raw[w,:8]).sum()/8)]])
            rows.append(dict(service=service,window=w,start=start+w*60,end=start+(w+1)*60,
                             features=features.tolist()))
    pq.write_table(pa.Table.from_pylist(rows),DEST/f'{system}-healthy-windows.parquet',compression='zstd')
    dump(DEST/f'{system}-healthy-reference.json',dict(system=system,reference_scope='Complete designated normal run only',
         fitting_normal_run_is_not_an_independent_false_alert_test=True,services=refs))
    return dict(complete_windows=n,service_rows=len(rows),start=start,end=end,coverage=coverage)


def main():
    report=dict(scope='Healthy-reference preparation only; no model inference or external fault evaluation',
        systems={system:prepare(system) for system in ['TT_data','SN_data']},
        limitations=['full healthy run used for reference fitting; cannot report unbiased false alerts on that same run',
                     'six of eight metric kinds unavailable; logged as missing rather than mapped to unrelated signals',
                     'short and sparse trace references; source coverage must accompany external results',
                     'SocialNetwork log UTC alignment inferred; TrainTicket logs excluded until source offset verified'])
    dump(OUT/'anomod_window_preparation.json',report)
    print(json.dumps({k:dict(complete_windows=v['complete_windows'],service_rows=v['service_rows'])
                      for k,v in report['systems'].items()},indent=2))


if __name__=='__main__':main()
