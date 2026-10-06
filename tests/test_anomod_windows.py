import unittest
import numpy as np
from incidentlab.anomod_healthy import parse_sn_line,sn_service
from incidentlab.anomod_windows import complete_bounds,reference,change


class AnoModWindowTests(unittest.TestCase):
    def test_complete_bounds_exclude_partial_minutes(self):
        self.assertEqual(complete_bounds([65,239]),(120,180))

    def test_multiline_timestamp_and_service_identity(self):
        self.assertIsNotNone(parse_sn_line('[2025-Nov-03 22:03:07.084255] <info>: started'))
        self.assertIsNone(parse_sn_line('  at package.Class.method(Class.java:10)'))
        self.assertEqual(sn_service('UserMentionService_'),'user-mention-service')
        self.assertEqual(sn_service('NginxThrift_'),'nginx-thrift')

    def test_missing_dimensions_stay_missing_without_nan_features(self):
        normal=np.array([[1,np.nan],[3,np.nan]])
        center,scale,count=reference(normal)
        self.assertEqual(count.tolist(),[2,0])
        self.assertTrue(np.isnan(center[1]))
        out=change(np.array([4,np.nan]),center,scale)
        self.assertEqual(out.tolist(),[2,0])
