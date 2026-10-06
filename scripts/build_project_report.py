"""Generate a concise measured-results report from actual saved artifacts."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS = ROOT/'artifacts'


def read(path):
    return json.loads(path.read_text()) if path.exists() else None


def build():
    full = read(ARTIFACTS/'research/preprocessing_report.json')
    semantic = read(ARTIFACTS/'research/semantic_log_content_report.json')
    external = read(ARTIFACTS/'research/anomod_external_report.json')
    stack = read(ARTIFACTS/'research/openstack_full_v2_report.json')
    parameters = read(ARTIFACTS/'research/openstack_parameters_v3_report.json')
    ranks = read(ARTIFACTS/'research/openstack_parameters_v4_report.json')
    live = read(ARTIFACTS/'live/latest_report.json')
    llm = read(ARTIFACTS/'live/latest_llm_report.json')
    grouping = read(ARTIFACTS/f"live/{live['run_id']}/grouped_incident_report.json") if live else None
    integrity = read(ARTIFACTS/f"live/{live['run_id']}/integrity_report.json") if live else None
    serving = read(ARTIFACTS/'research/parameter_serving_verification_v4.json')
    observer = read(ARTIFACTS/'live/native_observer_verification.json')
    runtime = read(ARTIFACTS/'live_runtime/latest_report.json')
    sampled = read(ARTIFACTS/f"live/{llm['run_id']}/llm_sample_summary.json") if llm else None
    lines = ['# IncidentLab measured status', '',
        'Evidence-grounded cloud incident detection and investigation. Generated from saved reports; '
        'benchmarks and short local trials do not establish production reliability.', '',
        '## Implemented and executed', '',
        '- Complete source acquisition and hashes; whole-case research splits.',
        '- Healthy-only Isolation Forest, supervised boosting, CUDA temporal multimodal GRU.',
        '- Frozen AnoMod transfer check; coverage warnings and healthy-trained text novelty.',
        '- Frozen MiniLM semantic encoder and complete OpenStack VM-session comparisons.',
        '- Fresh HTTP services, workload, raw traces, fault/recovery schedule, online scoring and evidence API.',
        '- Local log-only/hybrid LLM comparisons; citation/schema validation and fixed runbook retrieval.', '',
        '## Full-data results', '']
    if full:
        lines.append(f"RCAEval: {full['cases']} eligible cases, {full['log_rows_scanned']:,} scanned log rows. Whole-case splits are retained.")
    if external:
        lines.append(f"AnoMod frozen transfer: {external['evaluated_runs']} fault runs; temporal alerted in {external['models']['temporal']['alerted_fault_runs']}, boosting in {external['models']['boosting']['alerted_fault_runs']}. This is poor run-alert coverage, not verified incident recall.")
    if semantic:
        lines.append(f"Semantic log check: {semantic['processed_events']:,} events; MiniLM {semantic['warning_service_windows']} versus TF-IDF {semantic['lexical_warning_service_windows']} warning service-minutes. No warning-count gain. {semantic['unique_templates_embedded']} distinct normalized texts embedded on {semantic['device']}.")
    if stack:
        count = sum(a['physical_lines'] for a in stack['audits'].values())
        lines += ['', f"OpenStack: all {count:,} lines scanned. {stack['train_sessions']} training and {stack['validation_sessions']} healthy calibration VM sessions; four author-annotated abnormal sessions.", '',
                  '| Method | Positive sessions detected | Precision | Recall |', '|---|---:|---:|---:|']
        for name, result in stack['results'].items():
            lines.append(f"| {name} | {result['annotated_positive_hits']}/{stack['annotated_positive_sessions']} | {result['precision']:.3f} | {result['recall']:.3f} |")
        lines += ['', 'Only explicitly instance-associated events form VM sessions. Unassigned records and identity exclusions are published. Labels are not per-line fault labels. The sequence addition used already-inspected development cases.']
    if parameters:
        lines += ['', '## Restored OpenStack numeric parameters (development)', '',
            'Text masking discarded measured lifecycle durations. A separate versioned adapter now preserves four operation durations in seconds. Training and calibration use the same healthy splits; the inspected anomaly labels remain development evidence.', '',
            '| Method | Annotated sessions detected | Precision | Healthy normal2 false alerts |',
            '|---|---:|---:|---:|']
        for name, result in parameters['results'].items():
            lines.append(f"| {name} | {result['annotated_positive_hits']}/{parameters['annotated_positive_sessions']} | {result['precision']:.3f} | {result['false_alerted_normal2_sessions']} |")
        lines += ['', 'Improved detection does not establish a reliable deployment model: the residual detector still raises many false alerts. Missing durations remain explicit, capture boundaries can censor sessions, and completion records do not establish early detection. See [primary-source failure analysis](openstack_failure_research.md).']
    if ranks:
        result=ranks['results']
        lines += ['', f"A subsequent operation-specific delay-rank development comparison at the existing nominal 1% budget detected {result['annotated_positive_hits']}/{result['annotated_positive_sessions']}, precision {result['precision']:.3f}, with {result['false_alerted_normal2_sessions']} healthy normal2 false alerts. It asks a one-sided delay question rather than two-sided novelty. The four-operation correction does not establish a guarantee under chronological/censored data. These are inspected development cases; see [calibration assumptions](parameter_calibration_research.md)."]
    if live:
        lines += ['', '## Latest completed live run', '', f"Run `{live['run_id']}`: {live['training_windows']} independent healthy training windows, {live['validation_windows']} separate healthy calibration windows. Checkpoint `{live['checkpoint_sha256']}`.", '',
                  '| Trial | ML fault-window recall | Operational recall | ML false windows/hour | Operational false windows/hour |', '|---|---:|---:|---:|---:|']
        for result in live['trials']:
            ml, op = result['ml_alert'], result['operational_alert']
            fmt = lambda value: '—' if value is None else f'{value:.3f}'
            lines.append(f"| {result.get('phase', result['kind'])} | {fmt(ml['fault_window_recall'])} | {fmt(op['fault_window_recall'])} | {fmt(ml['false_alert_windows_per_healthy_hour'])} | {fmt(op['false_alert_windows_per_healthy_hour'])} |")
        lines += ['', f"p95 model inference: {live['inference_p95_ms']:.1f} ms, excluding collection. Fault-transition windows are excluded. False windows/hour are not deduplicated incident alerts, and short observation periods make the estimates unstable."]
        if 'fault_target_distribution' in live:
            faults = [r for r in live['trials'] if r['target'] is not None]
            matches = sum(r['operational_alert']['first_alert_service_matches_injected_target'] is True for r in faults)
            lines += ['', f"Targets: {live['fault_target_distribution']}. The first operational hypothesis matched {matches}/{len(faults)} injected targets; always choosing the most common target would achieve {live['service_prior_only_localization']:.1%}. {live.get('repetitions_per_fault',1)} repetition(s) per target/fault; these are known faults on one controlled application, not reviewed real-world root-cause accuracy."]
    if grouping:
        lines += ['', '## Grouped operational incidents', '',
            f"Two warning windows open and two clear windows close. Detected {grouping['detected_fault_trials']}/{grouping['fault_trials']} fault trials; {grouping['healthy_false_incidents']} healthy false incidents over {grouping['healthy_exposure_seconds']/60:.1f} observed healthy minutes. Schedules classify decisions only afterwards. Opening-time incident detection differs from fault-window recall; this limited controlled exposure does not establish a production alert rate."]
    if integrity:
        lines += ['', f"Artifact audit passed for {integrity['phase_count']} phases, {integrity['windows']:,} observation windows and {integrity['test_windows']:,} predictions: chronological phase order, archived source hashes and frozen checkpoint verified. Raw-file and canonical prediction receipts are retained per run. Archived runners omitted the final JSONL journal append; canonical predictions.json retains every window. The current runner repairs that journal behavior for future runs."]
    if serving:
        lines += ['', '## Durable serving checks', '',
            f"Native observer SQLite commits offsets, partial records, future pending events, predictions and incident state together. Actual archived replay matched {observer['windows_verified'] if observer else '—'} windows exactly across {observer['restarts'] if observer else '—'} object restarts; duplicate scoring was rejected. A separate five-minute healthy observer collected 100 fresh windows. These checks verify serving behavior, not model generalisation.", '',
            f"OpenStack V4 HTTP replay: {serving['parameter_events_sent']:,} raw duration events; {serving['heldout_sessions_compared']} held-out sessions matched offline scores with maximum difference {serving['max_score_difference']:.1f}. {serving['eligible_complete_ml_sessions']} sessions were complete for ML decisions; two no-parameter sessions remain listed. Duplicate submission returned HTTP {serving['duplicate_http_status']}. This is historical replay through a real HTTP/SQLite serving path, not a live company OpenStack connection."]
    if runtime:
        lines += ['', f"Bounded running-app verification with the latest native checkpoint: {runtime['windows']} chronological windows over {runtime['completed_seconds']} seconds, {runtime['collector']['records_read']:,} validated request events, {runtime['operational_warning_windows']} operational warning windows, {runtime['ml_warning_windows']} ML novelty windows, {runtime['opened_incidents']} grouped incidents and {runtime['dropped_workload_requests']} dropped workload requests. Source snapshots and checkpoint were verified. {runtime['collector']['late_records']} records preceded the first observation window and remain counted. This actual new healthy workload validates the serving path, not fault detection or industrial reliability."]
    if llm:
        lines += ['', '## Latest local LLM comparison', '', f"`{llm['model_id']}` on run `{llm['run_id']}`. {llm['sample']}. No fault labels or schedule fields enter prompts.", '',
            '| Trial | Mode | Structural acceptance | Policy acceptance | Healthy review fraction | Fault review fraction | p95 seconds |', '|---|---|---:|---:|---:|---:|---:|']
        for result in llm['results']:
            fmt = lambda value: '—' if value is None else f'{value:.3f}'
            lines.append(f"| {result['trial']} | {result['mode']} | {result['structural_acceptance']:.3f} | {fmt(result.get('policy_acceptance'))} | {fmt(result['healthy_review_fraction'])} | {fmt(result['fault_review_fraction'])} | {result['latency_p95_ms']/1000:.2f} |")
        lines += ['', f"Policy {llm.get('policy_version','v1')}: {llm.get('evaluation_stage','development')}. Frozen pretrained weights; no fine-tuning. The policy/source manifest is retained when available. Valid evidence IDs and schemas do not prove semantic support. The initial smaller-model probe is retained in its original run directory. No final LLM diagnosis model is declared.", '',
            'An [explanation support spot check](explanation_support_review.md) found accepted outputs making unsupported downstream-cause and failed-request claims. This is an author/agent review of selected outputs, not an independent semantic-accuracy estimate. The LLM does not control operational incidents.']
        if sampled:
            logs,hybrid=sampled['modes']['logs_only'],sampled['modes']['hybrid']
            lines += ['', f"{logs['generations']+hybrid['generations']} total generations in {sampled['seconds']/60:.1f} minutes. Log-only reviewed {logs['fault_reviews']}/{logs['fault_samples']} sampled fault windows; hybrid reviewed {hybrid['fault_reviews']}/{hybrid['fault_samples']}, naming the injected target in {hybrid['fault_target_reviews']} and abstaining in {hybrid['fault_abstentions']}. Both had zero reviews in their {hybrid['healthy_samples']} sampled healthy windows. These sampled outcomes are neither incident recall nor semantic accuracy; some abstentions intentionally avoid attributing global source absence."]
    lines += ['', '## Remaining release gates', '',
        '1. Kubernetes/WSL/Docker provisioning requires a Windows administrator or an available Linux host.',
        '2. Reproduce orchestration and infrastructure faults on that cluster; native HTTP faults do not cover them.',
        '3. Collect hours/days of independent healthy workloads and unseen-system/fault trials; tune only development/calibration data.',
        '4. Resolve weak cross-system transfer and validate semantic explanation support before claiming reliable AI diagnosis.',
        '5. Record an industrial release demo after those acceptance gates; the local research demo guide and source handoff are available, retaining negative results.', '',
        '## Reproduce and inspect', '',
        'See [native live workflow](native_live_workflow.md), [full-data workflow](full_data_workflow.md), '
        '[external transfer](external_transfer_results.md), [model source research](semantic_models_research.md), '
        'and [project specification](project_specification.md).', '',
        'Run `python scripts/build_project_report.py` to regenerate this report after new experiments.']
    path = ROOT/'docs/project_status.md'
    path.write_text('\n'.join(lines)+'\n', encoding='utf-8')
    print(path)


if __name__ == '__main__': build()
