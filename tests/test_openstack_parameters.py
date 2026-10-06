import unittest
import numpy as np

from incidentlab.openstack_parameters import duration_event, vector, robust_scores


class LifecycleParameterTests(unittest.TestCase):
    def line(self, duration='31.27', instance='1643649d-2f42-4303-bfcd-7798baec19f9'):
        return ('nova-compute 2017-05-14 12:34:56.789 42 INFO nova.compute.manager '
                f'[instance: {instance}] Took {duration} seconds to build instance.')

    def test_numeric_parameter_retained_without_annotation(self):
        event = duration_event(self.line(), 23)
        self.assertEqual(event['duration_seconds'], 31.27)
        self.assertEqual(event['line_number'], 23)
        self.assertNotIn('label', event)

    def test_no_instance_is_not_assigned_by_guess(self):
        self.assertIsNone(duration_event(self.line().replace('[instance: 1643649d-2f42-4303-bfcd-7798baec19f9]', ''), 1))

    def test_missing_is_not_zero_and_duplicate_uses_measured_maximum(self):
        events = [duration_event(self.line(value), 1) for value in ('2.00','31.27')]
        values = vector(events)
        self.assertEqual(values[1],31.27)
        self.assertTrue(np.isnan(values[0]))

    def test_missing_parameters_do_not_create_anomaly_and_empty_abstains(self):
        scores=robust_scores(np.array([[np.nan,2,3,4],[np.nan]*4]), np.array([1,2,3,4]), np.ones(4))
        self.assertEqual(scores[0],0)
        self.assertTrue(np.isnan(scores[1]))


if __name__ == '__main__': unittest.main()
