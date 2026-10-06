"""Read-only dashboard access to locally collected HTTP trials."""
import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from typing import Literal

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'artifacts/live'
router = APIRouter()


@router.get('/api/native/observers')
def native_observers():
    from .native_observer import status
    return status()


@router.get('/api/native/observers/{stream}/history')
def native_observer_history(stream: str):
    from .native_observer import status
    return status(stream=stream)
PHASES = ('healthy_train', 'healthy_validation', 'test_healthy', 'test_surge',
          'test_delay', 'test_error', 'test_unavailable') + tuple(
    f'test_{kind}_{service}' for kind in ('delay','error','unavailable')
    for service in ('frontend','checkout','inventory'))
PHASES += tuple(f'{phase}_r{repeat}' for phase in PHASES if phase.startswith('test_')
                and phase not in ('test_healthy','test_surge') for repeat in range(1,6))


def read(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


@router.get('/live')
def live_page():
    return FileResponse(ROOT/'web/live.html')


@router.get('/api/live/status')
def live_status():
    progress = read(OUT/'progress.json', {'status': 'not_started'})
    report = read(OUT/'latest_report.json')
    run_id = progress.get('run_id')
    phases = []
    if run_id:
        phases = [phase for phase in PHASES if (OUT/run_id/phase/'windows.json').exists()]
    return dict(progress=progress, report=report, completed_phases=phases,
                grouped_report=read(OUT/run_id/'grouped_incident_report.json') if run_id else None,
                llm_report=read(OUT/'latest_llm_report.json'),
                source='Actual HTTP requests in three isolated local service processes',
                deployment='Native Windows development testbed; not Kubernetes or a company deployment')


@router.get('/api/live/trial/{phase}')
def live_trial(phase: str):
    if phase not in PHASES:
        raise HTTPException(404, 'Unknown trial')
    progress = read(OUT/'progress.json', {})
    run_id = progress.get('run_id')
    if not run_id:
        raise HTTPException(404, 'No native run collected')
    directory = OUT/run_id/phase
    rows = read(directory/'windows.json')
    if rows is None:
        raise HTTPException(409, 'Trial is still collecting')
    predictions = read(directory/'predictions.json', [])
    return dict(phase=phase, run_id=run_id, windows=rows[-300:],
                predictions=predictions[-100:], prediction_offset=max(0,len(predictions)-100),
                llm_diagnoses=read(directory/'llm_diagnoses_llm_medium_v2.json',
                    read(directory/'llm_diagnoses_llm_medium.json',
                    read(directory/'llm_diagnoses_llm.json', read(directory/'llm_diagnoses.json', []))))[-100:],
                schedule=read(directory/'schedule.json'),
                note='Schedule is evaluation-only and never passed to scoring')


class DiagnosisRequest(BaseModel):
    model_config = ConfigDict(extra='forbid')
    phase: str = Field(pattern=r'^test_(healthy|surge|(delay|error|unavailable)(_(frontend|checkout|inventory))?(_r[1-5])?)$')
    window: int = Field(ge=0, le=10000)
    mode: Literal['logs_only', 'hybrid'] = 'hybrid'
    policy_version: Literal['v1','v2'] = 'v1'


@router.post('/api/live/diagnose')
def live_diagnose(request: DiagnosisRequest):
    if os.environ.get('INCIDENTLAB_DISABLE_LLM')=='1':
        raise HTTPException(503,'Local LLM generation is disabled in the CPU laptop profile. Saved explanations remain available.')
    progress = read(OUT/'progress.json', {})
    if not progress.get('run_id'):
        raise HTTPException(404, 'No live run')
    values = read(OUT/progress['run_id']/request.phase/'predictions.json', [])
    if request.window >= len(values):
        raise HTTPException(404, 'Choose a completed prediction window')
    if not any((ROOT/'models'/role/'provenance.json').exists() for role in ('llm', 'llm_medium')):
        raise HTTPException(503, 'Download and verify the pinned local LLM first')
    try:
        from .evidence_diagnosis import diagnose
    except ImportError as exc:
        raise HTTPException(503, 'Install requirements-semantic.txt for optional LLM diagnosis') from exc
    result = diagnose(values[request.window], request.mode, policy_version=request.policy_version)
    # Store only the bounded input reference and generated result; never a control schedule.
    archive = OUT/progress['run_id']/request.phase/'on_demand_diagnoses.jsonl'
    with archive.open('a', encoding='utf-8') as output:
        output.write(json.dumps(dict(window=request.window, **result))+'\n')
    return result
