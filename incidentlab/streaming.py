"""Durable causal serving at the trained-feature boundary, not a raw OTLP collector."""
import json
import sqlite3
import threading
from contextlib import closing
from pathlib import Path
from typing import Annotated, Literal

import numpy as np
import torch
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .temporal_model import DEVICE, HISTORY

FiniteFeature = Annotated[float, Field(ge=0, le=1e12, allow_inf_nan=False)]


class ServiceFeatures(BaseModel):
    model_config = ConfigDict(extra='forbid')
    service: str = Field(min_length=1, max_length=128, pattern=r'^[A-Za-z0-9_.-]+$')
    features: list[FiniteFeature] = Field(min_length=18, max_length=18)

    @model_validator(mode='after')
    def availability(self):
        if self.features[10] not in (0, 1) or self.features[15] not in (0, 1):
            raise ValueError('Source availability indicators must be 0 or 1')
        if self.features[16] > 1:
            raise ValueError('Known trace status fraction must be within [0,1]')
        if self.features[17] > 1:
            raise ValueError('Missing metric fraction must be within [0,1]')
        return self


class FeatureWindow(BaseModel):
    model_config = ConfigDict(extra='forbid')
    stream: str = Field(min_length=1, max_length=80, pattern=r'^[A-Za-z0-9_.-]+$')
    profile: Literal['ob', 'ss', 'tt']
    end: int = Field(gt=0)
    feature_schema: Literal['rcaeval-multimodal-v2']
    services: list[ServiceFeatures] = Field(min_length=1, max_length=128)

    @model_validator(mode='after')
    def unique_aligned(self):
        if self.end % 60:
            raise ValueError('Window end must align to a UTC epoch minute')
        if len({s.service for s in self.services}) != len(self.services):
            raise ValueError('Duplicate service')
        return self


class StreamStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.path = path
        self.lock = threading.Lock()
        with closing(sqlite3.connect(path)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS streams (name TEXT PRIMARY KEY, profile TEXT, end INTEGER, history TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS predictions (id INTEGER PRIMARY KEY, stream TEXT, end INTEGER, result TEXT)')

    def analyze(self, request: FeatureWindow, model, checkpoint):
        # Serialize sequence transitions and inference. Deploy this local prototype with one worker.
        with self.lock, closing(sqlite3.connect(self.path)) as db, db:
            state = db.execute('SELECT profile,end,history FROM streams WHERE name=?', (request.stream,)).fetchone()
            if state and (state[0] != request.profile or request.end <= state[1]):
                raise ValueError('Profile changes and duplicate/out-of-order windows are rejected')
            if state and request.end != state[1] + 60:
                raise ValueError('Missing whole windows: start a new stream after a fresh healthy warm-up')
            if not state and db.execute('SELECT COUNT(*) FROM streams').fetchone()[0] >= 1000:
                raise ValueError('Stream capacity reached')
            if db.execute('SELECT COUNT(*) FROM predictions').fetchone()[0] >= 10000:
                raise ValueError('Prediction archive capacity reached; export/archive before continuing')
            history = json.loads(state[2]) if state else []
            current = {s.service:s.features for s in request.services}
            history.append({'end':request.end, 'services':current})
            history = [h for h in history if h['end'] > request.end - HISTORY * 60]
            names = sorted(current)
            raw = np.zeros((1, len(names), HISTORY, 18), dtype=np.float32)
            # Zero left-padding matches training. Current-window masks control eligibility.
            for h in history:
                slot = HISTORY - 1 - (request.end - h['end']) // 60
                for s, name in enumerate(names):
                    if name in h['services']:
                        raw[0,s,slot] = h['services'][name]
            valid = np.array([[v[17] < 1 or v[10] > 0 or v[15] > 0 for v in (current[n] for n in names)]])
            with torch.inference_mode():
                detect, rank = model(torch.from_numpy(raw).to(DEVICE), torch.from_numpy(valid).to(DEVICE))
                score = float(detect.sigmoid().cpu()[0])
                ranking = rank.cpu()[0].numpy()
                weights = rank.softmax(-1).cpu()[0].numpy()
            candidates = [{'service':names[s], 'ranking_weight':float(weights[s])}
                          for s in np.argsort(-ranking) if valid[0,s] and ranking[s] > -9999][:5]
            threshold = checkpoint['thresholds'][request.profile]
            result = dict(stream=request.stream, end=request.end, score=score, threshold=threshold,
                          alert=bool(candidates) and score > threshold, abstained=not bool(candidates),
                          candidates=candidates, history_windows=len(history),
                          deployment_validated=False,
                          warning='Research thresholds; ranking weights are not causal probabilities. Raw telemetry normalization must match the frozen feature schema.')
            db.execute('INSERT OR REPLACE INTO streams VALUES (?,?,?,?)',
                       (request.stream, request.profile, request.end, json.dumps(history)))
            db.execute('INSERT INTO predictions(stream,end,result) VALUES (?,?,?)',
                       (request.stream, request.end, json.dumps(result)))
            return result

    def history(self, stream: str):
        with closing(sqlite3.connect(self.path)) as db:
            return [json.loads(r[0]) for r in db.execute(
                'SELECT result FROM predictions WHERE stream=? ORDER BY id DESC LIMIT 100', (stream,))]
