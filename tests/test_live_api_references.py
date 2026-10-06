import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from incidentlab import live_api


class LiveReferenceChecks(unittest.TestCase):
    def test_clipped_history_preserves_absolute_prediction_reference(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary);run=root/'20261005T200503-c9862c';phase=run/'test_healthy';phase.mkdir(parents=True)
            (root/'progress.json').write_text(json.dumps(dict(run_id=run.name)))
            (phase/'windows.json').write_text('[]')
            (phase/'predictions.json').write_text(json.dumps([dict(index=i) for i in range(200)]))
            with patch.object(live_api,'OUT',root):
                response=live_api.live_trial('test_healthy')
                self.assertEqual(response['prediction_offset'],100)
                self.assertEqual(response['predictions'][-1]['index'],199)
                self.assertEqual(response['prediction_offset']+len(response['predictions'])-1,199)


if __name__=='__main__':unittest.main()
