"""Regression checks for the final window journal and invalid duration handling."""
import json
import io
from contextlib import redirect_stderr
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from incidentlab import native_experiment as experiment


class NativeCompletionChecks(unittest.TestCase):
    def test_settled_final_window_is_in_both_canonical_file_and_journal(self):
        # No services or workload are created: simulate reaching the duration
        # boundary before the periodic loop can publish its final window.
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            with patch.object(experiment,'OUT',root), patch.object(experiment,'Testbed'), \
                    patch.object(experiment,'score',return_value=dict(start=100,end=103,candidates=[])), \
                    patch.object(experiment.time,'time',side_effect=[100,103]), \
                    patch.object(experiment.time,'monotonic',side_effect=[0,4]):
                _,predictions,_=experiment.collect(root/'run','test_healthy',3,3,'healthy',bundle={'frozen':True})
            path=root/'run/test_healthy'
            canonical=json.loads((path/'predictions.json').read_text())
            journal=[json.loads(line) for line in (path/'predictions.jsonl').read_text().splitlines()]
            self.assertEqual(len(predictions),1)
            self.assertEqual(journal,canonical)

    def test_explicit_zero_duration_rejected_before_service_launch(self):
        for option in ('--healthy-seconds','--control-seconds'):
            with patch('sys.argv',['native_experiment',option,'0']),patch.object(experiment,'collect') as collect,redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit) as error: experiment.main()
                self.assertEqual(error.exception.code,2)
                collect.assert_not_called()


if __name__=='__main__':unittest.main()
