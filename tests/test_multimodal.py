import unittest
import numpy as np
import pyarrow as pa
import torch
from incidentlab.trace_features import aggregate_trace
from incidentlab.temporal_model import TemporalFusion


class MultimodalTests(unittest.TestCase):
    def test_null_trace_status_is_unknown_not_error(self):
        batch = pa.record_batch({'serviceName':['a','a','b'], 'startTimeMillis':[100000,101000,161000],
                                 'duration':[10,20,30], 'statusCode':[None,0,500]})
        names, counts, _, _, unusual, known, ignored = aggregate_trace(batch,100,2)
        a,b=names.index('a'),names.index('b')
        self.assertEqual(counts[a,0],2)
        self.assertEqual(known[a,0],1)
        self.assertEqual(unusual[a,0],0)
        self.assertEqual(unusual[b,1],1)
        self.assertEqual(ignored,0)

    def test_padded_services_cannot_change_real_prediction(self):
        torch.manual_seed(3)
        model=TemporalFusion().eval()
        x=torch.ones(1,2,5,18);x[...,17]=0
        mask=torch.tensor([[True,False]])
        a,r=model(x,mask)
        x[:,1]=100
        b,s=model(x,mask)
        torch.testing.assert_close(a,b)
        torch.testing.assert_close(r[:,0],s[:,0])

    def test_removed_trace_values_cannot_affect_prediction(self):
        model=TemporalFusion().eval()
        x=torch.ones(1,2,5,18);x[...,17]=0
        mask=torch.ones(1,2,dtype=torch.bool)
        a,_=model(x,mask,drop=2)
        x[...,11:17]=100
        b,_=model(x,mask,drop=2)
        torch.testing.assert_close(a,b)

    def test_all_missing_sources_produce_abstention(self):
        model=TemporalFusion().eval()
        x=torch.zeros(1,2,5,18);x[...,17]=1
        detect,rank=model(x,torch.ones(1,2,dtype=torch.bool))
        self.assertLess(detect.item(),-9999)
        self.assertTrue((rank < -9999).all())

    def test_service_order_cannot_encode_root_identity(self):
        model=TemporalFusion().eval()
        x=torch.rand(1,3,5,18);x[...,17]=0
        mask=torch.ones(1,3,dtype=torch.bool)
        a,r=model(x,mask)
        permutation=torch.tensor([2,0,1])
        b,s=model(x[:,permutation],mask[:,permutation])
        torch.testing.assert_close(a,b)
        torch.testing.assert_close(r[:,permutation],s)


if __name__=='__main__':
    unittest.main()
