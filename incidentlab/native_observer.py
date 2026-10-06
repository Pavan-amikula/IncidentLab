"""Transactional raw-event observer and conservative incident grouping.

Uses the calibrated native HTTP model, never the RCAEval GRU's incompatible schema.
Persists offsets, partial records, future events and predictions together in SQLite.
"""
import argparse
import hashlib
import json
import math
import re
import sqlite3
import threading
import time
from contextlib import closing
from pathlib import Path

import joblib

from .live_monitor import FEATURES, SERVICES, aggregate, score
from .native_experiment import ROOT, OUT
from .raw_telemetry import EventCollector

DATABASE = ROOT/'artifacts/native_observer.sqlite3'


def native_bundle(run_id):
    if not re.fullmatch(r'\d{8}T\d{6}-[0-9a-f]{6}', run_id):
        raise ValueError('Choose a completed native run ID')
    directory = OUT/run_id
    report = json.loads((directory/'report.json').read_text(encoding='utf-8'))
    checkpoint = directory/'native_monitor.joblib'
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if report['status']!='complete' or report['checkpoint_sha256']!=digest:
        raise ValueError('Native checkpoint does not match its completed experiment')
    bundle = joblib.load(checkpoint)
    if bundle['schema']!='incidentlab-http-v1' or tuple(bundle['features'])!=FEATURES or set(bundle['services'])!=set(SERVICES):
        raise ValueError('Incompatible native checkpoint schema')
    return bundle, digest


def collector_state(collector):
    return dict(positions=collector.positions, carry={k:v.hex() for k,v in collector.carry.items()},
        pending=collector.pending, record_count=collector.record_count,
        late_count=collector.late_count, last_end=collector.last_end)


def restore_collector(directory, state):
    collector = EventCollector(directory)
    if state is not None:
        collector.positions = state['positions']
        collector.carry = {k:bytes.fromhex(v) for k,v in state['carry'].items()}
        collector.pending = state['pending']
        collector.record_count = state['record_count']
        collector.late_count = state['late_count']
        collector.last_end = state['last_end']
    return collector


def incident_transition(state, prediction):
    state = dict(state or dict(active=False, warning_streak=0, clear_streak=0,
                              opened_incidents=0, closed_incidents=0))
    warning = prediction['operational_alert']
    state['warning_streak'] = state['warning_streak']+1 if warning else 0
    state['clear_streak'] = 0 if warning else state['clear_streak']+1
    transition = None
    if not state['active'] and state['warning_streak']==2:
        state.update(active=True, opened_incidents=state['opened_incidents']+1,
            opened_at=prediction['end'], first_warning_at=prediction['start']-3,
            service_hypothesis=prediction['candidates'][0]['service'])
        transition='opened'
    elif state['active'] and state['clear_streak']==2:
        state.update(active=False, closed_incidents=state['closed_incidents']+1,
                     closed_at=prediction['end'])
        transition='closed'
    # Raw warnings are retained immediately. Grouping does not suppress their evidence.
    return state, transition


class NativeObserver:
    def __init__(self, database=DATABASE):
        self.database = Path(database)
        self.database.parent.mkdir(parents=True, exist_ok=True)
        self.lock = threading.Lock()
        with closing(sqlite3.connect(self.database)) as db, db:
            db.execute('CREATE TABLE IF NOT EXISTS observers '
                '(stream TEXT PRIMARY KEY, source TEXT, checkpoint TEXT, end REAL, state TEXT, incident TEXT, identities TEXT)')
            db.execute('CREATE TABLE IF NOT EXISTS native_predictions '
                '(stream TEXT, end REAL, prediction TEXT, PRIMARY KEY(stream,end))')

    def observe(self, stream, directory, start, end, bundle, checkpoint):
        if not re.fullmatch(r'[A-Za-z0-9_.-]{1,80}', stream):
            raise ValueError('Invalid stream ID')
        if not all(math.isfinite(v) and v>0 for v in (start,end)) or abs(end-start-3)>1e-6:
            raise ValueError('Use finite three-second completed windows')
        if end > time.time()+.01:
            raise ValueError('Do not observe a future window')
        directory = Path(directory).resolve(strict=True)
        if not directory.is_dir():
            raise ValueError('Source must be a telemetry directory')
        # BEGIN IMMEDIATE protects offset/prediction transitions across observer instances.
        with self.lock, closing(sqlite3.connect(self.database, timeout=10)) as db, db:
            db.execute('BEGIN IMMEDIATE')
            row = db.execute('SELECT source,checkpoint,end,state,incident,identities FROM observers WHERE stream=?', (stream,)).fetchone()
            if row and (row[0]!=str(directory) or row[1]!=checkpoint):
                raise ValueError('A stream cannot change its source or frozen checkpoint')
            if row and abs(start-row[2])>1e-6:
                raise ValueError('Duplicate, overlapping or missing windows: use a new stream after a gap')
            if not row and db.execute('SELECT COUNT(*) FROM observers').fetchone()[0]>=1000:
                raise ValueError('Observer capacity reached')
            if db.execute('SELECT COUNT(*) FROM native_predictions').fetchone()[0]>=20000:
                raise ValueError('Prediction capacity reached; archive before continuing')
            identities = json.loads(row[5]) if row else {}
            for service in SERVICES:
                path = directory/f'{service}.jsonl'
                if path.exists():
                    stat = path.stat()
                    identity = [stat.st_dev, stat.st_ino]
                    if not stat.st_ino:
                        raise ValueError('Stable telemetry file identity is unavailable')
                    if service in identities and identities[service]!=identity:
                        raise ValueError('Telemetry file rotated or replaced; start a new stream')
                    identities[service] = identity
                elif service in identities:
                    raise ValueError('Previously observed telemetry file disappeared')
            collector = restore_collector(directory, json.loads(row[3]) if row else None)
            # No in-memory state survives a failed transaction, including failed parsing.
            events = collector.read_window(start,end)
            prediction = score(aggregate(events,start,end),bundle)
            incident, transition = incident_transition(json.loads(row[4]) if row else None, prediction)
            prediction.update(stream=stream, checkpoint_sha256=checkpoint,
                collector_audit=collector.audit(), incident=dict(**incident, transition=transition),
                decision_completed_at=time.time(), raw_ingestion_persisted=True,
                deployment_validated=False)
            db.execute('INSERT OR REPLACE INTO observers VALUES (?,?,?,?,?,?,?)',
                (stream,str(directory),checkpoint,end,json.dumps(collector_state(collector)),
                 json.dumps(incident),json.dumps(identities)))
            db.execute('INSERT INTO native_predictions VALUES (?,?,?)',
                (stream,end,json.dumps(prediction)))
            return prediction


def status(database=DATABASE, stream=None):
    database = Path(database)
    if not database.exists():
        return dict(streams=[], predictions=[])
    # Read-only API access must not initialize or change storage.
    with closing(sqlite3.connect(database.resolve().as_uri()+'?mode=ro', uri=True)) as db:
        stream_rows = db.execute('SELECT stream,end,incident FROM observers ORDER BY end DESC LIMIT 100') if stream is None else db.execute(
            'SELECT stream,end,incident FROM observers WHERE stream=?', (stream,))
        streams = [dict(stream=row[0], end=row[1], incident=json.loads(row[2]),
                        observation_age_seconds=max(0,time.time()-row[1])) for row in stream_rows]
        predictions = [] if stream is None else [json.loads(row[0]) for row in db.execute(
            'SELECT prediction FROM native_predictions WHERE stream=? ORDER BY end DESC LIMIT 100', (stream,))]
    return dict(streams=streams, predictions=predictions)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--run-id', required=True, help='Completed calibrated native model run')
    parser.add_argument('--source-directory', type=Path, required=True)
    parser.add_argument('--stream', required=True)
    parser.add_argument('--windows', type=int, default=200, help='Bounded window count; 200 is ten minutes')
    parser.add_argument('--database', type=Path, default=DATABASE)
    args=parser.parse_args()
    if not 1<=args.windows<=10000:
        parser.error('Use 1–10000 windows')
    bundle,digest=native_bundle(args.run_id)
    observer=NativeObserver(args.database)
    previous=next((s for s in status(args.database)['streams'] if s['stream']==args.stream), None)
    # Fresh streams begin at the next epoch-aligned boundary. Resuming does not drop a gap.
    start=previous['end'] if previous else math.ceil(time.time()/3)*3
    for _ in range(args.windows):
        end=start+3
        while time.time()<end:
            time.sleep(max(0,min(.2,end-time.time())))
        value=observer.observe(args.stream,args.source_directory,start,end,bundle,digest)
        print(json.dumps(dict(stream=args.stream,end=end,operational_alert=value['operational_alert'],
            ml_alert=value['ml_alert'],incident=value['incident'],collector=value['collector_audit'])),flush=True)
        start=end


if __name__=='__main__': main()
