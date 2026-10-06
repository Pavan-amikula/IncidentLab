import unittest
from incidentlab.anomod_adapter import normalize_tt_span,normalize_sn_span,counter_rate


class AnoModAdapterTests(unittest.TestCase):
    def test_tt_units_and_boolean_semantics(self):
        span=dict(duration_ms=3.5,is_error=True,service_code='checkout',node_id='a',start_timestamp_ms=1500)
        row=normalize_tt_span(span)
        self.assertEqual(row['duration_us'],3500)
        self.assertEqual(row['timestamp_epoch_seconds'],1.5)
        self.assertEqual(row['status_code'],500)
        span['is_error']='false'
        with self.assertRaises(ValueError):normalize_tt_span(span)

    def test_sn_naive_time_and_missing_status_not_fabricated(self):
        row=normalize_sn_span(dict(start_time='2025-11-03 22:03:07',duration_us='10',service='checkout',
            span_id='a',parent_span_id='',http_status_code=''))
        self.assertIsNone(row['timestamp_epoch_seconds'])
        self.assertIsNotNone(row['timestamp_local'])
        self.assertIsNone(row['status_code'])

    def test_counter_resets_and_out_of_order(self):
        self.assertEqual(counter_rate(10,100,20,130),3)
        self.assertIsNone(counter_rate(10,100,20,5))
        with self.assertRaises(ValueError):counter_rate(20,100,10,130)
