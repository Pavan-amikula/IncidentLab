import unittest
from sklearn.feature_extraction.text import TfidfVectorizer
from incidentlab.log_content import template,instrumentation,analyze


class LogContentTests(unittest.TestCase):
    def test_variable_ids_do_not_become_spurious_novelty(self):
        self.assertEqual(template('[2025-Nov-03 10:00:00] request id=123 completed'),
                         template('[2026-Jan-01 11:00:00] request id=456 completed'))
        self.assertNotEqual(template('connection refused'),template('connection established'))

    def test_benchmark_markers_are_not_fault_evidence(self):
        self.assertTrue(instrumentation('CHAOS_EXCEPTION_INJECTION'))
        self.assertFalse(instrumentation('database connection refused'))

    def test_persistence_resets_after_normal_window(self):
        vectorizer=TfidfVectorizer();prototypes=vectorizer.fit_transform(['normal request'])
        bundle=dict(vectorizer=vectorizer,prototypes=prototypes,event_novelty_threshold=.05,
                    window_novel_fraction=.1,minimum_events=20,consecutive_alert_minutes=2)
        rows=[dict(service='a',timestamp=w*60+1,message='database refused' if w in [0,1,3] else 'normal request')
              for w in range(4) for _ in range(20)]
        findings,_=analyze(bundle,rows,0,240)
        self.assertEqual(len(findings),1)
        self.assertEqual(findings[0]['end'],120)
        self.assertEqual(findings[0]['evidence'][0]['message'],'database refused')
