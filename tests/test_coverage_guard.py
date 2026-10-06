import unittest
from incidentlab.coverage_guard import CoverageGuard,fit_inventory


class CoverageGuardTests(unittest.TestCase):
    def guard(self):
        return CoverageGuard(dict(expected_gap_minutes={s:2 for s in ['a','b','c','d','e']},peer_coverage_required=.8))

    def test_missing_expected_service_is_retained_with_evidence(self):
        guard=self.guard()
        self.assertEqual(guard.step(60,['b','c','d','e'])['issues'],[])
        issue=guard.step(120,['b','c','d','e'])['issues'][0]
        self.assertEqual(issue['service'],'a')
        self.assertEqual(issue['missing_minutes'],2)
        self.assertIn('scrape target',issue['action'])

    def test_global_collector_loss_abstains_not_service_failure(self):
        guard=self.guard()
        for end in [60,120,180]:
            result=guard.step(end,[])
            self.assertEqual(result['state'],'insufficient_telemetry')
            self.assertEqual(result['issues'],[])

    def test_recovery_clears_warning_and_invalid_time_does_not_mutate(self):
        guard=self.guard();guard.step(60,['b','c','d','e'])
        with self.assertRaises(ValueError):guard.step(180,['b','c','d','e'])
        result=guard.step(120,['a','b','c','d','e'])
        self.assertEqual(result['state'],'observed')

    def test_inventory_excludes_intermittent_services(self):
        rows=[]
        for w in range(5):
            for service in ['steady','intermittent']:
                features=[0]*18;features[17]=0 if service=='steady' or w==0 else 1
                rows.append(dict(service=service,window=w,features=features))
        bundle=fit_inventory(rows)
        self.assertEqual(bundle['expected_gap_minutes'],{'steady':2})
