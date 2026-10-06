import unittest
from datetime import datetime,timezone
from incidentlab.external_evaluation import case_start,run_key


class ExternalProtocolTests(unittest.TestCase):
    def test_case_time_parsing_is_explicit_utc(self):
        expected=datetime(2025,11,3,14,9,39,tzinfo=timezone.utc).timestamp()
        self.assertEqual(case_start('Lv_P_CPU_preserve_20251103T140939Z_em'),expected)
        self.assertEqual(case_start('Perf_CPU_Contention_20251103_140939'),expected)
        with self.assertRaises(ValueError):case_start('case_without_time')

    def test_run_matching_does_not_include_collector_suffix(self):
        self.assertEqual(run_key('SN_data','Code_Stop_MediaService_20251104_024819_metrics_2025-11-04_03-21-39'),
                         'Code_Stop_MediaService_20251104_024819')
        self.assertEqual(run_key('TT_data','example_em'),'example_em')
