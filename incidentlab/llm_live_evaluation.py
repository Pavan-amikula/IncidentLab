"""Compare local log-only and hybrid LLM outputs on frozen collected live trials."""
import json
import argparse
import time
import hashlib

import numpy as np

from .evidence_diagnosis import diagnose, model
from .native_experiment import OUT, save


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run-id', help='Choose a completed immutable native run instead of latest')
    parser.add_argument('--sample-windows', type=int, default=8)
    parser.add_argument('--policy-version', choices=('v1','v2'), default='v1')
    args = parser.parse_args()
    if not 1 <= args.sample_windows <= 40:
        parser.error('Use between 1 and 40 uniformly spaced windows')
    if args.run_id:
        import re
        if not re.fullmatch(r'\d{8}T\d{6}-[0-9a-f]{6}', args.run_id):
            parser.error('Invalid native run ID')
        report = json.loads((OUT/args.run_id/'report.json').read_text())
    else:
        report = json.loads((OUT/'latest_report.json').read_text())
    directory = OUT/report['run_id']
    candidate_path = directory/'diagnosis_candidate_v2/manifest.json'
    candidate = json.loads(candidate_path.read_text()) if args.policy_version=='v2' and candidate_path.exists() else None
    if candidate:
        from .native_experiment import ROOT
        if candidate['run_id']!=report['run_id'] or any(
            hashlib.sha256((ROOT/'incidentlab'/name).read_bytes()).hexdigest()!=digest
            for name,digest in candidate['code_sha256'].items()):
            raise ValueError('Implementation changed after candidate freeze')
        schedules=[json.loads((directory/(t.get('phase') or 'test_'+t['kind'])/'schedule.json').read_text()) for t in report['trials'] if t['target'] is not None]
        if any(candidate['created_epoch']>=s['onset'] for s in schedules):
            raise ValueError('Candidate was not frozen before recorded fault onsets')
    engine = model()
    results = []
    started = time.perf_counter()
    # Uniformly spaced complete windows. Sampling is not based on faults or detector alerts.
    for trial in report['trials']:
        kind = trial['kind']
        phase = trial.get('phase') or 'test_'+kind
        predictions = json.loads((directory/phase/'predictions.json').read_text())
        indices = sorted(set(np.linspace(0, len(predictions)-1, args.sample_windows, dtype=int).tolist()))
        generated = []
        for index in indices:
            prediction = predictions[index]
            for mode in ('logs_only', 'hybrid'):
                diagnosis = diagnose(prediction, mode, engine, policy_version=args.policy_version)
                generated.append(dict(window=index, start=prediction['start'], end=prediction['end'], **diagnosis))
        version = engine.role+('_v2' if args.policy_version=='v2' else '')
        save(directory/phase/f'llm_diagnoses_{version}.json', generated)
        schedule = json.loads((directory/phase/'schedule.json').read_text())
        onset, recovery = schedule['onset'], schedule['recovery']
        for mode in ('logs_only', 'hybrid'):
            values = [r for r in generated if r['mode'] == mode]
            # Exclude transition windows; independently recorded control timings used only here.
            healthy = [r for r in values if onset is None or r['end'] <= onset or r['start'] >= recovery]
            faulty = [r for r in values if onset is not None and r['start'] >= onset and r['end'] <= recovery]
            results.append(dict(trial=phase.removeprefix('test_'), target=trial.get('target'),
                mode=mode, evaluated_windows=len(values),
                structural_acceptance=sum(r['structurally_valid'] for r in values)/len(values),
                policy_acceptance=sum(r['accepted'] for r in values)/len(values),
                abstention_rate=sum(r['status']=='abstain' for r in values)/len(values),
                healthy_review_fraction=sum(r['status']=='review' for r in healthy)/len(healthy) if healthy else None,
                fault_review_fraction=sum(r['status']=='review' for r in faulty)/len(faulty) if faulty else None,
                fault_service_hypothesis_fraction=sum(r['suspected_service']==schedule.get('target') and r['status']=='review' for r in faulty)/len(faulty) if faulty else None,
                latency_p95_ms=float(np.quantile([r['latency_ms'] for r in values], .95)),
                input_tokens=sum(r['token_usage']['input_tokens'] for r in values),
                output_tokens=sum(r['token_usage']['output_tokens'] for r in values)))
        print(f'Local LLM comparisons complete: {kind}', flush=True)
    summary = dict(run_id=report['run_id'], model_id=engine.model_id, revision=engine.revision, results=results,
        policy_version=args.policy_version,
        candidate_freeze=candidate,
        evaluation_stage='fresh known-fault trials after candidate freeze' if candidate else 'development on previously inspected trials',
        prompt_sha256=generated[0]['prompt_sha256'],
        sample=f'{args.sample_windows} uniformly spaced completed windows per trial, chosen without fault labels or detector scores',
        training='Frozen pretrained weights; zero-shot prompt; no learning on fault outcomes',
        comparison=('Log-only bounded HTTP event records versus the same records plus measured warnings, aggregate measurement citations and trace-derived investigation hints'
                    if args.policy_version=='v2' else 'Log-only bounded HTTP event records versus the same records plus measured warnings'),
        seconds=time.perf_counter()-started, limitations=[
            'Structural citation validity does not prove semantic support',
            'Small zero-shot model and short controlled application; no production or cross-system claim',
            'Sampled-window rates are not full-stream false alerts/hour or incident recall',
            'Known fault families on one controlled application; no production or unseen-system claim',
            'Logs include duration/status of actual requests; log-only is not plain message-text-only'])
    save(directory/f'llm_report_{version}.json', summary)
    save(OUT/'latest_llm_report.json', summary)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == '__main__':
    run()
