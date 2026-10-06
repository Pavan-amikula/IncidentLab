"""Development delay-calibration comparison; no fault-label-derived thresholds."""
import hashlib
import json

import joblib
import numpy as np
from sklearn.metrics import precision_recall_fscore_support,average_precision_score

from .openstack_parameters import BASE,OPERATIONS,parse_parameters,vector
from .research_pipeline import OUT,dump

ALPHA=.01


def tail_probabilities(matrix,references):
    probabilities=np.full(matrix.shape,np.nan)
    for column,operation in enumerate(OPERATIONS):
        reference=np.asarray(references[operation])
        if len(reference)<50:
            raise ValueError('Insufficient healthy calibration for an operation')
        observed=np.isfinite(matrix[:,column])
        values=matrix[observed,column]
        # Include ties in the upper tail; plus one prevents invented zero p-values.
        greater_equal=len(reference)-np.searchsorted(reference,values,side='left')
        probabilities[observed,column]=(1+greater_equal)/(1+len(reference))
    available=np.isfinite(probabilities)
    combined=np.minimum(1,len(OPERATIONS)*np.min(np.where(available,probabilities,np.inf),axis=1))
    combined[~available.any(axis=1)]=np.nan
    return probabilities,combined


def run():
    splits=json.loads((OUT/'openstack_split_manifest.json').read_text())
    normal,normal_audit=parse_parameters(BASE/'openstack_normal2.log')
    abnormal,abnormal_audit=parse_parameters(BASE/'openstack_abnormal.log')
    calibration=np.stack([vector(normal[key]) for key in splits['validation']])
    references={operation:np.sort(calibration[np.isfinite(calibration[:,i]),i])
                for i,operation in enumerate(OPERATIONS)}
    # Reuse the existing trained parameter IF/scaling as a declared ML control.
    base=joblib.load(OUT/'openstack_parameter_models_v3.joblib')
    model=dict(**base,rank_references=references,alpha=ALPHA,
        selected_policy='Four-operation conservative empirical upper-tail rank',
        note='Healthy normal2 calibration only; one-sided delay question, development after inspected V3 results')
    checkpoint=OUT/'openstack_parameter_models_v4.joblib'
    joblib.dump(model,checkpoint)
    frozen=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    predictions=json.loads((OUT/'openstack_parameters_v3_predictions.json').read_text())
    matrix=np.stack([vector((normal if row['source']=='normal2' else abnormal)[row['instance']]) for row in predictions])
    probabilities,combined=tail_probabilities(matrix,references)
    # Annotation access begins after calibrator freeze; these outcomes were already
    # inspected in prior development, so this remains a development comparison.
    truth=np.array([row['annotation'] for row in predictions])
    available=np.isfinite(combined)
    warned=available & (combined<=ALPHA)
    precision,recall,f1,_=precision_recall_fscore_support(truth,warned,average='binary',zero_division=0)
    result=dict(precision=float(precision),recall=float(recall),f1=float(f1),
        annotated_positive_hits=int((warned&(truth==1)).sum()),annotated_positive_sessions=int(truth.sum()),
        alerted_sessions=int(warned.sum()),false_alerted_normal2_sessions=int(sum(
            bool(value) and row['source']=='normal2' for value,row in zip(warned,predictions))),
        average_precision_eligible=float(average_precision_score(truth[available],-combined[available])),
        abstained_sessions=int((~available).sum()))
    rows=[dict(instance=row['instance'],source=row['source'],annotation=row['annotation'],
        combined_tail_pvalue=float(combined[i]) if available[i] else None,
        operation_tail_pvalues={name:float(probabilities[i,j]) if np.isfinite(probabilities[i,j]) else None
                               for j,name in enumerate(OPERATIONS)},warning=bool(warned[i]))
        for i,row in enumerate(predictions)]
    report=dict(scope='Development comparison of operation-specific tail calibration after inspecting V3 outcomes',
        alpha=ALPHA,calibration_sessions=len(splits['validation']),
        calibration_counts={name:len(value) for name,value in references.items()},
        healthy_normal2_test_sessions=len(splits['normal2_test']),
        results=result,checkpoint_sha256=frozen,audits=dict(normal2=normal_audit,abnormal=abnormal_audit),
        limitations=['Four already-inspected positives; no fresh final-test claim or outcome-based alpha tuning',
            'One-sided operation delay question differs from V3 two-sided residual novelty',
            'Ordered/censored log sessions can violate exchangeability; nominal alpha is not verified production false-alarm rate',
            'Tail p-values are not probabilities that a VM or service is faulty',
            'Missing operations remain explicit; no-duration sessions abstain',
            'Unannotated abnormal-file sessions follow the supplied four-UUID label policy, which may be incomplete'])
    dump(OUT/'openstack_parameters_v4_predictions.json',rows)
    dump(OUT/'openstack_parameters_v4_report.json',report)
    print(json.dumps(result,indent=2))


if __name__=='__main__':run()
