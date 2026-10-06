"""Normalize designated normal telemetry; no fault runs or model predictions."""
import csv
import hashlib
import json
import re
from collections import Counter,defaultdict
from datetime import datetime,timezone

import pyarrow as pa
import pyarrow.parquet as pq

from .anomod_adapter import counter_rate,normalize_tt_span,normalize_sn_span
from .research_pipeline import ROOT,OUT,ERROR,dump

BASE=ROOT/'data/research/AnoMod'
DEST=ROOT/'data/processed/anomod-normal'
METRIC_SCHEMA=pa.schema([('service',pa.string()),('kind',pa.string()),('timestamp',pa.float64()),
                        ('value',pa.float64()),('source',pa.string())])
LOG_SCHEMA=pa.schema([('service',pa.string()),('timestamp',pa.float64()),('error_indicator',pa.bool_()),
                     ('message',pa.string())])


def normal(system,modality):
    directories=[p for p in (BASE/system/modality).iterdir() if p.is_dir() and p.name.startswith('Normal')]
    if len(directories)!=1:raise ValueError('Expected one designated healthy reference')
    return directories[0]


def source_time_zone():
    """Recover the collector's observed offset using every paired healthy Jaeger span."""
    directory=normal('SN_data','trace_data')
    obj=json.loads((directory/'all_traces.json').read_text())
    raw={(t['traceID'],s['spanID']):s['startTime']/1e6 for t in obj['data'] for s in t['spans']}
    offsets=Counter()
    with (directory/'all_traces.csv').open() as f:
        for row in csv.DictReader(f):
            local=datetime.fromisoformat(row['start_time']).replace(tzinfo=timezone.utc).timestamp()
            offsets[round(local-raw[(row['trace_id'],row['span_id'])],3)]+=1
    if len(offsets)!=1 or next(iter(offsets))!=0:
        raise ValueError('Healthy collector timezone is not consistently UTC')
    return dict(paired_spans=sum(offsets.values()),offset_seconds=0,
                evidence='All healthy CSV span IDs match raw Jaeger microsecond epochs. Author metric and trace exporters both use datetime.fromtimestamp.')


def tt_metrics(directory=None):
    series=defaultdict(list);audit=Counter()
    mappings={'container_cpu_usage_seconds_total':('cpu',True),
              'container_memory_usage_bytes':('mem',False)}
    for path in (directory or normal('TT_data','metric_data')).glob('*.csv'):
        with path.open(encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                audit['scanned']+=1
                if row['metric_name'] not in mappings or not row.get('container','').startswith('ts-'):
                    audit['excluded_unmapped_or_infrastructure']+=1;continue
                kind,derivative=mappings[row['metric_name']]
                key=tuple(sorted((k,v) for k,v in row.items() if k not in ['timestamp','datetime','value'] and v))
                series[(row['container'],kind,derivative,key)].append((float(row['timestamp']),float(row['value'])))
    result=[]
    for (service,kind,derivative,key),values in series.items():
        previous=None
        for stamp,value in sorted(values):
            if derivative:
                if previous is None:previous=(stamp,value);continue
                if stamp==previous[0]:audit['duplicate_counter_samples']+=1;continue
                rate=counter_rate(*previous,stamp,value);previous=(stamp,value)
                if rate is None:audit['counter_reset_intervals']+=1;continue
                value=rate
            result.append(dict(service=service,kind=kind,timestamp=stamp,value=value,
                source='cumulative CPU seconds converted to same-series rate' if derivative else 'memory usage bytes'))
    return result,dict(audit)


def sn_metrics(directory=None):
    result=[];audit=Counter()
    mappings={'socialnet_container_cpu.csv':('cpu','author PromQL sum(rate(cpu_seconds_total[5m]))'),
              'socialnet_container_memory.csv':('mem','container memory usage bytes')}
    for filename,(kind,source) in mappings.items():
        with ((directory or normal('SN_data','metric_data'))/filename).open(encoding='utf-8-sig',newline='') as f:
            for row in csv.DictReader(f):
                audit['scanned']+=1
                service=row['container_label_com_docker_compose_service']
                if service in ['cadvisor','prometheus','node-exporter','jaeger-agent']:
                    audit['excluded_infrastructure']+=1;continue
                result.append(dict(service=service,kind=kind,
                    timestamp=datetime.fromisoformat(row['timestamp']).replace(tzinfo=timezone.utc).timestamp(),
                    value=float(row['value']),source=source))
    return result,dict(audit)


def sn_service(filename):
    name=filename.removesuffix('_')
    if name=='NginxThrift':return 'nginx-thrift'
    return re.sub(r'(?<!^)(?=[A-Z])','-',name).lower()


def parse_sn_line(line):
    match=re.match(r'^\[(\d{4}-[A-Za-z]{3}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)\]',line)
    if not match:return None
    return datetime.strptime(match[1],'%Y-%b-%d %H:%M:%S.%f').replace(tzinfo=timezone.utc).timestamp()


def sn_logs(directory=None):
    audit=Counter();result=[]
    for path in (directory or normal('SN_data','log_data')).glob('*.log'):
        service=sn_service(path.stem);current=None
        def flush():
            if current:
                message=''.join(current[1])
                result.append(dict(service=service,timestamp=current[0],
                    error_indicator=bool(ERROR.search(message)),message=message))
        with path.open(encoding='utf-8',errors='replace') as f:
            for line in f:
                audit['physical_lines']+=1
                stamp=parse_sn_line(line)
                if stamp is not None:
                    flush();current=(stamp,[line]);audit['timestamped_events']+=1
                elif current:
                    current[1].append(line);audit['continuation_lines']+=1
                else:audit['unattached_lines']+=1
            flush()
    return result,dict(audit)


def run():
    DEST.mkdir(parents=True,exist_ok=True)
    zone=source_time_zone()
    report=dict(scope='Healthy telemetry normalization; no fault runs, predictions or threshold fitting',
                socialnetwork_time_evidence=zone,
                collection_revision=json.loads((OUT/'anomod_collection_tree.json').read_text())['sha'],systems={})
    for system,loader in [('TT_data',tt_metrics),('SN_data',sn_metrics)]:
        rows,audit=loader()
        pq.write_table(pa.Table.from_pylist(rows,schema=METRIC_SCHEMA),DEST/f'{system}-metrics.parquet',compression='zstd')
        report['systems'][system]=dict(metric_rows=len(rows),metric_services=sorted({r['service'] for r in rows}),metric_audit=audit)
    logs,audit=sn_logs()
    pq.write_table(pa.Table.from_pylist(logs,schema=LOG_SCHEMA),DEST/'SN_data-logs.parquet',compression='zstd')
    report['systems']['SN_data'].update(log_events=len(logs),log_audit=audit,
        log_clock_policy='UTC alignment inferred from shared collector, matching healthy run wall times; container timezone not independently configured by adapter')
    spans=pq.read_table(DEST/'SN_data-spans.parquet').to_pylist()
    for span in spans:
        span['timestamp_epoch_seconds']=span['timestamp_local'].replace(tzinfo=timezone.utc).timestamp()
    from .anomod_adapter import SCHEMA
    pq.write_table(pa.Table.from_pylist(spans,schema=SCHEMA),DEST/'SN_data-spans-aligned.parquet',compression='zstd')
    report['limitations']=['TrainTicket naive application-log timezone remains unresolved; logs not normalized',
        'only CPU/memory have verified service metric mappings; other trained features remain unavailable',
        'nginx-thrift and nginx-web-server not silently merged without application identity evidence',
        'raw values are normalized source records, not reference-scaled model feature windows']
    dump(OUT/'anomod_healthy_normalization.json',report)
    print(json.dumps(report,indent=2))


if __name__=='__main__':run()
