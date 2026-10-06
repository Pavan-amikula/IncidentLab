"""CPU experiment against the dedicated kind testbed; never a production context."""
import argparse
import hashlib
import json
import shutil
import socket
import subprocess
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import numpy as np

from .kubernetes_telemetry import CONTEXT, NAMESPACE, OWNER, Kubectl, PodCapture, PodEventStore
from .live_monitor import SERVICES, aggregate, fit, score
from .native_experiment import evaluate, save

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/kubernetes'


class FaultControl:
    def __init__(self,cli,target,kind):
        self.cli,self.target,self.kind=cli,target,kind
        self.active=False

    def verify(self):
        self.cli.verify_scope()
        value=json.loads(self.cli.run('get','deployment/'+self.target,'-o','json'))
        if value['metadata'].get('labels',{}).get('app.kubernetes.io/part-of')!=OWNER:
            raise ValueError('Deployment is not owned by the testbed')
        if value['spec']['replicas']!=1:raise ValueError('Experiment requires one healthy replica per service')

    def apply(self):
        self.verify()
        # Set before invocation so a partially completed command still triggers restoration.
        self.active=True
        if self.kind=='unavailable':
            self.cli.run('scale','deployment/'+self.target,'--replicas=0')
        else:self.write({self.target:self.kind})

    def write(self,value):
        script="import pathlib; p=pathlib.Path('/telemetry/control.json'); t=p.with_suffix('.tmp'); t.write_text("+repr(json.dumps(value))+ "); t.replace(p)"
        self.cli.run('exec','deployment/'+self.target,'--','python','-c',script)

    def restore(self):
        if not self.active:return
        self.cli.verify_scope()
        value=json.loads(self.cli.run('get','deployment/'+self.target,'-o','json'))
        if value['metadata'].get('labels',{}).get('app.kubernetes.io/part-of')!=OWNER:
            raise ValueError('Ownership changed; refusing recovery against another deployment')
        if self.kind=='unavailable':
            self.cli.run('scale','deployment/'+self.target,'--replicas=1')
            self.cli.run('rollout','status','deployment/'+self.target,'--timeout=20s')
        else:self.write({})
        self.active=False


class Forward:
    def __init__(self,directory):
        self.child=None
        self.handle=(directory/'port-forward.log').open('ab')
        self.next_attempt=0

    def ensure(self):
        if self.child and self.child.poll() is None:return
        if time.monotonic()<self.next_attempt:return
        self.next_attempt=time.monotonic()+2
        self.child=subprocess.Popen(['kubectl','--context',CONTEXT,'-n',NAMESPACE,
            'port-forward','--address=127.0.0.1','--pod-running-timeout=3s',
            'service/frontend','8891:8891'],stdout=self.handle,stderr=self.handle,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))

    def close(self):
        if self.child and self.child.poll() is None:
            self.child.terminate()
            try:self.child.wait(timeout=5)
            except subprocess.TimeoutExpired:self.child.kill();self.child.wait(timeout=5)
        self.handle.close()


def request_once():
    trace=uuid.uuid4().hex;started=time.time()
    try:
        with urlopen(Request('http://127.0.0.1:8891/request',headers={'X-Trace-ID':trace}),timeout=2) as response:
            response.read();status=response.status
    except HTTPError as exc:status=exc.code;exc.close()
    except OSError:status=0
    return dict(trace_id=trace,start=started,end=time.time(),status=status)


def collect(run_dir,phase,seconds,kind,bundle=None,target=None):
    directory=run_dir/phase;directory.mkdir()
    cli=Kubectl();cli.verify_scope()
    control=FaultControl(cli,target,kind) if target else None
    store=PodEventStore(directory/'capture.sqlite3')
    forward=Forward(directory)
    rows,predictions,commands=[],[],[]
    onset=recovery=None;dropped=0;recovered=False
    started=None
    try:
        # Require a healthy reachable frontend before timing a phase.
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            forward.ensure()
            try:
                with urlopen('http://127.0.0.1:8891/health',timeout=.3) as response:
                    if json.loads(response.read()).get('service')=='frontend':break
            except (OSError,ValueError):pass
            time.sleep(.2)
        else:raise RuntimeError('Testbed frontend did not become reachable on localhost:8891')
        started=time.time();began=time.monotonic();next_request=began;next_poll=began
        capture=PodCapture(store,started);closed=0;pending=set()
        with ThreadPoolExecutor(max_workers=8) as pool, (directory/'client_requests.jsonl').open('w',encoding='utf-8') as client_log:
            # Three seconds of collection grace; arrival cutoff saved with each prediction.
            while time.monotonic()-began<seconds+3 or closed<seconds//3:
                now=time.monotonic();elapsed=now-began;forward.ensure()
                if control and elapsed>=seconds*.3 and onset is None:
                    control.apply();onset=time.time()
                    commands.append(dict(action=kind,target=target,command_completed=onset))
                    save(directory/'control_commands.json',commands)
                if control and onset is not None and elapsed>=seconds*.7 and not recovered:
                    control.restore();recovery=time.time();recovered=True
                    commands.append(dict(action='recover',target=target,command_completed=recovery))
                    save(directory/'control_commands.json',commands)
                done={future for future in pending if future.done()}
                for future in done:client_log.write(json.dumps(future.result())+'\n')
                pending-=done
                rate=(1,2,3,6)[min(3,int(elapsed/seconds*4))] if kind=='healthy_loads' else (
                    6 if kind=='surge' and seconds*.3<=elapsed<seconds*.7 else 3)
                if elapsed<seconds and now>=next_request:
                    if len(pending)<8:pending.add(pool.submit(request_once))
                    else:dropped+=1
                    next_request=now+1/rate
                if now>=next_poll:
                    capture.poll(time.time());decision=time.time();next_poll=time.monotonic()+3
                    while closed<seconds//3 and started+(closed+1)*3+3<=decision:
                        start=started+closed*3;end=start+3
                        batch=aggregate(store.window(start,end,as_of=decision),start,end);rows.extend(batch);closed+=1
                        if bundle:
                            result=score(batch,bundle);result['decision_at']=decision
                            result['window_close_to_decision_ms']=(decision-end)*1000
                            predictions.append(result)
                        save(OUT/'progress.json',dict(run_id=run_dir.name,phase=phase,status='running',
                            windows=closed,phase_seconds=seconds,elapsed_seconds=round(elapsed,1)))
                time.sleep(.01)
            for future in pending:client_log.write(json.dumps(future.result())+'\n')
        schedule=dict(kind=kind,target=target,phase=phase,onset=onset,recovery=recovery,
            dropped=dropped,commands=commands,label_semantics='Control command completion proxy; actual workload onset requires trace review')
        save(directory/'windows.json',rows);save(directory/'predictions.json',predictions)
        with (directory/'predictions.jsonl').open('w',encoding='utf-8') as output:
            for result in predictions:output.write(json.dumps(result)+'\n')
        save(directory/'schedule.json',schedule);save(directory/'capture_report.json',store.export(directory))
        return rows,predictions,schedule
    finally:
        try:
            if control:control.restore()
            save(directory/'cleanup.json',dict(status='restored',owned_fault_active=False))
        except BaseException as exc:
            save(directory/'cleanup.json',dict(status='recovery_failed',error=str(exc),manual_recovery_required=True))
            raise
        finally:forward.close()


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--quick',action='store_true')
    args=parser.parse_args()
    with socket.socket() as probe:
        try:probe.bind(('127.0.0.1',8891))
        except OSError:raise RuntimeError('Port 8891 is already occupied; stop the other local testbed before cluster experiments')
    cli=Kubectl();cli.verify_scope()
    for service in SERVICES:
        FaultControl(cli,service,'delay').verify()
        cli.run('rollout','status','deployment/'+service,'--timeout=20s')
    run_id=time.strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:6]
    run_dir=OUT/run_id;run_dir.mkdir(parents=True)
    snapshots=run_dir/'source_snapshot';snapshots.mkdir()
    names=('kubernetes_experiment.py','kubernetes_telemetry.py','native_service.py','live_monitor.py','raw_telemetry.py')
    for name in names:shutil.copyfile(ROOT/'incidentlab'/name,snapshots/name)
    train_seconds=36 if args.quick else 180;fault_seconds=36 if args.quick else 60
    plan=[('healthy',None,'test_healthy'),('surge',None,'test_surge')]
    for kind in ('delay','error','unavailable'):
        for target in (('inventory',) if args.quick else SERVICES):plan.append((kind,target,'test_'+kind+'_'+target))
    save(run_dir/'source.json',dict(context=CONTEXT,namespace=NAMESPACE,quick=args.quick,
        code_sha256={n:hashlib.sha256((snapshots/n).read_bytes()).hexdigest() for n in names},
        intended_purpose='Fresh low-resource kind CPU calibration and controlled fault evaluation; not production'))
    try:
        print('Collecting fresh Kubernetes healthy training and calibration; no deep-model training',flush=True)
        training,_,_=collect(run_dir,'healthy_train',train_seconds,'healthy_loads')
        validation,_,_=collect(run_dir,'healthy_validation',train_seconds,'healthy_loads')
        checkpoint=run_dir/'native_monitor.joblib';bundle=fit(training,validation,checkpoint)
        frozen=hashlib.sha256(checkpoint.read_bytes()).hexdigest();results=[];latencies=[]
        for kind,target,phase in plan:
            print('Held-out phase: '+phase,flush=True)
            _,predictions,schedule=collect(run_dir,phase,train_seconds if target is None else fault_seconds,kind,bundle,target)
            results.append(evaluate(predictions,schedule));latencies.extend(p['inference_ms'] for p in predictions)
            if hashlib.sha256(checkpoint.read_bytes()).hexdigest()!=frozen:raise RuntimeError('Frozen checkpoint changed')
        report=dict(status='complete',run_id=run_id,quick=args.quick,checkpoint_sha256=frozen,
            device='cpu',model='Fresh Kubernetes healthy-fitted IsolationForest plus separate operational envelopes',
            training_windows=len(training)//3,calibration_windows=len(validation)//3,trials=results,
            inference_p95_ms=float(np.quantile(latencies,.95)),
            limitations=['Control timestamps are command-completion proxies; manually review trace impact before research claims',
                'Known controlled application faults only; no unseen infrastructure or industrial validation',
                'Polling can lose logs on pod deletion/rotation; capture lifecycle snapshots must be reviewed',
                'Transport delay or missing logs can resemble outages; service hypotheses are not causal proof',
                'Short healthy periods do not establish stable operational false-alarm rates'])
        save(run_dir/'report.json',report);save(OUT/'latest_report.json',report)
        save(OUT/'progress.json',dict(status='complete',run_id=run_id))
        print(json.dumps(report,indent=2),flush=True)
    except BaseException as exc:
        save(run_dir/'failure.json',dict(status='failed',error=type(exc).__name__+': '+str(exc)))
        save(OUT/'progress.json',dict(status='failed',run_id=run_id,error=str(exc)))
        raise


if __name__=='__main__':main()
