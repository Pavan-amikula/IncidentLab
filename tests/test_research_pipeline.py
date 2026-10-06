import unittest
import numpy as np
from incidentlab.research_pipeline import causal_change, splits, FEATURES


class ResearchPipelineTests(unittest.TestCase):
    def test_future_observations_cannot_change_earlier_features(self):
        data = np.arange(40, dtype=float).reshape(20, 2)
        original = causal_change(data)
        changed = data.copy()
        changed[15:] = 1e12
        np.testing.assert_allclose(original[:15], causal_change(changed)[:15])

    def test_whole_cases_assigned_once_and_input_order_irrelevant(self):
        cases = [dict(case=f'run-{i}', dataset='suite-a') for i in range(30)]
        assignment = splits(cases)
        self.assertEqual(assignment, splits(list(reversed(cases))))
        self.assertEqual(len(assignment), 30)
        self.assertEqual([sum(v == split for v in assignment.values())
                          for split in ['train', 'validation', 'test']], [18, 6, 6])

    def test_features_exclude_ground_truth_and_case_identity(self):
        for forbidden in ['case', 'fault', 'inject_time', 'root_cause_service']:
            self.assertNotIn(forbidden, FEATURES)
        self.assertEqual(len(FEATURES), 11)


if __name__ == '__main__':
    unittest.main()
