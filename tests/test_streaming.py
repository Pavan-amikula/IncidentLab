import tempfile
import unittest
from pathlib import Path

from pydantic import ValidationError
from incidentlab.streaming import FeatureWindow, StreamStore
from incidentlab.temporal_model import TemporalFusion, DEVICE


def request(end=120, features=None, **extra):
    return FeatureWindow(stream='test', profile='ob', end=end, feature_schema='rcaeval-multimodal-v2',
                         services=[dict(service='checkout',features=features or [0]*18)], **extra)


class StreamingTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'stream.sqlite3'
        self.store=StreamStore(self.path)
        self.model=TemporalFusion().to(DEVICE).eval()
        self.checkpoint={'thresholds':{'ob':.5}}

    def tearDown(self):
        self.temp.cleanup()

    def test_labels_and_nonfinite_values_rejected(self):
        with self.assertRaises(ValidationError):
            request(root_cause='checkout')
        with self.assertRaises(ValidationError):
            request(features=[float('nan')]*18)

    def test_missing_telemetry_abstains_and_survives_restart(self):
        features=[0]*18;features[17]=1
        result=self.store.analyze(request(features=features),self.model,self.checkpoint)
        self.assertTrue(result['abstained'])
        self.assertFalse(result['alert'])
        self.assertEqual(StreamStore(self.path).history('test'),[result])

    def test_duplicate_and_gap_rejections_do_not_mutate_history(self):
        self.store.analyze(request(),self.model,self.checkpoint)
        for end in [120,60,240]:
            with self.assertRaises(ValueError):
                self.store.analyze(request(end),self.model,self.checkpoint)
        self.assertEqual(len(self.store.history('test')),1)
        result=self.store.analyze(request(180),self.model,self.checkpoint)
        self.assertEqual(result['history_windows'],2)
