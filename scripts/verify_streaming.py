"""Exercise actual HTTP serving; compare sequential predictions with offline inference.

This is an integration/latency check on archived normalized features, not a live fault trial.
"""
import json
import time
import uuid
from pathlib import Path

import httpx
import numpy as np
import pyarrow.parquet as pq

ROOT=Path(__file__).resolve().parents[1]
CASE='re2ob_checkoutservice_delay_1'
client=httpx.Client(base_url='http://127.0.0.1:8768',timeout=60)
expected=client.get(f'/api/replay/{CASE}?model=temporal').raise_for_status().json()['windows']
rows=pq.read_table(ROOT/f'data/processed/multimodal/{CASE}.parquet').to_pylist()
groups={}
for r in rows:
    groups.setdefault(r['window'],[]).append(dict(service=r['service'],
        features=r['features']+[r['metric_columns_missing']/8]))
stream='integration-'+uuid.uuid4().hex[:12]
latencies=[];differences=[]
for i, (_,services) in enumerate(sorted(groups.items())):
    payload=dict(stream=stream,profile='ob',end=(i+1)*60,
                 feature_schema='rcaeval-multimodal-v2',services=services)
    start=time.perf_counter()
    actual=client.post('/api/stream/windows',json=payload).raise_for_status().json()
    latencies.append((time.perf_counter()-start)*1000)
    differences.append(abs(actual['score']-expected[i]['score']))
    if actual['alert']!=expected[i]['alert']:
        raise AssertionError('Serving/replay alert mismatch')
# CUDA GRU kernels differ for batched archive versus single-window serving.
# Require tight score agreement and identical decisions, report the actual discrepancy.
if max(differences)>1e-3:
    raise AssertionError(f'Probability mismatch: {max(differences)}')
duplicate=client.post('/api/stream/windows',json=payload)
assert duplicate.status_code==409
report=dict(case=CASE,windows=len(latencies),stream=stream,
            max_probability_difference=max(differences),duplicate_status=duplicate.status_code,
            http_latency_ms=dict(p50=float(np.median(latencies)),p95=float(np.percentile(latencies,95))),
            scope='Local HTTP, archived feature windows, includes SQLite commit; excludes raw normalization, collection and network transport from services')
(ROOT/'artifacts/research/streaming_verification.json').write_text(json.dumps(report,indent=2))
print(json.dumps(report,indent=2))
