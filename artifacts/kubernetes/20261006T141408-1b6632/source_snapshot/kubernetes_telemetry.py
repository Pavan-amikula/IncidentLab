"""Bounded, deduplicated pod-log capture for the owned kind testbed only."""
import json
import sqlite3
import subprocess
import time
from contextlib import closing
from datetime import datetime,timezone
from pathlib import Path

from .raw_telemetry import RequestEvent,SERVICES

CONTEXT='kind-incidentlab'
NAMESPACE='incidentlab-testbed'
OWNER='incidentlab-testbed'
MAX_BYTES=4*1024*1024


def utc(epoch):return datetime.fromtimestamp(epoch,timezone.utc).isoformat().replace('+00:00','Z')


class Kubectl:
    def run(self,*arguments):
        result=subprocess.run(['kubectl','--context',CONTEXT,'-n',NAMESPACE,*arguments],
            capture_output=True,timeout=30,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if result.returncode:raise RuntimeError('Scoped kubectl operation failed: '+arguments[0])
        if len(result.stdout)>=MAX_BYTES:raise ValueError('Pod/API capture limit reached; refusing truncated logs')
        return result.stdout.decode('utf-8')

    def verify_scope(self):
        namespace=json.loads(self.run('get','namespace',NAMESPACE,'-o','json'))
        if namespace['metadata'].get('labels',{}).get('app.kubernetes.io/part-of')!=OWNER:
            raise ValueError('Namespace is not the owned IncidentLab testbed')


class PodEventStore:
    def __init__(self,path):
        self.path=Path(path);self.path.parent.mkdir(parents=True,exist_ok=True)
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('CREATE TABLE IF NOT EXISTS events (service TEXT,span TEXT,end REAL,payload TEXT,captured REAL,PRIMARY KEY(service,span))')
            db.execute('CREATE INDEX IF NOT EXISTS events_end ON events(end)')
            db.execute('CREATE TABLE IF NOT EXISTS cursors (source TEXT PRIMARY KEY,watermark REAL)')
            db.execute('CREATE TABLE IF NOT EXISTS snapshots (observed REAL,payload TEXT)')

    def watermark(self,source):
        with closing(sqlite3.connect(self.path)) as db:
            row=db.execute('SELECT watermark FROM cursors WHERE source=?',(source,)).fetchone()
            return row[0] if row else None

    def seen(self,source):
        with closing(sqlite3.connect(self.path)) as db:
            return db.execute('SELECT 1 FROM cursors WHERE source=?',(source,)).fetchone() is not None

    def ingest(self,source,service,text,captured=None):
        captured=time.time() if captured is None else captured
        parsed=[]
        for line in text.splitlines():
            if not line:continue
            stamp,raw=line.split(' ',1)
            transport=datetime.fromisoformat(stamp.replace('Z','+00:00'))
            if transport.tzinfo is None:raise ValueError('Pod transport timestamp needs a timezone')
            event=RequestEvent.model_validate_json(raw).model_dump(by_alias=True)
            if event['service']!=service:raise ValueError('Pod service label and request event disagree')
            if abs(transport.timestamp()-event['end'])>30:
                raise ValueError('Event and pod-log clock differ by more than the capture budget')
            parsed.append((transport.timestamp(),event))
        with closing(sqlite3.connect(self.path,timeout=10)) as db,db:
            db.execute('BEGIN IMMEDIATE')
            if db.execute('SELECT COUNT(*) FROM events').fetchone()[0]+len(parsed)>200000:
                raise ValueError('Cluster event-store capacity reached')
            old=db.execute('SELECT watermark FROM cursors WHERE source=?',(source,)).fetchone()
            latest=old[0] if old else None
            inserted=0
            for timestamp,event in parsed:
                payload=json.dumps(event,sort_keys=True,separators=(',',':'))
                previous=db.execute('SELECT payload FROM events WHERE service=? AND span=?',
                    (service,event['span_id'])).fetchone()
                if previous and previous[0]!=payload:raise ValueError('Conflicting payload for an already captured span')
                if not previous:
                    db.execute('INSERT INTO events VALUES (?,?,?,?,?)',(service,event['span_id'],event['end'],payload,captured))
                    inserted+=1
                latest=max(timestamp,latest) if latest is not None else timestamp
            db.execute('INSERT OR REPLACE INTO cursors VALUES (?,?)',(source,latest))
            return inserted

    def window(self,start,end,as_of=None):
        if end<=start:raise ValueError('Invalid window')
        with closing(sqlite3.connect(self.path)) as db:
            return [json.loads(row[0]) for row in db.execute(
                'SELECT payload FROM events WHERE end>=? AND end<? AND captured<=? ORDER BY end,service,span',
                (start,end,time.time() if as_of is None else as_of))]

    def snapshot(self,observed,pods):
        with closing(sqlite3.connect(self.path)) as db,db:
            db.execute('INSERT INTO snapshots VALUES (?,?)',(observed,json.dumps(pods)))

    def export(self,directory):
        with closing(sqlite3.connect(self.path)) as db:
            for service in SERVICES:
                with (Path(directory)/f'{service}.jsonl').open('w',encoding='utf-8') as target:
                    for row in db.execute('SELECT payload FROM events WHERE service=? ORDER BY end,span',(service,)):
                        target.write(row[0]+'\n')
            return dict(events=db.execute('SELECT COUNT(*) FROM events').fetchone()[0],
                sources=db.execute('SELECT COUNT(*) FROM cursors').fetchone()[0],
                snapshot_count=db.execute('SELECT COUNT(*) FROM snapshots').fetchone()[0],
                storage='SQLite unique service/span IDs and transactional transport watermarks',
                limitation='Pod deletion/rotation between polls can lose tail records; snapshots expose lifecycle changes but cannot reconstruct missing logs')


class PodCapture:
    def __init__(self,store,since,kubectl=None):
        self.store,self.since,self.cli=store,since,kubectl or Kubectl()

    def poll(self,observed):
        pods=json.loads(self.cli.run('get','pods','-l','app.kubernetes.io/part-of='+OWNER,'-o','json'))['items']
        self.store.snapshot(observed,pods)
        inserted=0
        for pod in pods:
            meta=pod['metadata'];labels=meta.get('labels',{})
            service=labels.get('app.kubernetes.io/name')
            if labels.get('app.kubernetes.io/part-of')!=OWNER or service not in SERVICES:
                raise ValueError('Pod is not an allowed testbed service')
            for container in pod.get('status',{}).get('containerStatuses',[]):
                if container['name']!=service:raise ValueError('Unexpected container in testbed pod')
                current=container.get('containerID')
                if not current or 'running' not in container.get('state',{}):continue
                source=meta['uid']+'/'+current
                if container.get('restartCount',0)>0:
                    previous=meta['uid']+'/previous/'+str(container['restartCount'])
                    if not self.store.seen(previous):
                        text=self.cli.run('logs',meta['name'],'-c',service,'--previous','--timestamps=true',
                            '--since-time='+utc(self.since),'--limit-bytes='+str(MAX_BYTES))
                        inserted+=self.store.ingest(previous,service,text)
                watermark=self.store.watermark(source)
                since=max(self.since,(watermark-2) if watermark is not None else self.since)
                text=self.cli.run('logs',meta['name'],'-c',service,'--timestamps=true',
                    '--since-time='+utc(since),'--limit-bytes='+str(MAX_BYTES))
                inserted+=self.store.ingest(source,service,text)
        return inserted
