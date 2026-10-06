"""Replay actual archived raw HTTP evidence through transactional observation."""
import hashlib
import argparse
import json
import time
import uuid

from incidentlab.native_experiment import OUT, save
from incidentlab.native_observer import NativeObserver, native_bundle, status, DATABASE


def main():
    from incidentlab.live_api import PHASES
    import re
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-id',default='20261005T200503-c9862c')
    parser.add_argument('--phase',default='test_error_checkout',choices=PHASES)
    args=parser.parse_args()
    run_id,phase=args.run_id,args.phase
    if not re.fullmatch(r'\d{8}T\d{6}-[0-9a-f]{6}',run_id):
        parser.error('Invalid run ID')
    source=OUT/run_id/phase
    expected=json.loads((source/'predictions.json').read_text())
    if not expected:
        parser.error('Choose a completed test trial with predictions')
    bundle,digest=native_bundle(run_id)
    stream='raw-replay-'+uuid.uuid4().hex[:8]
    latencies=[]
    for i,prediction in enumerate(expected):
        # Reconstruct the observer each time: offsets/future records/incident state
        # must come from SQLite rather than a surviving Python object.
        observer=NativeObserver(DATABASE)
        began=time.perf_counter()
        result=observer.observe(stream,source,prediction['start'],prediction['end'],bundle,digest)
        latencies.append((time.perf_counter()-began)*1000)
        assert result['ml_alert']==prediction['ml_alert']
        assert result['operational_alert']==prediction['operational_alert']
        measured={r['service']:r for r in result['candidates']}
        for reference in prediction['candidates']:
            actual=measured[reference['service']]
            assert actual['count']==reference['count'] and actual['features']==reference['features']
    values=status(DATABASE,stream)
    assert len(values['predictions'])==len(expected)
    try:
        observer.observe(stream,source,expected[-1]['start'],expected[-1]['end'],bundle,digest)
    except ValueError:
        pass
    else:
        raise RuntimeError('Duplicate observation was accepted')
    assert len(status(DATABASE,stream)['predictions'])==len(expected)
    report=dict(status='passed', source_run=run_id, phase=phase, stream=stream,
        windows_verified=len(expected), restarts=len(expected)-1,
        exact_feature_match=True, duplicate_rejected=True, checkpoint_sha256=digest,
        raw_sha256={name:hashlib.sha256((source/f'{name}.jsonl').read_bytes()).hexdigest()
                    for name in ('frontend','checkout','inventory')},
        incident=values['streams'][0]['incident'],
        processing_mean_ms=sum(latencies)/len(latencies),
        scope='Actual archived HTTP raw-event replay; exact offline match and durable restart, not a fresh live accuracy trial')
    save(OUT/'native_observer_verification.json',report)
    save(source/'native_observer_verification.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__': main()
