"""Meaningful isolation, leakage, boundary and citation checks for the native pipeline."""
import json
import unittest

from incidentlab.evidence_diagnosis import context, diagnose
from incidentlab.native_experiment import evaluate


def prediction():
    return dict(start=10, end=13, candidates=[dict(service='checkout', count=10,
        features=[30, 1, 3.3, 1], reasons=['HTTP errors'],
        evidence=[dict(span_id='span-real', trace_id='trace-real', message='downstream failed',
            status=502, duration_ms=30, dependency='inventory', dependency_status=0)],
        root_cause='SECRET_EVALUATION_LABEL')],
        root_cause='SECRET_EVALUATION_LABEL', ml_alert=True, operational_alert=True)


class Generator:
    def __init__(self, output): self.output = output
    def generate(self, *args, **kwargs):
        return json.dumps(self.output), dict(input_tokens=1, output_tokens=1)


class NativeEvidenceChecks(unittest.TestCase):
    def test_evaluation_fields_never_enter_generation_context(self):
        for mode in ('logs_only', 'hybrid'):
            payload, evidence, _, _ = context(prediction(), mode)
            self.assertNotIn('SECRET_EVALUATION_LABEL', json.dumps(payload))
            self.assertNotIn('SECRET_EVALUATION_LABEL', json.dumps(evidence))
            self.assertNotIn('root_cause', json.dumps(payload))

    def test_unknown_evidence_abstains_without_invented_citation(self):
        output = dict(status='review', suspected_service='inventory', evidence_ids=['E999'],
                      runbook_id='dependency', summary='Inspect dependency')
        result = diagnose(prediction(), engine=Generator(output))
        self.assertEqual(result['status'], 'abstain')
        self.assertFalse(result['structurally_valid'])
        self.assertEqual(result['cited_evidence'], {})

    def test_unknown_action_and_service_are_rejected(self):
        for values in ({'suspected_service': 'invented-service'}, {'runbook_id': 'delete_database'}):
            output = dict(status='review', suspected_service='inventory', evidence_ids=['E1'],
                          runbook_id='dependency', summary='Inspect dependency')
            output.update(values)
            self.assertEqual(diagnose(prediction(), engine=Generator(output))['status'], 'abstain')

    def test_valid_citation_resolves_to_original_trace(self):
        output = dict(status='review', suspected_service='inventory', evidence_ids=['E1'],
                      runbook_id='dependency', summary='Inspect the failed inventory dependency')
        result = diagnose(prediction(), engine=Generator(output))
        self.assertTrue(result['structurally_valid'])
        self.assertEqual(result['cited_evidence']['E1']['span_id'], 'span-real')
        self.assertFalse(result['semantic_support_verified'])

    def test_clear_language_cannot_override_measured_warning(self):
        output = dict(status='clear', suspected_service=None, evidence_ids=[],
                      runbook_id='none', summary='Everything is fine')
        result = diagnose(prediction(), engine=Generator(output))
        self.assertEqual(result['status'], 'abstain')
        self.assertTrue(result['structurally_valid'])
        self.assertFalse(result['accepted'])

    def test_citation_must_refer_to_hypothesized_service(self):
        value = prediction()
        value['candidates'].append(dict(service='frontend', count=0, features=[0]*4, reasons=[], evidence=[]))
        output = dict(status='review', suspected_service='frontend', evidence_ids=['E1'],
                      runbook_id='dependency', summary='Inspect frontend')
        result = diagnose(value, engine=Generator(output))
        self.assertEqual(result['status'], 'abstain')
        self.assertFalse(result['accepted'])

    def test_fault_transition_windows_are_not_mislabeled(self):
        windows = [dict(start=i, end=i+3, ml_alert=True, operational_alert=True) for i in (0, 3, 6, 9)]
        result = evaluate(windows, dict(onset=4, recovery=10, kind='error', dropped=0))
        self.assertEqual(result['healthy_windows'], 1)
        self.assertEqual(result['active_fault_windows'], 1)
        self.assertEqual(result['boundary_windows_excluded'], 2)

    def test_v2_measurement_citation_resolves_to_actual_window_not_fake_span(self):
        payload,evidence,_,_=context(prediction(),'hybrid','v2')
        self.assertEqual(evidence['M1']['requests'],10)
        self.assertEqual(evidence['M1']['start'],10)
        self.assertNotIn('span_id',evidence['M1'])
        self.assertNotIn('SECRET_EVALUATION_LABEL',json.dumps(payload))
        output=dict(status='review',suspected_service='checkout',evidence_ids=['M1'],
                    runbook_id='dependency',summary='Inspect the measured error fraction')
        self.assertTrue(diagnose(prediction(),engine=Generator(output),policy_version='v2')['accepted'])

    def test_v2_global_absence_cannot_name_a_service_failure(self):
        value=prediction(); value['candidates'][0].update(count=0,features=[0]*4,evidence=[],reasons=['no requests'])
        output=dict(status='review',suspected_service='checkout',evidence_ids=['M1'],
                    runbook_id='coverage',summary='Checkout failed')
        result=diagnose(value,engine=Generator(output),policy_version='v2')
        self.assertEqual(result['status'],'abstain')
        self.assertFalse(result['accepted'])

    def test_v2_log_only_does_not_receive_metric_hints(self):
        payload,evidence,_,_=context(prediction(),'logs_only','v2')
        self.assertNotIn('measured_windows',payload)
        self.assertNotIn('observation_assessment',payload)
        self.assertNotIn('M1',evidence)


if __name__ == '__main__': unittest.main()
