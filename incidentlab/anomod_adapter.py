"""Explicit source normalization. No model fitting or fault-case evaluation."""
import argparse
import csv
import json
import math
from datetime import datetime
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq

from .research_pipeline import ROOT, OUT, dump

SCHEMA=pa.schema([
    ('service',pa.string()),('span_id',pa.string()),('parent_span_id',pa.string()),
    ('timestamp_epoch_seconds',pa.float64()),('timestamp_local',pa.timestamp('us')),
    ('duration_us',pa.float64()),('status_code',pa.int32()),('status_source',pa.string())])


def normalize_tt_span(span):
    duration=float(span['duration_ms'])
    if not math.isfinite(duration) or duration<0:raise ValueError('Invalid span duration')
    stamp=float(span['start_timestamp_ms'])/1000
    if not math.isfinite(stamp):raise ValueError('Invalid span timestamp')
    if type(span['is_error']) is not bool:raise ValueError('Expected an actual error boolean')
    return dict(service=span['service_code'],span_id=span['node_id'],parent_span_id=span.get('parent_node_id'),
        timestamp_epoch_seconds=stamp,timestamp_local=None,
        duration_us=duration*1000,status_code=500 if span['is_error'] else 0,
        status_source='SkyWalking error boolean mapped to synthetic indicator; not HTTP status')


def normalize_sn_span(row):
    stamp=datetime.fromisoformat(row['start_time'])
    duration=float(row['duration_us'])
    if not math.isfinite(duration) or duration<0:raise ValueError('Invalid span duration')
    aware=stamp.utcoffset() is not None
    return dict(service=row['service'],span_id=row['span_id'],parent_span_id=row['parent_span_id'] or None,
        timestamp_epoch_seconds=stamp.timestamp() if aware else None,
        timestamp_local=None if aware else stamp,duration_us=duration,
        status_code=int(row['http_status_code']) if row['http_status_code'] else None,
        status_source='HTTP status; empty values remain unknown')


def counter_rate(previous_time,previous_value,current_time,current_value):
    """Same-series, forward-only derivative; reset intervals are unavailable, not negative rates."""
    if not all(math.isfinite(v) for v in [previous_time,previous_value,current_time,current_value]):
        raise ValueError('Counter inputs must be finite')
    if min(previous_value,current_value)<0:raise ValueError('Counter values must be nonnegative')
    if current_time<=previous_time:raise ValueError('Counter samples must be strictly chronological')
    if current_value<previous_value:return None
    return (current_value-previous_value)/(current_time-previous_time)


def export_normal():
    base=ROOT/'data/research/AnoMod'
    destination=ROOT/'data/processed/anomod-normal';destination.mkdir(parents=True,exist_ok=True)
    report={'scope':'Healthy-reference trace schema normalization only; no inference, training or threshold adjustment',
            'systems':{},'timezone_policy':'Naive timestamps stay local; epoch conversion requires separately verified source zone'}
    for system in ['TT_data','SN_data']:
        directories=[p for p in (base/system/'trace_data').iterdir() if p.is_dir() and p.name.startswith('Normal')]
        if len(directories)!=1:raise ValueError('Expected one designated normal trace directory')
        source=directories[0]
        if system=='TT_data':
            files=list(source.glob('*.json'))
            if len(files)!=1:raise ValueError('Unexpected TrainTicket trace files')
            obj=json.loads(files[0].read_text())
            iterator=(normalize_tt_span(s) for t in obj['traces'] for s in t['spans'])
            handle=None
        else:
            handle=(source/'all_traces.csv').open(encoding='utf-8',newline='')
            iterator=(normalize_sn_span(r) for r in csv.DictReader(handle))
        count=unknown_time=unknown_status=0;services=set();batch=[]
        path=destination/f'{system}-spans.parquet'
        try:
            with pq.ParquetWriter(path,SCHEMA,compression='zstd') as writer:
                for row in iterator:
                    count+=1;unknown_time+=row['timestamp_epoch_seconds'] is None
                    unknown_status+=row['status_code'] is None;services.add(row['service']);batch.append(row)
                    if len(batch)==8192:
                        writer.write_table(pa.Table.from_pylist(batch,schema=SCHEMA));batch=[]
                if batch:writer.write_table(pa.Table.from_pylist(batch,schema=SCHEMA))
        finally:
            if handle:handle.close()
        report['systems'][system]=dict(spans=count,services=sorted(services),missing_epoch_timestamps=unknown_time,
                                       missing_status=unknown_status,file=str(path.relative_to(ROOT)))
    dump(OUT/'anomod_adapter_preparation.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    export_normal()
