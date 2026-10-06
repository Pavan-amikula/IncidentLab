import json
import tempfile
import time
import unittest
from pathlib import Path

import numpy as np
from incidentlab.native_observer import NativeObserver, status
from incidentlab.live_monitor import SERVICES, FEATURES


class ConstantScore:
    def score_samples(self, values): return np.full(len(values),-.5)


class DurableNativeChecks(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.directory=Path(self.temporary.name)/'source'; self.directory.mkdir()
        self.database=Path(self.temporary.name)/'observer.sqlite3'
        self.digest='a'*64
        self.bundle=dict(schema='incidentlab-http-v1',features=FEATURES,services={service:dict(
            model=ConstantScore(),center=np.zeros(4),scale=np.ones(4),threshold=.9,
            latency_limit=50,error_limit=.05) for service in SERVICES})
        self.base=time.time()-120

    def tearDown(self): self.temporary.cleanup()

    def event(self, service, end, error=False):
        return dict(schema='incidentlab-http-v1', service=service, trace_id='a'*32,
            span_id='b'*32, parent_span_id=None,start=end-.02,end=end,duration_ms=20,
            status=503 if error else 200,active_requests=1,message='local error' if error else 'complete',
            dependency=None,dependency_status=None)

    def append(self, end, error=False):
        for service in SERVICES:
            with (self.directory/f'{service}.jsonl').open('a') as output:
                output.write(json.dumps(self.event(service,end,error))+'\n')

    def observe(self, observer, number):
        return observer.observe('stream',self.directory,self.base+3*number,self.base+3*(number+1),self.bundle,self.digest)

    def test_restart_keeps_future_events_and_does_not_duplicate(self):
        self.append(self.base+1); self.append(self.base+4)
        first=self.observe(NativeObserver(self.database),0)
        self.assertEqual(first['collector_audit']['pending_records'],3)
        second=self.observe(NativeObserver(self.database),1)
        self.assertEqual(second['collector_audit']['records_read'],6)
        self.assertTrue(all(c['count']==1 for c in second['candidates']))
        self.assertEqual(len(status(self.database,'stream')['predictions']),2)

    def test_duplicate_gap_and_checkpoint_changes_leave_storage_unchanged(self):
        self.append(self.base+1); observer=NativeObserver(self.database)
        self.observe(observer,0)
        for number in (0,2):
            with self.assertRaises(ValueError): self.observe(observer,number)
        with self.assertRaises(ValueError):
            observer.observe('stream',self.directory,self.base+3,self.base+6,self.bundle,'different')
        self.assertEqual(len(status(self.database,'stream')['predictions']),1)

    def test_parse_failure_rolls_back_offsets_and_allows_corrected_retry(self):
        self.append(self.base+1); observer=NativeObserver(self.database)
        self.observe(observer,0)
        path=self.directory/'frontend.jsonl'; previous=path.read_text()
        path.write_text(previous+'malformed\n')
        with self.assertRaises(ValueError): self.observe(observer,1)
        self.assertEqual(len(status(self.database,'stream')['predictions']),1)
        path.write_text(previous+json.dumps(self.event('frontend',self.base+4))+'\n')
        result=self.observe(observer,1)
        self.assertEqual(result['collector_audit']['records_read'],4)

    def test_partial_record_survives_restart(self):
        raw=json.dumps(self.event('frontend',self.base+4)); path=self.directory/'frontend.jsonl'
        path.write_text(raw[:40]); self.observe(NativeObserver(self.database),0)
        with path.open('a') as output: output.write(raw[40:]+'\n')
        result=self.observe(NativeObserver(self.database),1)
        self.assertEqual(result['collector_audit']['records_read'],1)
        self.assertEqual(result['collector_audit']['partial_record_bytes'],0)

    def test_file_replacement_cannot_reuse_offsets(self):
        self.append(self.base+1); observer=NativeObserver(self.database); self.observe(observer,0)
        path=self.directory/'frontend.jsonl'
        replacement=self.directory/'replacement.jsonl'; replacement.write_text(path.read_text())
        replacement.replace(path)
        with self.assertRaises(ValueError): self.observe(observer,1)
        self.assertEqual(len(status(self.database,'stream')['predictions']),1)

    def test_two_warning_windows_open_one_incident_and_two_clear_close(self):
        observer=NativeObserver(self.database)
        for i in range(3):
            self.append(self.base+3*i+1,error=True); value=self.observe(observer,i)
        self.assertEqual(value['incident']['opened_incidents'],1)
        self.assertTrue(value['incident']['active'])
        for i in (3,4):
            self.append(self.base+3*i+1); value=self.observe(observer,i)
        self.assertEqual(value['incident']['closed_incidents'],1)
        self.assertFalse(value['incident']['active'])


if __name__=='__main__': unittest.main()
