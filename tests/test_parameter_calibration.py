import unittest
import numpy as np

from incidentlab.parameter_calibration import tail_probabilities
from incidentlab.openstack_parameters import OPERATIONS


class TailCalibrationChecks(unittest.TestCase):
    def test_ties_conservative_and_values_beyond_support_never_zero(self):
        references={operation:np.array([1.]*100) for operation in OPERATIONS}
        p,combined=tail_probabilities(np.array([[1.]*4,[2.]*4]),references)
        self.assertTrue(np.all(p[0]==1))
        self.assertTrue(np.all(p[1]==1/101))
        self.assertEqual(combined[1],4/101)

    def test_missing_operations_do_not_reduce_four_operation_correction(self):
        references={operation:np.arange(100.) for operation in OPERATIONS}
        p,combined=tail_probabilities(np.array([[100,np.nan,np.nan,np.nan],[np.nan]*4]),references)
        self.assertEqual(combined[0],4/101)
        self.assertTrue(np.isnan(combined[1]))


if __name__=='__main__':unittest.main()
