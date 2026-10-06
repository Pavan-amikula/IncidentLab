"""Compare frozen scores on AnoMod healthy-reference and fault-reference windows.

Healthy scores reuse the windows that fitted AnoMod's reference scale, so their normal
alerts are descriptive and optimistically biased, never an independent false-alarm test.
"""
import json
import sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

import joblib
import numpy as np
import pyarrow.parquet as pq
import torch

from incidentlab.external_evaluation import items
from incidentlab.temporal_model import TemporalFusion,DEVICE,HISTORY,collate
from incidentlab.research_pipeline import OUT


def summarize(scores,thresholds):
    values=np.asarray(scores)
    return dict(windows=len(values),p50=float(np.median(values)),p95=float(np.percentile(values,95)),
                maximum=float(values.max()),alerts=int(np.sum(values>thresholds)))


def main():
    policy=json.loads((OUT/'anomod_external_policy.json').read_text())
    reports=json.loads((OUT/'anomod_external_preparation.json').read_text())['cases']
    checkpoint=torch.load(OUT/'temporal_best.pt',map_location=DEVICE,weights_only=True)
    temporal=TemporalFusion(checkpoint['hidden']).to(DEVICE).eval();temporal.load_state_dict(checkpoint['state'])
    boosting=joblib.load(OUT/'supervised_reference.joblib')
    report={'note':'Reference-window score summaries reuse the healthy windows that fit each external normalization; these are optimistically biased development diagnostics, not false alarm rates.', 'systems':{}}
    externalrows=json.loads((OUT/'anomod_external_predictions.json').read_text())
    for system in ['TT_data','SN_data']:
        healthyfile=Path('data/processed/anomod-normal')/f'{system}-healthy-windows.parquet'
        healthycase=dict(case=system+':Normal',system=system,file='anomod-normal/'+healthyfile.name,
                         windows=pq.read_table(healthyfile).column('window').to_numpy().max()+1)
        def scores_for(case,normal):
            if normal:
                rows=pq.read_table(healthyfile).to_pylist();services=sorted({r['service'] for r in rows})
                ids={s:i for i,s in enumerate(services)};count=case['windows'];raw=np.zeros((count,len(services),18),np.float32)
                for row in rows:raw[row['window'],ids[row['service']]]=row['features']
                data=[]
                for w in range(count):
                    hist=np.zeros((len(services),HISTORY,18),np.float32)
                    segment=raw[max(0,w-HISTORY+1):w+1].transpose(1,0,2);hist[:,-segment.shape[1]:]=segment
                    mask=(raw[w,:,17]<1)|(raw[w,:,10]>0)|(raw[w,:,15]>0)
                    data.append(dict(x=hist,mask=mask,y=0,root=-1,meta={}))
            else:services,data=items(case)
            x,mask,_,_,_=collate(data)
            with torch.inference_mode():d,_=temporal(x.to(DEVICE),mask.to(DEVICE))
            ts=d.sigmoid().cpu().numpy()
            bs=[]
            for item in data:
                ix=np.flatnonzero(item['mask'])
                if not len(ix):continue
                cur=np.log1p(item['x'][:,-1].clip(min=0));ctx=cur[ix].mean(0)
                bs.append(boosting['detector'].predict_proba(np.concatenate([ctx,cur[ix].max(0)])[None])[0,1])
            return ts,bs
        for normal,case in [(True,healthycase),(False,None)]:
            ts=[];bs=[]
            selected=[case] if normal else [a for a in reports if a.get('system')==system and 'excluded' not in a]
            for c in selected:
                a,b=scores_for(c,normal);ts.extend(a);bs.extend(b)
            report['systems'].setdefault(system,{})['healthy_reference_windows' if normal else 'fault_run_windows']={
                'temporal':summarize(ts,policy['thresholds']['temporal'][system]),
                'boosting':summarize(bs,policy['thresholds']['boosting'][system])}
    report['interpretation']='Low fault-run scores alongside low in-reference scores indicate source/domain calibration shift. In-reference alert burden is not independent and cannot set deployment thresholds.'
    (OUT/'anomod_score_diagnostics.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
