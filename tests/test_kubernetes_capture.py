import json
import tempfile
import unittest
from pathlib import Path
from incidentlab.kubernetes_telemetry import PodEventStore,utc


def line(span='a'*32,end=100):
    event=dict(schema='incidentlab-http-v1',service='checkout',span_id=span,trace_id='b'*32,
        start=end-.02,end=end,duration_ms=20,status=200,active_requests=1,message='complete')
    return utc(end)+' '+json.dumps(event)


class ClusterCaptureChecks(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/'events.sqlite3'
    def tearDown(self):self.temp.cleanup()

    def test_reconnect_and_new_pod_do_not_duplicate_existing_span(self):
        store=PodEventStore(self.path);self.assertEqual(store.ingest('pod1','checkout',line()),1)
        store=PodEventStore(self.path)
        self.assertEqual(store.ingest('pod1','checkout',line()),0)
        self.assertEqual(store.ingest('pod2','checkout',line()+'\n'+line('c'*32,101)),1)
        self.assertEqual(len(store.window(99,102)),2)
        self.assertEqual(store.watermark('pod2'),101)

    def test_conflicting_duplicate_rolls_back_new_records_and_watermark(self):
        store=PodEventStore(self.path);store.ingest('pod','checkout',line())
        conflict=line().replace('complete','changed')
        with self.assertRaises(ValueError):store.ingest('pod','checkout',line('c'*32,101)+'\n'+conflict)
        self.assertEqual(len(store.window(99,102)),1)
        self.assertEqual(store.watermark('pod'),100)

    def test_future_events_and_wrong_service_do_not_leak_into_window(self):
        store=PodEventStore(self.path);store.ingest('pod','checkout',line()+'\n'+line('c'*32,110))
        self.assertEqual(len(store.window(99,103)),1)
        with self.assertRaises(ValueError):store.ingest('other','inventory',line())
        self.assertFalse(store.seen('other'))

    def test_untrusted_clock_or_malformed_record_does_not_advance_cursor(self):
        store=PodEventStore(self.path)
        for text in (utc(200)+' '+line().split(' ',1)[1],line()+'\nmalformed'):
            with self.assertRaises((ValueError,TypeError)):store.ingest('pod','checkout',text)
        self.assertFalse(store.seen('pod'))

    def test_late_transport_arrival_is_excluded_from_earlier_decision_replay(self):
        store=PodEventStore(self.path);store.ingest('pod','checkout',line(),captured=105)
        self.assertEqual(store.window(99,103,as_of=104),[])
        self.assertEqual(len(store.window(99,103,as_of=106)),1)


if __name__=='__main__':unittest.main()
