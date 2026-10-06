"""Guided laptop workspace; bounded local actions and read-only saved evidence."""
import json
import os
import re
import socket
import shutil
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT/'artifacts/live_runtime'
FIGURES = ROOT/'artifacts/report_figures'
router = APIRouter()
lock = threading.Lock()
child = None
log_handle = None
cluster_health_cache = {}
cluster_health_lock = threading.Lock()


def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8-sig')) if path.exists() else default


def latest_demo():
    directories = sorted(RUNTIME.glob('demo-*'), reverse=True) if RUNTIME.exists() else []
    return directories[0] if directories else None


def validated_cluster_report():
    receipt=read(ROOT/'artifacts/laptop_validation/final_summary.json', {})
    run=receipt.get('run_id')
    return read(ROOT/'artifacts/kubernetes'/run/'report.json', {}) if run else {}


@router.get('/')
def home():
    return FileResponse(ROOT/'web/workspace.html')


@router.get('/archive-help.js')
def archive_help():
    return FileResponse(ROOT/'web/archive_help.js', media_type='text/javascript')


@router.get('/api/workspace')
def workspace(stream: str | None = Query(default=None, pattern=r'^demo-[0-9T]+-[a-f0-9]{8}$')):
    from .native_observer import status
    directory = RUNTIME/stream if stream else latest_demo()
    if stream and not directory.is_dir():
        raise HTTPException(404,'Unknown saved demo')
    demo = read(directory/'status.json', dict(status='starting', windows=0)) if directory else dict(status='idle', windows=0)
    history = []
    if directory:
        demo.update(read(directory/'completion.json', {}))
        demo.update(stream=directory.name, metadata=read(directory/'runtime.json', {}),
                    schedule=read(directory/'schedule.json', {}))
        history = status(stream=directory.name)['predictions'][::-1]
        if child and child.poll() is not None and demo['status'] in ('running','starting'):
            demo.update(status='failed',error='Demo worker exited before recording cleanup. Inspect '+str(directory/'runtime.log'))
        if demo['status'] in ('running','starting') and time.time()-directory.stat().st_mtime>120:
            demo.update(status='interrupted', error='Collector stopped updating. Inspect runtime logs before interpreting telemetry.')
    cluster = validated_cluster_report()
    review = read(ROOT/'artifacts/kubernetes'/cluster.get('run_id','missing')/'trace_review.json', {})
    demos=[]
    for saved in sorted(RUNTIME.glob('demo-*'),reverse=True)[:20]:
        metadata=read(saved/'runtime.json',{})
        completion=read(saved/'completion.json',{})
        demos.append(dict(stream=saved.name,scenario=metadata.get('scenario','starting'),
                          status=completion.get('status','running')))
    active=latest_demo()
    active_demo=bool(active and not (active/'completion.json').exists() and time.time()-active.stat().st_mtime<120)
    return dict(demo=demo, history=history, demos=demos, active_demo=active_demo, cluster=cluster, trace_review=review,
        figures=read(FIGURES/'index.json', {}), llm_enabled=False,
        finished='Research, CPU portability and controlled laptop Kubernetes validation complete. Industrial validation remains open.',
        server_time=time.time())


class DemoRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    scenario: Literal['healthy','delay'] = 'healthy'


def local_action(request):
    origin = request.headers.get('origin')
    if request.client.host not in ('127.0.0.1','::1','testclient'):
        raise HTTPException(403, 'Demo controls are localhost only')
    if request.url.hostname not in ('127.0.0.1','localhost','::1','testserver'):
        raise HTTPException(403, 'Use the localhost dashboard address')
    if origin and origin != str(request.base_url).rstrip('/'):
        raise HTTPException(403, 'Use this dashboard origin for demo controls')


@router.post('/api/workspace/demo')
def start_demo(payload: DemoRequest, request: Request):
    global child, log_handle
    local_action(request)
    with lock:
        if child and child.poll() is None:
            raise HTTPException(409, 'A one-minute demo is already running. Watch it or stop it first.')
        previous = latest_demo()
        if previous and not (previous/'completion.json').exists() and time.time()-previous.stat().st_mtime<120:
            raise HTTPException(409, 'A demo is still active; wait for cleanup before starting another.')
        for port in (8891,8892,8893):
            with socket.socket() as sock:
                try:
                    sock.bind(('127.0.0.1',port))
                except OSError:
                    raise HTTPException(409, f'Local service port {port} is occupied. Finish that workload first.')
        stream = 'demo-'+time.strftime('%Y%m%dT%H%M%S')+'-'+uuid.uuid4().hex[:8]
        directory = RUNTIME/stream
        directory.mkdir(parents=True)
        from .native_experiment import save
        save(directory/'status.json',dict(status='starting', windows=0, scenario=payload.scenario, stream=stream))
        if log_handle:
            log_handle.close()
        log_handle = (directory/'runtime.log').open('ab')
        child = subprocess.Popen([sys.executable,'-m','incidentlab.guided_runtime','--stream',stream,
            '--scenario',payload.scenario], cwd=ROOT, stdout=log_handle, stderr=log_handle,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        return dict(status='starting',stream=stream,seconds=60,training=False)


@router.post('/api/workspace/demo/stop')
def stop_demo(request: Request):
    local_action(request)
    directory = latest_demo()
    if directory and not (directory/'completion.json').exists():
        (directory/'stop').write_text('User requested graceful cleanup', encoding='utf-8')
    return dict(status='stop_requested', note='The worker clears its fault and closes only its own services.')


@router.get('/api/workspace/cluster/{phase}')
def cluster_phase(phase: str):
    if not re.fullmatch(r'test_(healthy|surge|(delay|error|unavailable)_(frontend|checkout|inventory))', phase):
        raise HTTPException(404,'Unknown controlled phase')
    report = validated_cluster_report()
    directory = ROOT/'artifacts/kubernetes'/report.get('run_id','missing')/phase
    if not directory.is_dir():
        raise HTTPException(404,'No completed phase')
    return dict(run_id=report['run_id'],phase=phase,predictions=read(directory/'predictions.json', []),
        schedule=read(directory/'schedule.json'),
        boundary='Saved cluster telemetry, not a running collector. Labels are control-completion proxies.')


@router.get('/api/workspace/figures/{name}')
def figure(name: str):
    if not re.fullmatch(r'[a-z0-9_-]+\.(png|svg|pdf|json|zip)', name) or not (FIGURES/name).is_file():
        raise HTTPException(404,'Unknown report figure')
    return FileResponse(FIGURES/name, filename=name if name.endswith(('.pdf','.zip','.json')) else None)


@router.get('/api/workspace/report')
def report_download():
    return FileResponse(ROOT/'docs/laptop_execution_20261006.md',filename='IncidentLab-laptop-report.md')


@router.get('/api/workspace/documents/{name}')
def document_download(name: str):
    documents={'ieee.pdf':ROOT/'reports/IncidentLab-IEEE-readable.pdf',
        'ieee.tex':ROOT/'reports/IncidentLab-IEEE.tex',
        'ieee-source.zip':ROOT/'reports/IncidentLab-IEEE-source.zip',
        'resume.md':ROOT/'docs/resume_project_description.md'}
    if name not in documents or not documents[name].is_file():
        raise HTTPException(404,'Unknown project document')
    return FileResponse(documents[name],filename=documents[name].name)


@router.get('/api/workspace/cluster-health')
def cluster_health():
    """Current pod readiness, separate from archived telemetry; no cluster mutation."""
    global cluster_health_cache
    with cluster_health_lock:
        if time.time()-cluster_health_cache.get('checked_at',0)<15:
            return cluster_health_cache
        result=dict(checked_at=time.time(),context='kind-incidentlab',namespace='incidentlab-testbed',
            node_container='incidentlab-control-plane',pods=[],status='unavailable',
            boundary='Live Kubernetes pod status only. The charts below are saved experiment data.')
        binary=shutil.which('kubectl')
        if not binary:
            result['message']='kubectl is unavailable. Saved results still work.'
        else:
            try:
                process=subprocess.run([binary,'--context','kind-incidentlab','-n','incidentlab-testbed',
                    'get','pods','-l','app.kubernetes.io/part-of=incidentlab-testbed','-o','json',
                    '--request-timeout=5s'],capture_output=True,timeout=8,
                    creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
                if process.returncode:
                    raise RuntimeError('Cannot reach the cluster. Start Docker Desktop and check the IncidentLab node.')
                if len(process.stdout)>1024*1024:raise ValueError('Pod status exceeded its read budget')
                for pod in json.loads(process.stdout)['items']:
                    service=pod['metadata']['labels'].get('app.kubernetes.io/name')
                    if service not in ('frontend','checkout','inventory'):continue
                    containers=pod.get('status',{}).get('containerStatuses',[])
                    result['pods'].append(dict(service=service,name=pod['metadata']['name'],
                        ready=bool(containers) and all(c.get('ready',False) for c in containers),
                        phase=pod.get('status',{}).get('phase','Unknown'),
                        restarts=sum(c.get('restartCount',0) for c in containers),
                        node=pod.get('spec',{}).get('nodeName')))
                services={p['service'] for p in result['pods'] if p['ready']}
                result.update(status='ready' if len(services)==3 else 'needs_review',
                    message='All three apps are ready.' if len(services)==3 else 'Some test apps are not ready. Inspect the pod rows.')
            except (OSError,ValueError,RuntimeError,subprocess.TimeoutExpired) as exc:
                result['message']=str(exc)[:200]
        cluster_health_cache=result
        return result
