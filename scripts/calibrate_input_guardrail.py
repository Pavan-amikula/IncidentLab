"""Fit an input-shift abstention guardrail on validation only; never tune AnoMod faults."""
import json,sys
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from incidentlab.temporal_model import WindowDataset

def observable(x):
    dims=list(range(8))
    if x[10]>0:dims.extend([8,9])
    if x[15]>0:dims.extend([11,12,13,14])
    dims.extend([17])
    return dims

def score_rows(rows,bounds):
    results=[]
    for row in rows:
        x=row['features'];dims=observable(x)
        if x[17]>=1 and x[10]<=0 and x[15]<=0:continue
        out=sum(x[i]<bounds[i][0] or x[i]>bounds[i][1] for i in dims)
        results.append(out/len(dims))
    return results

def main():
    validation=WindowDataset('validation');values=[[] for _ in range(18)]
    for item in validation.items:
        for x,m in zip(item['x'][:,-1],item['mask']):
            if m:
                for i in observable(x):values[i].append(float(x[i]))
    bounds=[]
    for a in values:
        if a:bounds.append([float(np.quantile(a,.001)),float(np.quantile(a,.999))])
        else:bounds.append([0.,0.])
    calibration=[]
    for item in validation.items:
        fractions=[]
        for x,m in zip(item['x'][:,-1],item['mask']):
            if m:
                dims=observable(x);fractions.append(sum(x[i]<bounds[i][0] or x[i]>bounds[i][1] for i in dims)/len(dims))
        calibration.append(max(fractions,default=1.))
    threshold=float(np.quantile(calibration,.99,method='higher'))
    cases=json.loads((ROOT/'artifacts/research/anomod_external_preparation.json').read_text())['cases']
    summary={};alarms=[]
    for case in cases:
        if 'excluded' in case:continue
        rows=pq.read_table(ROOT/'data/processed/anomod-external'/case['file']).to_pylist()
        scores=score_rows(rows,bounds);flagged=sum(s>threshold for s in scores)
        summary[case['case']]=dict(eligible_windows=len(scores),high_shift_windows=flagged,
            high_shift_fraction=flagged/max(len(scores),1))
        if flagged:alarms.append((case['case'],flagged,len(scores)))
    result=dict(method='Per-window fraction of observable service-feature values outside the validation 0.1–99.9 percentile range',
        validation_cases=validation.cases,validation_windows=len(validation.items),validation_q99_cutoff=threshold,
        external_cases=len(summary),high_shift_cases=len(alarms),cases=summary,
        flagged=alarms,interpretation='This is an abstention/review signal for input shift, not an anomaly detector or root-cause prediction. RCAEval validation case/system overlap makes it a development guardrail, not independent cross-system calibration.',
        limitations=['Threshold uses RCAEval validation data; the source domain differs from AnoMod.',
                     'Metric missingness is partially observable; six metric dimensions lack compatible external mappings.',
                     'No decision guarantees fault detection; review every high-shift input.'])
    (ROOT/'artifacts/research/input_shift_guardrail.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({k:v for k,v in result.items() if k!='cases'},indent=2))

if __name__=='__main__':main()
