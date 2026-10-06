"""Verify actual dashboard demos and export a bounded evidence receipt."""
import hashlib
import json
from pathlib import Path
from urllib.request import urlopen
from incidentlab.native_observer import status

ROOT=Path(__file__).resolve().parents[1]


def main():
    demos=[]
    for directory in sorted((ROOT/'artifacts/live_runtime').glob('demo-*')):
        if not (directory/'completion.json').exists():continue
        completion=json.loads((directory/'completion.json').read_text())
        metadata=json.loads((directory/'runtime.json').read_text())
        schedule=json.loads((directory/'schedule.json').read_text())
        history=status(stream=directory.name)['predictions']
        events=[json.loads(line) for path in directory.glob('*.jsonl') for line in path.read_text().splitlines() if line]
        delay=[e for e in events if e['service']=='inventory' and e['duration_ms']>=250
               and schedule['onset'] is not None and schedule['onset']<=e['start']<schedule['recovery']]
        assert completion['cleanup_complete']
        assert json.loads((directory/'control.json').read_text())=={}
        assert len(history)==completion['windows']
        if metadata['scenario']=='delay' and completion['status']=='complete':
            assert delay,'No measured inventory delay impact'
            assert any(p['incident']['active'] for p in history),'Operational incident never opened'
            assert not history[0]['incident']['active'],'Incident did not close after recovery'
        demos.append(dict(stream=directory.name,scenario=metadata['scenario'],**{k:v for k,v in completion.items() if k!='stream'},
            measured_spans=len(events),measured_inventory_delay_spans=len(delay),
            operational_warning_windows=sum(p['operational_alert'] for p in history),
            ml_warning_windows=sum(p['ml_alert'] for p in history),
            opened_incidents=history[0]['incident']['opened_incidents'] if history else 0,
            checkpoint_sha256=metadata['checkpoint_sha256']))
    http={}
    for path in ('/','/research','/live','/api/workspace','/api/workspace/cluster/test_delay_inventory',
                 '/api/workspace/figures/report-figures.zip','/api/workspace/figures/research-gru-confusion.png'):
        with urlopen('http://127.0.0.1:8768'+path,timeout=10) as response:
            data=response.read();http[path]=dict(status=response.status,bytes=len(data))
            if path.endswith('.zip'):
                assert hashlib.sha256(data).hexdigest()==hashlib.sha256((ROOT/'artifacts/report_figures/report-figures.zip').read_bytes()).hexdigest()
    receipt=dict(status='passed',demos=demos,http=http,training_performed=False,
        boundary='Short controlled localhost runs verify user workflow; no industrial reliability estimate.')
    (ROOT/'artifacts/laptop_validation/guided-dashboard-verification.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt,indent=2))


if __name__=='__main__':main()
