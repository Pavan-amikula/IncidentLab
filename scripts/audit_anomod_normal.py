"""Audit only author-designated healthy reference telemetry, never fault cases.

No prediction, model fitting, threshold selection, or external accuracy calculation.
"""
import csv
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'data/research/AnoMod'
OUT=ROOT/'artifacts/research'


def healthy_directories(system, modality):
    directories=sorted(p for p in (BASE/system/modality).iterdir()
                       if p.is_dir() and p.name.startswith('Normal'))
    if len(directories)!=1:
        raise ValueError(f'Expected exactly one designated healthy reference: {system}/{modality}')
    return directories


def sha(path):
    digest=hashlib.sha256()
    with path.open('rb') as f:
        while chunk:=f.read(1024*1024): digest.update(chunk)
    return digest.hexdigest()


def metric_audit(path):
    names=Counter(); services=set(); times=set(); invalid=0; rows=0
    with path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f);columns=reader.fieldnames
        for row in reader:
            rows+=1; names[row.get('metric_name',path.stem)]+=1
            service=row.get('container_label_com_docker_compose_service') or row.get('container')
            if service: services.add(service)
            times.add(row['timestamp'])
            try:
                if not math.isfinite(float(row['value'])):invalid+=1
            except ValueError:invalid+=1
    # Timestamps are inventoried in their source encoding; naive times aren't silently assigned UTC.
    numeric=all(re.fullmatch(r'\d+(\.\d+)?', t) for t in times)
    ordered=sorted(times,key=float) if numeric else sorted(times)
    return dict(file=str(path.relative_to(BASE)),rows=rows,columns=columns,
                metric_names=dict(names),services=sorted(services),nonfinite_or_invalid_values=invalid,
                timestamp_encoding='numeric epoch seconds' if numeric else 'timezone-naive text; alignment requires verification',
                first_timestamp=ordered[0] if ordered else None,last_timestamp=ordered[-1] if ordered else None,
                unique_timestamps=len(times),sha256=sha(path))


def log_audit(path):
    rows=blank=0;formats=Counter()
    with path.open(encoding='utf-8',errors='replace') as f:
        for line in f:
            rows+=1
            if not line.strip():blank+=1
            elif re.match(r'^\[\d{4}-[A-Za-z]{3}-\d{2}',line):formats['bracket_month_name_no_timezone']+=1
            elif re.match(r'^\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}',line):formats['leading_iso_or_space_time']+=1
            else:formats['continuation_or_other_format']+=1
    return dict(file=str(path.relative_to(BASE)),lines=rows,blank_lines=blank,
                timestamp_formats=dict(formats),sha256=sha(path))


def tt_trace_audit(path, metric_start, metric_end):
    obj=json.loads(path.read_text(encoding='utf-8'));meta=obj['metadata']
    times=[];services=set();spans=outside=errors=0
    for trace in obj['traces']:
        for span in trace['spans']:
            spans+=1;stamp=span['start_timestamp_ms']/1000;times.append(stamp)
            outside+=not metric_start<=stamp<=metric_end
            services.add(span['service_code']);errors+=bool(span['is_error'])
            if span['duration_ms']<0:raise ValueError('Negative duration in healthy reference')
    return dict(file=str(path.relative_to(BASE)),traces=len(obj['traces']),spans=spans,
                collector_lookback_hours=meta.get('lookback_hours'),services=sorted(services),
                duration_unit='milliseconds; convert x1000 to microseconds for trained trace features',
                status_encoding='is_error boolean; not an HTTP status code',error_spans=errors,
                first_epoch_seconds=min(times),last_epoch_seconds=max(times),
                spans_outside_metric_interval=outside,sha256=sha(path))


def sn_trace_audit(path):
    services=Counter();rows=0;times=[];known=0
    with path.open(encoding='utf-8',newline='') as f:
        reader=csv.DictReader(f);columns=reader.fieldnames
        for row in reader:
            rows+=1;services[row['service']]+=1;times.append(row['start_time'])
            known+=bool(row['http_status_code'])
            if float(row['duration_us'])<0:raise ValueError('Negative trace duration')
    return dict(file=str(path.relative_to(BASE)),spans=rows,columns=columns,services=dict(services),
                duration_unit='microseconds',timestamp_encoding='timezone-naive text; alignment requires verification',
                first_timestamp=min(times),last_timestamp=max(times),http_status_known=known,
                sha256=sha(path))


def main():
    report=dict(scope='Designated healthy reference directories only. Fault telemetry and labels not read.',
                training_performed=False,predictions_performed=False,systems={})
    for system in ['TT_data','SN_data']:
        metrics=[];logs=[];traces=[]
        for directory in healthy_directories(system,'metric_data'):
            metrics=[metric_audit(p) for p in sorted(directory.glob('*.csv'))]
        for directory in healthy_directories(system,'log_data'):
            logs=[log_audit(p) for p in sorted(directory.rglob('*.log'))]
        for directory in healthy_directories(system,'trace_data'):
            if system=='TT_data':
                traces=[tt_trace_audit(p,float(metrics[0]['first_timestamp']),float(metrics[0]['last_timestamp']))
                        for p in sorted(directory.glob('*.json'))]
            else:traces=[sn_trace_audit(directory/'all_traces.csv')]
        report['systems'][system]=dict(metrics=metrics,logs=logs,traces=traces,
            metric_rows=sum(m['rows'] for m in metrics),log_lines=sum(l['lines'] for l in logs),
            trace_spans=sum(t['spans'] for t in traces))
        print(system, {k:report['systems'][system][k] for k in ['metric_rows','log_lines','trace_spans']},flush=True)
    report['checkpoints']={p.name:sha(p) for p in [OUT/'temporal_best.pt',OUT/'supervised_reference.joblib']}
    (OUT/'anomod_normal_audit.json').write_text(json.dumps(report,indent=2))
    print('Healthy-reference schema audit saved. External fault evaluation remains unopened.')


if __name__=='__main__': main()
