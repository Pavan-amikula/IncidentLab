"""Evaluate grouping on saved warnings; schedules are used only after decisions."""
import argparse
import json

from incidentlab.native_experiment import OUT, save
from incidentlab.native_observer import incident_transition


def group(predictions):
    state, episodes = None, []
    for prediction in predictions:
        state,transition=incident_transition(state,prediction)
        if transition=='opened':
            episodes.append(dict(opened_at=state['opened_at'],
                first_warning_window_start=state['first_warning_at'],
                service_hypothesis=state['service_hypothesis'],closed_at=None))
        elif transition=='closed':
            episodes[-1]['closed_at']=state['closed_at']
    return episodes


def evaluate(predictions,schedule):
    episodes=group(predictions)
    onset,recovery=schedule['onset'],schedule['recovery']
    # Opening timestamps, not inferred log-line labels. Keep all warning windows
    # for grouping, including windows crossing a recorded control boundary.
    faulty=[e for e in episodes if onset is not None and onset<=e['opened_at']<=recovery]
    false=[e for e in episodes if e not in faulty]
    observed=sum(p['end']-p['start'] for p in predictions)
    healthy=observed-(recovery-onset if onset is not None else 0)
    return dict(phase=schedule.get('phase'),target=schedule.get('target'),
        episodes=episodes,opened_incidents=len(episodes),healthy_false_incidents=len(false),
        healthy_exposure_seconds=healthy,
        false_incidents_per_healthy_hour=len(false)/(healthy/3600) if healthy>0 else None,
        fault_incident_detected=bool(faulty) if onset is not None else None,
        fault_openings=len(faulty),detection_delay_seconds=faulty[0]['opened_at']-onset if faulty else None,
        first_hypothesis_matches_injected_target=faulty[0]['service_hypothesis']==schedule['target'] if faulty else None)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',required=True)
    args=parser.parse_args()
    import re
    if not re.fullmatch(r'\d{8}T\d{6}-[0-9a-f]{6}',args.run_id):
        parser.error('Invalid run ID')
    directory=OUT/args.run_id
    source=json.loads((directory/'report.json').read_text())
    trials=[]
    for trial in source['trials']:
        phase=trial['phase'] or 'test_'+trial['kind']
        predictions=json.loads((directory/phase/'predictions.json').read_text())
        schedule=json.loads((directory/phase/'schedule.json').read_text())
        schedule['phase']=phase
        trials.append(evaluate(predictions,schedule))
    faults=[t for t in trials if t['target'] is not None]
    report=dict(run_id=args.run_id,policy='Two consecutive operational-warning windows open; two clear windows close',
        decision_inputs='Operational warnings only; no schedules, injected targets or labels',trials=trials,
        detected_fault_trials=sum(bool(t['fault_incident_detected']) for t in faults),fault_trials=len(faults),
        healthy_false_incidents=sum(t['healthy_false_incidents'] for t in trials),
        healthy_exposure_seconds=sum(t['healthy_exposure_seconds'] for t in trials),
        limitations=['Grouping policy is a development design choice, not optimized on the current run',
            'Opening-time classification differs from fault-window recall; control boundaries are not used in grouping',
            'Short, correlated controlled trials do not establish production incident rate or reliability',
            'Service hypotheses are not proven causes; workload and collector absence can be confounded'])
    save(directory/'grouped_incident_report.json',report)
    print(json.dumps({k:v for k,v in report.items() if k!='trials'},indent=2))


if __name__=='__main__':main()
