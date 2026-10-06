import tempfile
import unittest
from pathlib import Path

import numpy as np
from pydantic import ValidationError

from incidentlab.parameter_serving import ParameterBatch,ParameterStore,ParameterEvent
from incidentlab.openstack_parameters import OPERATIONS,SCHEMA


class ConstantScore:
    def score_samples(self,values): return np.full(len(values),-.5)


def event(number,operation=OPERATIONS[0],duration=20):
    return dict(instance='1643649d-2f42-4303-bfcd-7798baec19f9',operation=operation,
        duration_seconds=duration,line_number=number,observed_timestamp='2017-05-14 12:34:56.789')


class ParameterServingChecks(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.path=Path(self.temporary.name)/'parameters.sqlite3'
        self.model=dict(center=np.array([20,21,1,.5]),scale=np.ones(4),model=ConstantScore(),
                        thresholds=dict(parameter_residual=5,parameter_isolation_forest=.8))

    def tearDown(self):self.temporary.cleanup()

    def batch(self,events): return ParameterBatch(stream='test',feature_schema=SCHEMA,events=events)

    def test_future_events_in_same_batch_do_not_change_earlier_scores(self):
        values=ParameterStore(self.path).analyze(self.batch([event(1),event(2,OPERATIONS[1],50)]),self.model,'a'*64)
        self.assertEqual(values[0]['observed_operations'],1)
        self.assertIsNone(values[0]['parameters'][OPERATIONS[1]])
        self.assertFalse(values[0]['parameter_warning'])
        self.assertTrue(values[1]['parameter_warning'])
        self.assertIsNone(values[0]['ml_warning'])

    def test_restart_preserves_parameters_and_duplicate_rejection_is_atomic(self):
        store=ParameterStore(self.path);store.analyze(self.batch([event(1)]),self.model,'a'*64)
        with self.assertRaises(ValueError):
            store.analyze(self.batch([event(2),event(1)]),self.model,'a'*64)
        self.assertEqual(len(store.history('test')),1)
        values=ParameterStore(self.path).analyze(self.batch([event(2,OPERATIONS[1],21)]),self.model,'a'*64)
        self.assertEqual(values[0]['observed_operations'],2)

    def test_changing_calibration_requires_new_stream(self):
        store=ParameterStore(self.path);store.analyze(self.batch([event(1)]),self.model,'a'*64)
        with self.assertRaises(ValueError):store.analyze(self.batch([event(2)]),self.model,'b'*64)

    def test_rank_profile_preserves_prefix_and_missing_operation_correction(self):
        self.model.update(rank_references={operation:np.arange(400,dtype=float) for operation in OPERATIONS},alpha=.01)
        request=ParameterBatch(stream='test',feature_schema=SCHEMA,calibration_profile='v4',
            events=[event(1,duration=20),event(2,OPERATIONS[1],500)])
        values=ParameterStore(self.path).analyze(request,self.model,'a'*64)
        self.assertFalse(values[0]['parameter_warning'])
        self.assertTrue(values[1]['parameter_warning'])
        self.assertAlmostEqual(values[1]['combined_tail_pvalue'],4/401)
        self.assertIsNone(values[0]['operation_tail_pvalues'][OPERATIONS[1]])
        self.assertIsNone(values[1]['ml_warning'])

    def test_labels_nonfinite_values_and_invalid_dates_are_rejected(self):
        for change in ({'label':1},{'duration_seconds':float('nan')},{'observed_timestamp':'2017-02-31 12:00:00.000'}):
            value=event(1);value.update(change)
            with self.assertRaises(ValidationError):ParameterEvent.model_validate(value)


if __name__=='__main__':unittest.main()
