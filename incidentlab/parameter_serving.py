"""Causal, transactional serving of the frozen OpenStack parameter comparison."""
import hashlib
import json
import sqlite3
import threading
from contextlib import closing
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Literal

import joblib
import numpy as np
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .openstack_parameters import OPERATIONS, SCHEMA, robust_scores
from .parameter_calibration import tail_probabilities
from .research_pipeline import ROOT, OUT

DATABASE=ROOT/'artifacts/openstack_parameters.sqlite3'
router=APIRouter()


class ParameterEvent(BaseModel):
    model_config=ConfigDict(extra='forbid')
    instance: str=Field(pattern=r'^[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}$')
    operation: Literal['spawn the instance on the hypervisor','build instance',
                       'destroy the instance on the hypervisor','deallocate network for instance']
    duration_seconds: float=Field(ge=0,le=600000,allow_inf_nan=False)
    line_number: int=Field(ge=1)
    observed_timestamp: str=Field(pattern=r'^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{1,9}$')

    @model_validator(mode='after')
    def timestamp(self):
        datetime.fromisoformat(self.observed_timestamp)
        return self


class ParameterBatch(BaseModel):
    model_config=ConfigDict(extra='forbid')
    stream: str=Field(pattern=r'^[A-Za-z0-9_.-]{1,80}$')
    feature_schema: Literal['openstack-lifecycle-parameters-v1']
    calibration_profile: Literal['v3','v4']='v3'
    events: list[ParameterEvent]=Field(min_length=1,max_length=128)


@lru_cache(maxsize=2)
def bundle(profile='v3'):
    report=OUT/f'openstack_parameters_{profile}_report.json'
    checkpoint=OUT/f'openstack_parameter_models_{profile}.joblib'
    if not report.exists() or not checkpoint.exists():
        raise ValueError('Run the full healthy-calibrated OpenStack parameter comparison first')
    digest=hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if digest!=json.loads(report.read_text())['checkpoint_sha256']:
        raise ValueError('Parameter checkpoint differs from its report')
    model=joblib.load(checkpoint)
    if model['schema']!=SCHEMA or tuple(model['operations'])!=OPERATIONS:
        raise ValueError('Incompatible parameter checkpoint')
    return model,digest


class ParameterStore:
    def __init__(self,path=DATABASE):
        self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
        self.lock=threading.Lock()
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('CREATE TABLE IF NOT EXISTS parameter_streams (stream TEXT PRIMARY KEY, checkpoint TEXT, sequence INTEGER)')
            db.execute('CREATE TABLE IF NOT EXISTS parameter_instances (stream TEXT,instance TEXT,state TEXT,PRIMARY KEY(stream,instance))')
            db.execute('CREATE TABLE IF NOT EXISTS parameter_predictions (stream TEXT,sequence INTEGER,instance TEXT,result TEXT,PRIMARY KEY(stream,sequence))')

    def analyze(self,request,model,digest):
        with self.lock,closing(sqlite3.connect(self.path,timeout=10)) as db,db:
            db.execute('BEGIN IMMEDIATE')
            previous=db.execute('SELECT checkpoint,sequence FROM parameter_streams WHERE stream=?',(request.stream,)).fetchone()
            if previous and previous[0]!=digest:
                raise ValueError('Changing a frozen checkpoint requires a new stream')
            if not previous and db.execute('SELECT COUNT(*) FROM parameter_streams').fetchone()[0]>=1000:
                raise ValueError('Parameter stream capacity reached')
            if db.execute('SELECT COUNT(*) FROM parameter_predictions').fetchone()[0]+len(request.events)>20000:
                raise ValueError('Parameter prediction capacity reached; archive first')
            sequence=previous[1] if previous else 0
            states,vectors,evidence=[],[],[]
            cache={}
            for event in request.events:
                if event.line_number<=sequence:
                    raise ValueError('Duplicate or out-of-order source lines are rejected')
                sequence=event.line_number
                if event.instance not in cache:
                    row=db.execute('SELECT state FROM parameter_instances WHERE stream=? AND instance=?',
                        (request.stream,event.instance)).fetchone()
                    cache[event.instance]=json.loads(row[0]) if row else {}
                state=cache[event.instance]
                old=state.get(event.operation)
                if old is None or event.duration_seconds>old['duration_seconds']:
                    state[event.operation]=event.model_dump()
                # Snapshot each prefix, before later events in the same batch arrive.
                vector=np.array([state[operation]['duration_seconds'] if operation in state else np.nan for operation in OPERATIONS])
                vectors.append(vector.copy())
                evidence.append([dict(value) for value in state.values()])
                states.append(event)
            matrix=np.stack(vectors)
            residual=robust_scores(matrix,model['center'],model['scale'])
            features=np.column_stack([np.nan_to_num((matrix-model['center'])/model['scale'],nan=0.0),np.isnan(matrix).astype(float)])
            ml=-model['model'].score_samples(features)
            ranked,combined=tail_probabilities(matrix,model['rank_references']) if 'rank_references' in model else (None,None)
            results=[]
            for i,event in enumerate(states):
                values=vectors[i]
                result=dict(stream=request.stream,line_number=event.line_number,instance=event.instance,
                    feature_schema=SCHEMA,checkpoint_sha256=digest,
                    calibration_profile=request.calibration_profile,
                    parameters={key:(float(value) if np.isfinite(value) else None) for key,value in zip(OPERATIONS,values)},
                    parameter_residual=float(residual[i]),parameter_isolation_forest=float(ml[i]),
                    parameter_warning=bool(combined[i]<=model['alpha']) if combined is not None else bool(residual[i]>model['thresholds']['parameter_residual']),
                    residual_warning=bool(residual[i]>model['thresholds']['parameter_residual']),
                    ml_warning=bool(ml[i]>model['thresholds']['parameter_isolation_forest']) if np.isfinite(values).all() else None,
                    ml_eligible=bool(np.isfinite(values).all()),
                    observed_operations=int(np.isfinite(values).sum()),evidence=evidence[i],
                    development_calibration=True,deployment_validated=False,
                    notice='Observed operation durations; partial lifecycle and capture censoring remain possible. Source clock timezone and fault onset are not inferred.')
                if combined is not None:
                    result.update(combined_tail_pvalue=float(combined[i]),
                        operation_tail_pvalues={name:float(ranked[i,j]) if np.isfinite(ranked[i,j]) else None for j,name in enumerate(OPERATIONS)},
                        tail_notice='Calibrated rank is not a probability of fault. Nominal alpha assumes valid calibration; ordered/censored streams do not establish a guarantee.')
                db.execute('INSERT INTO parameter_predictions VALUES (?,?,?,?)',
                    (request.stream,event.line_number,event.instance,json.dumps(result)))
                results.append(result)
            for instance,state in cache.items():
                db.execute('INSERT OR REPLACE INTO parameter_instances VALUES (?,?,?)',
                    (request.stream,instance,json.dumps(state)))
            db.execute('INSERT OR REPLACE INTO parameter_streams VALUES (?,?,?)',(request.stream,digest,sequence))
            return results

    def history(self,stream):
        with closing(sqlite3.connect(self.path)) as db:
            return [json.loads(row[0]) for row in db.execute(
                'SELECT result FROM parameter_predictions WHERE stream=? ORDER BY sequence DESC LIMIT 100',(stream,))]


@lru_cache(maxsize=1)
def store(): return ParameterStore()


@router.post('/api/openstack/parameters')
def observe_parameters(request:ParameterBatch):
    try:
        model,digest=bundle(request.calibration_profile)
        return dict(results=store().analyze(request,model,digest))
    except ValueError as exc:
        raise HTTPException(409,str(exc)) from exc


@router.get('/api/openstack/schema')
def parameter_schema():
    return dict(feature_schema=SCHEMA,operations=list(OPERATIONS),duration_unit='seconds',
        profiles=dict(v3='Two-sided robust residual, original parameter IF',v4='One-sided operation-calibrated delay rank; original parameter IF retained'),
        boundary='Structured raw-log measurements; explicit instance association and source line order required',
        clock='Causal in source-line ingestion order. Source timezone and fault-onset semantics are unspecified',
        calibration='Development healthy OpenStack reference; not calibrated for arbitrary company infrastructure')


@router.get('/api/openstack/{stream}/history')
def parameter_history(stream:str): return dict(results=store().history(stream))
