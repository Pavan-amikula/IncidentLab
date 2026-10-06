"""Check completed-run artifacts without changing source data or decisions."""
import argparse
import hashlib
import json
import re

from incidentlab.native_experiment import OUT, save


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(run_id):
    if not re.fullmatch(r'\d{8}T\d{6}-[0-9a-f]{6}',run_id):
        raise ValueError('Invalid run ID')
    directory=OUT/run_id
    report=json.loads((directory/'report.json').read_text())
    source=json.loads((directory/'source.json').read_text())
    assert report['status']=='complete' and report['run_id']==run_id
    assert digest(directory/'native_monitor.joblib')==report['checkpoint_sha256']
    for name,expected in source['code_sha256'].items():
        assert digest(directory/'source_snapshot'/name)==expected, name
    phases=['healthy_train','healthy_validation']+[t['phase'] for t in report['trials']]
    receipts=[]
    previous_end=None
    for phase in phases:
        path=directory/phase
        rows=json.loads((path/'windows.json').read_text())
        schedule=json.loads((path/'schedule.json').read_text())
        duration=schedule['ended']-schedule['started']
        expected=round(duration/source['window_seconds'])
        assert len(rows)==expected*3, phase
        assert previous_end is None or schedule['started']>=previous_end, phase
        previous_end=schedule['ended']
        for index in range(expected):
            batch=rows[index*3:index*3+3]
            assert {r['service'] for r in batch}=={'frontend','checkout','inventory'}, phase
            start=schedule['started']+index*source['window_seconds']
            assert all(abs(r['start']-start)<.001 and abs(r['end']-start-source['window_seconds'])<.001 for r in batch), phase
        predictions=json.loads((path/'predictions.json').read_text())
        if phase.startswith('test_'):
            assert len(predictions)==expected, phase
            for prediction in predictions:
                assert not {'onset','recovery','target','kind','label','fault'}.intersection(prediction), phase
                assert len(prediction['candidates'])==3, phase
        else:
            assert predictions==[], phase
            assert schedule['onset'] is None and schedule['target'] is None, phase
        journal=path/'predictions.jsonl'
        journal_count=len(journal.read_text().splitlines()) if journal.exists() else 0
        receipts.append(dict(phase=phase,windows=expected,predictions=len(predictions),
            journal_predictions=journal_count,
            journal_note='Canonical predictions.json retains final window; the archived runner omitted its last journal append' if predictions and journal_count!=len(predictions) else None,
            collector=json.loads((path/'collector_audit.json').read_text()),
            raw_sha256={name:digest(path/f'{name}.jsonl') for name in ('frontend','checkout','inventory')},
            windows_sha256=digest(path/'windows.json'),predictions_sha256=digest(path/'predictions.json')))
    result=dict(status='passed',run_id=run_id,phase_count=len(phases),
        windows=sum(r['windows'] for r in receipts),test_windows=sum(r['predictions'] for r in receipts),
        source_snapshots_verified=True,checkpoint_sha256=report['checkpoint_sha256'],
        chronological_phase_order=True,receipts=receipts,
        scope='Artifact integrity and top-level input boundaries, not a proof of algorithm correctness or production reliability')
    save(directory/'integrity_report.json',result)
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True)
    result=audit(parser.parse_args().run_id)
    print(json.dumps({key:value for key,value in result.items() if key!='receipts'},indent=2))
