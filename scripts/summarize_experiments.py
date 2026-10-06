"""Expose completed stages and preserve a machine-readable comparison."""
import json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/research'

def read(name):
    return json.loads((OUT/name).read_text())

baseline=read('full_test_report.json')
reference=read('supervised_reference_report.json')['development_test']
temporal=read('temporal_test_report.json')
summary={'protocol':'development comparison; AnoMod external final untouched',
         'baseline':{'metrics':baseline['overall'],'incident_recall':baseline['incident_recall'],
                     'top1':baseline['ranking_at_first_alert']['top1'],'supervision':'healthy only','sources':'metrics/logs'},
         'supervised_reference':{'metrics':reference['overall'],'incident_recall':reference['incident_recall'],
                     'top1':reference['top1_at_first_alert'],'supervision':'fault and root-cause labels','sources':'metrics/logs/traces'},
         'temporal':{'metrics':temporal['full']['overall'],'incident_recall':temporal['full']['incident_recall'],
                     'top1':temporal['full']['top1_at_first_alert'],'supervision':'fault and root-cause labels','sources':'metrics/logs/traces'},
         'missing_logs':temporal['missing_logs'],'missing_traces':temporal['missing_traces']}
(OUT/'model_comparison.json').write_text(json.dumps(summary,indent=2))
print(json.dumps(summary,indent=2))
