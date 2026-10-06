"""Bounded owned inventory container restart and previous-log capture verification.

No fitting or fault-metric changes. Raw evidence goes to a separate infrastructure check.
"""
import json
import socket
import subprocess
import re
import time
import uuid
from pathlib import Path
from urllib.request import urlopen

from incidentlab.kubernetes_experiment import Forward,request_once,FaultControl
from incidentlab.kubernetes_telemetry import Kubectl,PodEventStore,PodCapture,OWNER
from incidentlab.native_experiment import save

ROOT=Path(__file__).resolve().parents[1]


def main():
    cli=Kubectl();cli.verify_scope()
    FaultControl(cli,'inventory','delay').verify()
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',8891))
    run='infrastructure-'+time.strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:6]
    directory=ROOT/'artifacts/kubernetes'/run;directory.mkdir()
    began=time.time();store=PodEventStore(directory/'capture.sqlite3');capture=PodCapture(store,began)
    forward=Forward(directory);clients=[]
    result=dict(run_id=run,status='running',kind='same-pod-container-restart',target='inventory',training=False)
    save(directory/'report.json',result)
    try:
        deadline=time.monotonic()+30
        while time.monotonic()<deadline:
            forward.ensure()
            try:
                with urlopen('http://127.0.0.1:8891/health',timeout=1) as response:
                    if response.status==200:break
            except OSError:time.sleep(.2)
        else:raise RuntimeError('Frontend not reachable')
        original=json.loads(cli.run('get','pods','-l','app.kubernetes.io/name=inventory','-o','json'))['items']
        assert len(original)==1
        pod=original[0]
        assert pod['metadata']['labels'].get('app.kubernetes.io/part-of')==OWNER
        name=pod['metadata']['name'];uid=pod['metadata']['uid']
        previous_count=pod['status']['containerStatuses'][0]['restartCount']
        for _ in range(12):clients.append(request_once())
        capture.poll(time.time())
        # Tail requests complete after the last poll; previous logs must recover them.
        tail=[request_once() for _ in range(8)];clients.extend(tail)
        assert all(c['status']==200 for c in tail)
        save(directory/'before-restart-pod.json',pod)
        result.update(pod_uid=uid,previous_restart_count=previous_count,restart_command_started=time.time())
        # Namespace PID 1 cannot be reliably killed from an exec child. Stop only
        # the inspected owned container through its parent runtime instead.
        container_id=pod['status']['containerStatuses'][0]['containerID']
        assert re.fullmatch(r'containerd://[a-f0-9]{64}',container_id)
        assert pod['spec']['nodeName']=='incidentlab-control-plane'
        stopped=subprocess.run(['docker','exec','incidentlab-control-plane','crictl',
            'stop','--timeout','1',container_id.split('://')[1]],capture_output=True,timeout=30,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        result['runtime_stop_exit_code']=stopped.returncode
        if stopped.returncode:raise RuntimeError('Owned runtime container stop failed')
        deadline=time.monotonic()+90
        while time.monotonic()<deadline:
            current=json.loads(cli.run('get','pod',name,'-o','json'))
            assert current['metadata']['uid']==uid,'Expected same pod UID'
            container=current.get('status',{}).get('containerStatuses',[{}])[0]
            if container.get('restartCount',0)>previous_count and container.get('ready',False):break
            time.sleep(2)
        else:raise RuntimeError('Container did not recover within 90 seconds')
        save(directory/'after-restart-pod.json',current)
        for _ in range(12):clients.append(request_once())
        first=capture.poll(time.time());second=capture.poll(time.time())
        assert second==0,'Repeated polling inserted duplicate spans'
        events=store.window(began,time.time()+1)
        inventory_traces={e['trace_id'] for e in events if e['service']=='inventory'}
        recovered=sum(c['trace_id'] in inventory_traces for c in tail)
        assert recovered==len(tail),'Previous log tail was not fully recovered'
        assert all(c['status']==200 for c in clients[-12:]),'Requests failed after recovery'
        exported=store.export(directory)
        previous_source=uid+'/previous/'+str(container['restartCount'])
        assert store.seen(previous_source),'Previous-container log path was not exercised'
        result.update(status='passed',same_pod_uid=True,current_restart_count=container['restartCount'],
            previous_log_source=previous_source,unpolled_tail_requests=len(tail),
            recovered_inventory_tail_traces=recovered,duplicate_poll_insertions=second,
            clients=len(clients),successful_clients=sum(c['status']==200 for c in clients),
            exported=exported,recovered_at=time.time(),
            boundary='One controlled same-pod restart. Does not establish log-rotation or repeated-restart completeness.')
    except BaseException as exc:
        result.update(status='failed',error=str(exc)[:300]);raise
    finally:
        forward.close()
        save(directory/'client_requests.json',clients)
        save(directory/'report.json',result)
        print(json.dumps(result,indent=2))


if __name__=='__main__':main()
