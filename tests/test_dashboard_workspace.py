"""Workspace boundary checks and independent agreement with recorded evaluations."""
import json
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from incidentlab.research_server import app
from incidentlab.dashboard_api import ROOT


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_cluster_health_is_scoped_read_only_and_cached(self):
        from types import SimpleNamespace
        pods={'items':[{'metadata':{'name':s+'-pod','labels':{'app.kubernetes.io/name':s}},
          'spec':{'nodeName':'incidentlab-control-plane'},
          'status':{'phase':'Running','containerStatuses':[{'ready':True,'restartCount':0}]}}
          for s in ('frontend','checkout','inventory')]}
        with patch('incidentlab.dashboard_api.cluster_health_cache',{}),patch('incidentlab.dashboard_api.shutil.which',return_value='kubectl'),patch('incidentlab.dashboard_api.subprocess.run',return_value=SimpleNamespace(returncode=0,stdout=json.dumps(pods).encode())) as run:
            self.assertEqual(self.client.get('/api/workspace/cluster-health').json()['status'],'ready')
            self.client.get('/api/workspace/cluster-health')
            run.assert_called_once()
            args=run.call_args.args[0]
            self.assertIn('kind-incidentlab',args)
            self.assertIn('incidentlab-testbed',args)
            self.assertIn('get',args)
            self.assertNotIn('exec',args)

    def test_saved_evidence_and_downloads(self):
        self.assertEqual(self.client.get('/').status_code,200)
        self.assertIn('Start here',self.client.get('/').text)
        self.assertEqual(self.client.get('/research').status_code,200)
        state=self.client.get('/api/workspace').json()
        self.assertEqual(state['cluster']['status'],'complete')
        self.assertFalse(state['llm_enabled'])
        self.assertEqual(len(state['figures']['figures']),10)
        phase=self.client.get('/api/workspace/cluster/test_error_checkout').json()
        self.assertTrue(any(p['operational_alert'] for p in phase['predictions']))
        self.assertEqual(self.client.get('/api/workspace/figures/report-figures.zip').status_code,200)

    def test_action_and_path_boundaries(self):
        with patch('incidentlab.dashboard_api.subprocess.Popen') as launch:
            self.assertEqual(self.client.post('/api/workspace/demo',json={'scenario':'retrain'}).status_code,422)
            self.assertEqual(self.client.post('/api/workspace/demo',json={'scenario':'healthy','command':'anything'}).status_code,422)
            self.assertEqual(self.client.post('/api/workspace/demo',json={'scenario':'healthy'},headers={'Origin':'https://other.example'}).status_code,403)
            launch.assert_not_called()
        self.assertEqual(self.client.get('/api/workspace/cluster/unknown').status_code,404)
        self.assertEqual(self.client.get('/api/workspace/figures/handoff_manifest.json').status_code,404)

    def test_figure_counts_match_existing_metrics(self):
        figures=json.loads((ROOT/'artifacts/report_figures/index.json').read_text())
        for name,report,overall in [('research-gru-confusion','temporal_test_report.json','full'),
                                    ('research-if-confusion','full_test_report.json',None)]:
            saved=json.loads((ROOT/'artifacts/research'/report).read_text())
            expected=(saved[overall] if overall else saved)['overall']
            tn,fp=figures['metrics'][name]['matrix'][0]
            fn,tp=figures['metrics'][name]['matrix'][1]
            self.assertEqual(tn+fp+fn+tp,expected['windows'])
            self.assertAlmostEqual(tp/(tp+fp),expected['precision'])
            self.assertAlmostEqual(tp/(tp+fn),expected['recall'])


if __name__=='__main__':unittest.main()
