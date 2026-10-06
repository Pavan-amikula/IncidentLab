"""CPU serving/capture tests; optional transformer diagnosis tests remain on GPU PC."""
import json
import unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
modules=['tests.'+path.stem for path in sorted((ROOT/'tests').glob('test_*.py'))
         if path.stem!='test_live_monitor']
suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in modules)
result=unittest.TextTestRunner(verbosity=1).run(suite)
report=dict(status='passed' if result.wasSuccessful() else 'failed',tests=result.testsRun,
    errors=len(result.errors),failures=len(result.failures),
    excluded_module='test_live_monitor imports optional transformer diagnosis; covered in full GPU-PC suite')
print(json.dumps(report,indent=2))
raise SystemExit(0 if result.wasSuccessful() else 1)
