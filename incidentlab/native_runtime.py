"""Bounded running HTTP application and durable frozen-model observation."""
import argparse
import hashlib
import json
import math
import shutil
import time
import uuid
from concurrent.futures import ThreadPoolExecutor

from .native_experiment import ROOT, OUT, Testbed, request_once, save
from .native_observer import NativeObserver, native_bundle


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-id',required=True,help='Completed healthy-calibrated native model run')
    parser.add_argument('--minutes',type=int,default=10)
    args=parser.parse_args()
    if not 1<=args.minutes<=60:
        parser.error('Use 1–60 minutes; observation and storage are deliberately bounded')
    bundle,digest=native_bundle(args.run_id)
    stream='running-app-'+time.strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:6]
    directory=ROOT/'artifacts/live_runtime'/stream
    save(directory/'control.json',{})
    snapshot=directory/'source_snapshot';snapshot.mkdir()
    hashes={}
    for name in ('native_runtime.py','native_service.py','native_experiment.py','live_monitor.py','raw_telemetry.py','native_observer.py'):
        source=ROOT/'incidentlab'/name
        shutil.copyfile(source,snapshot/name)
        hashes[name]=hashlib.sha256(source.read_bytes()).hexdigest()
    metadata=dict(stream=stream,model_run=args.run_id,checkpoint_sha256=digest,
        source_directory=str(directory),source_sha256=hashes,minutes=args.minutes,
        workload_requests_per_second=6,automatic_fault_injection=False,
        purpose='New real localhost HTTP requests; frozen native checkpoint and durable observation, not a company deployment')
    save(directory/'runtime.json',metadata)
    print(json.dumps(metadata),flush=True)
    bed=Testbed(directory);observer=NativeObserver()
    completed,dropped,pending=0,0,set()
    try:
        bed.start()
        start=math.ceil(time.time()/3)*3
        next_request=time.monotonic()
        with ThreadPoolExecutor(max_workers=24) as pool:
            while completed<args.minutes*20:
                now=time.monotonic()
                pending={future for future in pending if not future.done()}
                if time.time()>=start+3:
                    value=observer.observe(stream,directory,start,start+3,bundle,digest)
                    completed+=1
                    save(directory/'status.json',dict(status='running',stream=stream,
                        windows=completed,dropped_workload_requests=dropped,last_prediction=value))
                    print(json.dumps(dict(stream=stream,windows=completed,end=value['end'],
                        operational_alert=value['operational_alert'],ml_alert=value['ml_alert'],
                        incident=value['incident'],collector=value['collector_audit'])),flush=True)
                    start+=3
                    if completed==args.minutes*20:break
                if now>=next_request:
                    if len(pending)<24:pending.add(pool.submit(request_once))
                    else:dropped+=1
                    next_request=now+1/6
                time.sleep(.005)
        save(directory/'completion.json',dict(status='complete',windows=completed,
            dropped_workload_requests=dropped,ended_epoch=time.time()))
    except BaseException as exc:
        save(directory/'completion.json',dict(status='interrupted' if isinstance(exc,KeyboardInterrupt) else 'failed',
            windows=completed,error=type(exc).__name__+': '+str(exc)[:250],ended_epoch=time.time()))
        raise
    finally:
        bed.close()


if __name__=='__main__':main()
