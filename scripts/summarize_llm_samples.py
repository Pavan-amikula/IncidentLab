"""Aggregate archived generations; evaluation schedules never enter generation."""
import argparse
import json
import re

from incidentlab.native_experiment import OUT,save


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True)
    parser.add_argument('--policy-version',choices=('v1','v2'),default='v2')
    parser.add_argument('--role',choices=('llm','llm_medium'),default='llm_medium')
    args=parser.parse_args()
    if not re.fullmatch(r'\d{8}T\d{6}-[0-9a-f]{6}',args.run_id):parser.error('Invalid run ID')
    directory=OUT/args.run_id
    version=args.role+('_v2' if args.policy_version=='v2' else '')
    report=json.loads((directory/f'llm_report_{version}.json').read_text())
    native=json.loads((directory/'report.json').read_text())
    buckets={mode:dict(rows=[],healthy=[],fault=[]) for mode in ('logs_only','hybrid')}
    for trial in native['trials']:
        path=directory/(trial.get('phase') or 'test_'+trial['kind'])
        schedule=json.loads((path/'schedule.json').read_text())
        predictions=json.loads((path/'predictions.json').read_text())
        for row in json.loads((path/f'llm_diagnoses_{version}.json').read_text()):
            prediction=predictions[row['window']]
            assert row['start']==prediction['start'] and row['end']==prediction['end']
            assert row['policy_version']==args.policy_version and row['prompt_sha256']==report['prompt_sha256']
            bucket=buckets[row['mode']];bucket['rows'].append(row)
            if schedule['onset'] is None or row['end']<=schedule['onset'] or row['start']>=schedule['recovery']:
                bucket['healthy'].append(row)
            elif row['start']>=schedule['onset'] and row['end']<=schedule['recovery']:
                bucket['fault'].append(dict(row,target=schedule['target']))
    modes={}
    for mode,bucket in buckets.items():
        rows,healthy,fault=bucket['rows'],bucket['healthy'],bucket['fault']
        modes[mode]=dict(generations=len(rows),structurally_valid=sum(r['structurally_valid'] for r in rows),
            policy_accepted=sum(r['accepted'] for r in rows),healthy_samples=len(healthy),
            healthy_reviews=sum(r['status']=='review' for r in healthy),fault_samples=len(fault),
            fault_reviews=sum(r['status']=='review' for r in fault),
            fault_target_reviews=sum(r['status']=='review' and r['suspected_service']==r['target'] for r in fault),
            fault_abstentions=sum(r['status']=='abstain' for r in fault))
    result=dict(run_id=args.run_id,role=args.role,policy_version=args.policy_version,
        stage=report['evaluation_stage'],seconds=report['seconds'],modes=modes,
        scope='Uniform sampled complete windows; neither incident recall nor semantic accuracy')
    save(directory/f'llm_sample_summary_{version}.json',result)
    save(directory/'llm_sample_summary.json',result)
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
