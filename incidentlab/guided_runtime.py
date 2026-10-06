"""One-minute, CPU-only demonstration with frozen inference and explicit cleanup."""
import argparse
import hashlib
import math
import shutil
import time
from concurrent.futures import ThreadPoolExecutor

from .native_experiment import ROOT, Testbed, request_once, save
from .native_observer import NativeObserver, native_bundle


def run(directory, scenario):
    bundle, digest = native_bundle('20261005T202755-0e2c27')
    directory.mkdir(parents=True, exist_ok=True)
    stream = directory.name
    save(directory/'control.json', {})
    snapshot = directory/'source_snapshot'
    snapshot.mkdir()
    hashes = {}
    for name in ('guided_runtime.py', 'native_service.py', 'native_experiment.py',
                 'live_monitor.py', 'raw_telemetry.py', 'native_observer.py'):
        source = ROOT/'incidentlab'/name
        shutil.copyfile(source, snapshot/name)
        hashes[name] = hashlib.sha256(source.read_bytes()).hexdigest()
    save(directory/'runtime.json', dict(stream=stream, checkpoint_sha256=digest,
        model_run='20261005T202755-0e2c27', scenario=scenario, source_sha256=hashes,
        boundary='Controlled localhost demo; frozen inference, no training. Not cluster telemetry.'))
    bed = Testbed(directory)
    observer = NativeObserver()
    completed = dropped = 0
    pending = set()
    began = time.time()
    schedule = dict(kind=scenario, target='inventory' if scenario=='delay' else None,
                    onset=None, recovery=None, label_semantics='Control write completion proxy; inspect traces')
    outcome = 'complete'
    error = None
    try:
        bed.start()
        start = math.ceil(time.time()/3)*3
        began = start
        due = time.monotonic()
        with ThreadPoolExecutor(max_workers=12) as pool:
            while completed < 20:
                if (directory/'stop').exists():
                    outcome = 'stopped'
                    break
                elapsed = time.time()-began
                if scenario=='delay' and elapsed>=20 and schedule['onset'] is None:
                    save(directory/'control.json', {'inventory': 'delay'})
                    schedule['onset'] = time.time()
                    save(directory/'schedule.json', schedule)
                if scenario=='delay' and elapsed>=40 and schedule['recovery'] is None:
                    save(directory/'control.json', {})
                    schedule['recovery'] = time.time()
                    save(directory/'schedule.json', schedule)
                pending = {f for f in pending if not f.done()}
                if time.time() >= start+3:
                    prediction = observer.observe(stream, directory, start, start+3, bundle, digest)
                    completed += 1
                    save(directory/'status.json', dict(status='running', stream=stream, windows=completed,
                        scenario=scenario, elapsed_seconds=max(0, elapsed), dropped_workload_requests=dropped,
                        last_prediction=prediction))
                    start += 3
                if time.monotonic()>=due and completed<20:
                    if len(pending)<12:
                        pending.add(pool.submit(request_once))
                    else:
                        dropped += 1
                    due = time.monotonic()+1/6
                time.sleep(.01)
    except BaseException as exc:
        outcome, error = 'failed', str(exc)[:300]
        raise
    finally:
        save(directory/'control.json', {})
        if schedule['onset'] is not None and schedule['recovery'] is None:
            schedule['recovery'] = time.time()
        save(directory/'schedule.json', schedule)
        bed.close()
        save(directory/'completion.json', dict(status=outcome, stream=stream, windows=completed,
            dropped_workload_requests=dropped, error=error, ended_epoch=time.time(), cleanup_complete=True))


if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--stream', required=True)
    parser.add_argument('--scenario', choices=('healthy', 'delay'), required=True)
    args = parser.parse_args()
    import re
    if not re.fullmatch(r'demo-[0-9T]+-[a-f0-9]{8}', args.stream):
        parser.error('Invalid demo identifier')
    run(ROOT/'artifacts/live_runtime'/args.stream, args.scenario)
