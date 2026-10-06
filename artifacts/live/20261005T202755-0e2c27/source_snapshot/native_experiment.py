"""Collect fresh isolated HTTP runs, freeze a model, then evaluate whole unseen trials.

Starts only child processes created here. No admin, Docker, credential or external
service is required. These trials verify a live development pipeline, not Kubernetes.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
import uuid
import shutil
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import urlopen

import numpy as np

from .live_monitor import SERVICES, aggregate, fit, read_events, score
from .raw_telemetry import EventCollector

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'artifacts' / 'live'
PORTS = dict(frontend=8891, checkout=8892, inventory=8893)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, indent=2), encoding='utf-8')
    os.replace(temporary, path)


class Testbed:
    def __init__(self, directory):
        self.directory, self.children, self.handles = directory, {}, []

    def start_service(self, service):
        instance_id = uuid.uuid4().hex
        downstream = {'frontend': 'checkout', 'checkout': 'inventory'}.get(service)
        args = [sys.executable, '-m', 'incidentlab.native_service', '--service', service,
                '--port', str(PORTS[service]), '--directory', str(self.directory), '--instance-id', instance_id]
        if downstream:
            args.extend(['--downstream', f'{downstream}:{PORTS[downstream]}'])
        handle = (self.directory / f'{service}.stderr').open('ab')
        self.handles.append(handle)
        child = subprocess.Popen(args, cwd=ROOT, stdout=handle, stderr=handle,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        self.children[service] = child
        deadline = time.monotonic()+10
        while time.monotonic() < deadline:
            if child.poll() is not None:
                raise RuntimeError(f'{service} exited; inspect its stderr (ports may already be occupied)')
            try:
                with urlopen(f'http://127.0.0.1:{PORTS[service]}/health', timeout=.3) as response:
                    identity = json.loads(response.read())
                    if response.status == 200 and identity.get('service') == service and identity.get('instance_id') == instance_id:
                        return
            except (OSError, ValueError):
                time.sleep(.1)
        raise RuntimeError(f'{service} did not become ready')

    def start(self):
        self.directory.mkdir(parents=True, exist_ok=True)
        for service in reversed(SERVICES):
            self.start_service(service)

    def stop_service(self, service):
        child = self.children.pop(service, None)
        if child:
            child.terminate()
            try:
                child.wait(timeout=5)
            except subprocess.TimeoutExpired:
                child.kill(); child.wait(timeout=5)

    def close(self):
        for service in list(self.children):
            self.stop_service(service)
        for handle in self.handles:
            handle.close()


def request_once():
    try:
        with urlopen(f'http://127.0.0.1:{PORTS["frontend"]}/request', timeout=2) as response:
            response.read()
    except OSError:
        pass


def collect(run_dir, phase, seconds, window, kind, bundle=None, target='inventory'):
    directory = run_dir / phase
    bed = Testbed(directory)
    collector = EventCollector(directory)
    rows, predictions, schedule = [], [], []
    progress_path = OUT / 'progress.json'
    control = directory / 'control.json'
    save(control, {})
    active, recovered = False, False
    onset = recovery = None
    try:
        bed.start()
        started = time.time()
        monotonic_start = time.monotonic()
        request_due, window_due = monotonic_start, monotonic_start+window
        # Limit in-flight tasks; benign high load must not create an unbounded executor queue.
        pending = set()
        dropped = 0
        with ThreadPoolExecutor(max_workers=24) as pool:
            while time.monotonic()-monotonic_start < seconds:
                now = time.monotonic()
                elapsed = now-monotonic_start
                if kind in ('delay', 'error', 'unavailable') and elapsed >= seconds*.3 and not active:
                    if kind == 'unavailable':
                        bed.stop_service(target)
                    else:
                        save(control, {target: kind})
                    onset = time.time()
                    schedule.append(dict(timestamp=onset, action=kind, target=target))
                    active = True
                if active and not recovered and elapsed >= seconds*.7:
                    if kind == 'unavailable':
                        bed.start_service(target)
                    else:
                        save(control, {})
                    recovery = time.time()
                    schedule.append(dict(timestamp=recovery, action='recover', target=target))
                    recovered = True
                pending = {future for future in pending if not future.done()}
                if kind == 'healthy_loads':
                    rate = (3, 6, 12, 24)[min(3, int(elapsed/seconds*4))]
                else:
                    rate = 24 if kind == 'surge' and seconds*.3 <= elapsed < seconds*.7 else 6
                if now >= request_due:
                    if len(pending) < 24:
                        pending.add(pool.submit(request_once))
                    else:
                        dropped += 1
                    request_due = now+1/rate
                if now >= window_due:
                    end = started + round((window_due-monotonic_start)/window)*window
                    batch = aggregate(collector.read_window(end-window, end), end-window, end)
                    rows.extend(batch)
                    if bundle:
                        result = score(batch, bundle)
                        result['decision_at'] = time.time()
                        result['window_close_to_decision_ms'] = (result['decision_at']-end)*1000
                        predictions.append(result)
                        with (directory/'predictions.jsonl').open('a', encoding='utf-8') as output:
                            output.write(json.dumps(result)+'\n')
                    save(progress_path, dict(run_id=run_dir.name, stage=phase, status='running',
                        elapsed_seconds=round(elapsed, 1), phase_seconds=seconds,
                        windows=len(rows)//len(SERVICES), latest_prediction=predictions[-1] if predictions else None))
                    window_due += window
                time.sleep(.005)
        final = started + seconds
        # Include the final complete observation window after in-flight requests settle.
        if not rows or rows[-1]['end'] < final:
            batch = aggregate(collector.read_window(final-window, final), final-window, final)
            rows.extend(batch)
            if bundle:
                result = score(batch, bundle)
                result['decision_at'] = time.time()
                result['window_close_to_decision_ms'] = (result['decision_at']-final)*1000
                predictions.append(result)
        save(directory/'windows.json', rows)
        save(directory/'collector_audit.json', collector.audit())
        save(directory/'schedule.json', dict(kind=kind, target=target if onset else None,
            started=started, ended=final, onset=onset, recovery=recovery, actions=schedule,
            dropped_workload_requests=dropped))
        save(directory/'predictions.json', predictions)
        return rows, predictions, dict(kind=kind, target=target if onset else None, phase=phase,
            onset=onset, recovery=recovery,
            started=started, ended=final, dropped=dropped)
    finally:
        bed.close()


def evaluate(predictions, schedule):
    onset, recovery = schedule['onset'], schedule['recovery']
    # Windows crossing a control boundary are excluded, rather than assigned a misleading label.
    healthy, faulty, boundary = [], [], []
    for prediction in predictions:
        if onset is None or prediction['end'] <= onset or prediction['start'] >= recovery:
            healthy.append(prediction)
        elif prediction['start'] >= onset and prediction['end'] <= recovery:
            faulty.append(prediction)
        else:
            boundary.append(prediction)
    result = dict(kind=schedule['kind'], target=schedule.get('target'), phase=schedule.get('phase'),
                  healthy_windows=len(healthy), active_fault_windows=len(faulty),
                  boundary_windows_excluded=len(boundary), dropped_workload_requests=schedule['dropped'])
    for signal in ('ml_alert', 'operational_alert'):
        alerts = [p for p in faulty if p[signal]]
        minutes = sum((p['end']-p['start']) for p in healthy)/3600
        result[signal] = dict(fault_window_recall=len(alerts)/len(faulty) if faulty else None,
            incident_detected=bool(alerts) if faulty else None,
            detection_delay_seconds=alerts[0]['end']-onset if alerts else None,
            false_alert_windows_per_healthy_hour=sum(p[signal] for p in healthy)/minutes if minutes else None,
            first_alert_service=alerts[0]['candidates'][0]['service'] if alerts and alerts[0].get('candidates') else None,
            first_alert_service_matches_injected_target=(alerts[0]['candidates'][0]['service']==schedule.get('target'))
                if alerts and alerts[0].get('candidates') else None)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=int, default=60)
    parser.add_argument('--window', type=int, default=3)
    parser.add_argument('--healthy-loads', action='store_true',
                        help='Fit/calibrate on distinct healthy runs spanning 3, 6, 12 and 24 requests/s')
    parser.add_argument('--fault-targets', nargs='+', choices=SERVICES, default=['inventory'])
    parser.add_argument('--healthy-seconds', type=int, help='Duration of each independent train/calibration run')
    parser.add_argument('--control-seconds', type=int, help='Duration of each held-out healthy/surge control')
    parser.add_argument('--repetitions', type=int, default=1, choices=range(1,6))
    args = parser.parse_args()
    healthy_seconds = args.healthy_seconds or args.seconds
    control_seconds = args.control_seconds or args.seconds
    if args.window <= 0 or any(duration < args.window*12 or duration % args.window
                              for duration in (args.seconds, healthy_seconds, control_seconds)):
        parser.error('Duration must be a multiple of the window and contain at least twelve windows')
    if len(set(args.fault_targets)) != len(args.fault_targets):
        parser.error('Fault targets must be distinct')
    run_id = time.strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:6]
    run_dir = OUT / run_id
    run_dir.mkdir(parents=True)
    source_files = ('native_service.py', 'live_monitor.py', 'native_experiment.py', 'raw_telemetry.py')
    snapshot = run_dir/'source_snapshot'
    snapshot.mkdir()
    for name in source_files:
        shutil.copyfile(ROOT/'incidentlab'/name, snapshot/name)
    run_dir.joinpath('source.json').write_text(json.dumps({
        'code_sha256': {name: hashlib.sha256((ROOT/'incidentlab'/name).read_bytes()).hexdigest()
                        for name in source_files},
        'window_seconds': args.window, 'run_seconds': args.seconds, 'healthy_loads': args.healthy_loads,
        'healthy_seconds': healthy_seconds, 'control_seconds': control_seconds,
        'repetitions': args.repetitions,
        'fault_targets': args.fault_targets,
        'purpose': 'Actual local HTTP development trials, not Kubernetes or production evidence'}, indent=2))
    try:
        print(f'Fresh live run: {run_dir}', flush=True)
        print('Collecting independent healthy training run', flush=True)
        healthy_kind = 'healthy_loads' if args.healthy_loads else 'healthy'
        training, _, _ = collect(run_dir, 'healthy_train', healthy_seconds, args.window, healthy_kind)
        print('Collecting separate healthy calibration run', flush=True)
        validation, _, _ = collect(run_dir, 'healthy_validation', healthy_seconds, args.window, healthy_kind)
        checkpoint = run_dir/'native_monitor.joblib'
        bundle = fit(training, validation, checkpoint)
        frozen = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        results = []
        plan = [('healthy', None, 'test_healthy'), ('surge', None, 'test_surge')]
        for kind in ('delay', 'error', 'unavailable'):
            for target in args.fault_targets:
                for repeat in range(1, args.repetitions+1):
                    phase = 'test_'+kind+('_'+target if len(args.fault_targets)>1 else '')
                    if args.repetitions > 1:
                        phase += f'_r{repeat}'
                    plan.append((kind, target, phase))
        for kind, target, phase in plan:
            print(f'Frozen-model trial: {phase}', flush=True)
            duration = control_seconds if target is None else args.seconds
            _, predictions, schedule = collect(run_dir, phase, duration, args.window, kind,
                bundle, target=target or 'inventory')
            results.append(evaluate(predictions, schedule))
            if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != frozen:
                raise RuntimeError('Checkpoint changed during held-out evaluation')
        latencies = [p['inference_ms'] for _, _, phase in plan
                     for p in json.loads((run_dir/phase/'predictions.json').read_text())]
        target_counts = {target:sum(r['target']==target for r in results) for target in args.fault_targets}
        fault_count = sum(target_counts.values())
        report = dict(run_id=run_id, status='complete', model='healthy-fitted per-service IsolationForest',
            feature_schema='incidentlab-http-v1', features=list(bundle['features']),
            repetitions_per_fault=args.repetitions, healthy_run_seconds=healthy_seconds,
            control_run_seconds=control_seconds, fault_run_seconds=args.seconds,
            checkpoint_sha256=frozen, split='distinct chronological service-process trials',
            training_windows=len(training)//3, validation_windows=len(validation)//3,
            trials=results, inference_p50_ms=float(np.quantile(latencies, .5)),
            fault_target_distribution=target_counts,
            service_prior_only_localization=max(target_counts.values())/fault_count,
            inference_p95_ms=float(np.quantile(latencies, .95)),
            limitations=['Short healthy periods give unstable false-alert rates',
                'One controlled application; repeated known faults do not establish cross-system or unseen-fault performance',
                'Requests and faults are controlled; infrastructure/CPU/memory/Kubernetes faults not evaluated',
                'Separate HTTP model; pretrained RCAEval GRU was not silently reused',
                'Trace-supported service hypotheses are not causal proof'])
        save(run_dir/'report.json', report)
        save(OUT/'latest_report.json', report)
        last = json.loads((run_dir/plan[-1][2]/'predictions.json').read_text())[-1]
        save(OUT/'progress.json', dict(run_id=run_id, status='complete', stage='complete',
            windows=(len(training)+len(validation))//3+sum(r['healthy_windows']+r['active_fault_windows']+r['boundary_windows_excluded'] for r in results),
            latest_prediction=last))
        print(json.dumps(report, indent=2), flush=True)
    except BaseException as exc:
        save(OUT/'progress.json', dict(run_id=run_id, status='failed', error=str(exc)))
        raise


if __name__ == '__main__':
    main()
