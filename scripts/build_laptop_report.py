"""Rebuild the laptop report from completed experiments and reviewed receipts."""
import argparse
import json
import re
from pathlib import Path
import numpy as np

ROOT=Path(__file__).resolve().parents[1]


def read(path):return json.loads(path.read_text(encoding='utf-8-sig'))


def memory_bytes(value):
    number,unit=re.match(r'([0-9.]+)([A-Za-z]+)',value.split(' / ')[0]).groups()
    return float(number)*{'B':1,'KiB':1024,'MiB':1024**2,'GiB':1024**3}[unit]


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run-id',default='20261006T141939-0fc666');args=parser.parse_args()
    run=ROOT/'artifacts/kubernetes'/args.run_id
    report=read(run/'report.json');review=read(run/'trace_review.json')
    assert report['status']=='complete'
    assert all(p['score_decision_replay_mismatches']==0 for p in review['phases']), 'Run review_laptop_cluster --rescore first and investigate mismatches'
    assert all(p['arrival_cutoff_feature_mismatches']==0 for p in review['phases'])
    assert review['stored_checkpoint_digest_matches_report']
    receipts=ROOT/'artifacts/laptop_validation'
    assert (receipts/'validate-checkpoint-before-faults.sha256').read_text().strip()==report['checkpoint_sha256']
    by_phase={p['phase']:p for p in review['phases']}
    predictions=[p for phase in review['phases'] for p in read(run/phase['phase']/'predictions.json')]
    samples=[json.loads(line) for line in (receipts/'resource_samples.jsonl').read_text(encoding='utf-8-sig').splitlines() if line]
    samples=[p for p in samples if p.get('cluster_progress',{}).get('run_id')==args.run_id]
    fault_trials=[t for t in report['trials'] if t['target']]
    for trial in fault_trials:
        evidence=by_phase[trial['phase']]
        assert evidence['impact_event_count']>0 or (trial['kind']=='unavailable' and trial['target']=='frontend'
            and evidence['frontend_transport_failures_during_unavailability']>0 and evidence['snapshots_without_service'].get('frontend',0)>0), 'Fault impact was not confirmed'
    summary=dict(run_id=args.run_id,status='complete',phases=len(review['phases']),
        observation_windows=sum(len(read(run/p['phase']/'windows.json'))//3 for p in review['phases']),
        scored_windows=len(predictions),training_windows=report['training_windows'],calibration_windows=report['calibration_windows'],
        client_requests=sum(p['client_count'] for p in review['phases']),captured_spans=sum(p['event_count'] for p in review['phases']),
        operational_trials_flagged=sum(t['operational_alert']['incident_detected'] is True for t in fault_trials),
        ml_trials_flagged=sum(t['ml_alert']['incident_detected'] is True for t in fault_trials),
        confirmed_controlled_trials=len(fault_trials),
        incomplete_successful_trace_chains=sum(p['successful_client_traces_with_incomplete_service_chain'] for p in review['phases']),
        missing_parent_links=sum(p['parent_links_missing'] for p in review['phases']),
        dropped_workload_requests=sum(p['dropped_workload_requests'] for p in review['phases']),
        feature_replay_mismatches=sum(p['arrival_cutoff_feature_mismatches'] for p in review['phases']),
        score_decision_replay_mismatches=sum(p['score_decision_replay_mismatches'] for p in review['phases']),
        maximum_replayed_score_difference=max(p['maximum_replayed_ml_score_difference'] for p in review['phases']),
        checkpoint_sha256=report['checkpoint_sha256'],inference_p95_ms=report['inference_p95_ms'],
        window_close_to_decision_p95_ms=float(np.quantile([p['window_close_to_decision_ms'] for p in predictions],.95)),
        cleanup_receipts_restored=sum(p['cleanup']['status']=='restored' for p in review['phases']),
        validation_resource_samples=len(samples),sampled_node_memory_max_mib=max(memory_bytes(p['node']['MemUsage']) for p in samples if 'node' in p)/1024**2,
        sampled_windows_available_memory_min_gib=min(p['available_memory_bytes'] for p in samples)/1024**3,
        sampled_free_disk_min_gib=min(p['free_disk_bytes'] for p in samples)/1024**3,
        resource_sample_first=samples[0]['observed_at'],resource_sample_last=samples[-1]['observed_at'],
        evaluation_boundary='Trial flags and window fractions use command-completion proxies with crossing windows excluded; not grouped incidents or independently adjudicated causal diagnosis.')
    (receipts/'final_summary.json').write_text(json.dumps(summary,indent=2))
    table=[]
    for t in fault_trials:
        p=by_phase[t['phase']]
        evidence=(f"{p['impact_event_count']} delayed target spans" if t['kind']=='delay' else
            f"{p['impact_event_count']} local error spans; {p['active_failed_clients']} failed clients" if t['kind']=='error' else
            f"{p['frontend_transport_failures_during_unavailability']} transport failures; frontend pod removed" if t['target']=='frontend' else
            f"{p['impact_event_count']} failed dependency spans; {p['active_failed_clients']} failed clients")
        table.append(f"| {t['kind']} | {t['target']} | {t['operational_alert']['fault_window_recall']:.3f} | {t['ml_alert']['fault_window_recall']:.3f} | {evidence} |")
    controls=[]
    for name in ('test_healthy','test_surge'):
        p=by_phase[name]
        controls.append(f"| {name} | {p['client_count']} | {p['operational_warning_windows']} | {p['ml_warning_windows']} | {p['client_requests_per_planned_second']:.2f} |")
    cpu=read(receipts/'cpu-verification-original-source.json')
    max_difference=max(p['max_cpu_gpu_score_difference'] for p in cpu['temporal_comparisons'])
    body=f'''# IncidentLab: actual laptop deployment and validation, 6 October 2026

## Outcome and execution boundary

The CPU startup, Docker image build, isolated Kubernetes deployment, revised Quick experiment, and full Validate experiment completed on the user's laptop. The final run **`{args.run_id}`** contains **{summary['phases']} phases, {summary['observation_windows']} three-second observation windows, {summary['client_requests']:,} real client requests and {summary['captured_spans']:,} captured service spans**. The planned observation duration was 21 minutes, plus startup, polling, control and cleanup overhead.

Operational checks flagged **{summary['operational_trials_flagged']}/9** trace-supported controlled trials. ML-only IsolationForest flagged **{summary['ml_trials_flagged']}/9** under the prepared evaluation protocol. These are trial/window flags, not grouped incident counts. Every intended fault produced reviewed client or service evidence, but the automatic window labels still use command-completion proxies; this report does not replace them with independently adjudicated exact onset labels.

Three HTTP application services run in Kubernetes. Collection, fresh small-model fitting, CPU inference and the FastAPI dashboard run on Windows. The research GRU and other transferred checkpoints were not retrained. New LLM generation remains disabled, confirmed by actual HTTP 503 from its endpoint. No automatic remediation was enabled.

## Laptop verification

- All **2,502** transferred files passed SHA-256 and byte-count verification before changes. The folder was already extracted; this check compares files with the embedded manifest.
- Python **3.14.8 x64**, PyTorch **2.11.0+cpu**, CUDA version **None**, two numerical threads. Saved native and OpenStack checkpoints loaded. Three temporal profiles replayed 65, 7 and 11 windows; maximum CPU/GPU score difference was **{max_difference:.9f}**. These are portability checks, not transfer/generalization evidence.
- The original lean CPU suite passed **70 tests**. After the HTTP framing fix, **71 tests** passed, including a real-HTTP response-length regression. The optional transformer-dependent module was excluded; the historical full 80-test result belongs to the college PC.
- Actual localhost HTTP returned 200 for research, native and Kubernetes status endpoints. The dashboard remains at [localhost:8768](http://127.0.0.1:8768/); [cluster results](http://127.0.0.1:8768/api/kubernetes/status) report the completed run.
- One-minute frozen native-model run `running-app-20261006T135636-9a73f9`: 20 windows, zero dropped workload requests, zero operational warnings/opened incidents, one ML warning. Its final collector accounted for 48 pre-window late records and had zero pending/partial records. This is a bounded healthy check, not a false-alarm-rate estimate.

Receipts and terminal logs are in `artifacts/laptop_validation/`. Original research and college-PC measured results remain unchanged.

## Deployment and preserved failures

Docker Desktop **4.90.0**, Linux Docker engine **29.7.2**, kind **0.33.0**, kubectl client **1.36.1**, Kubernetes server **1.37.0**. Only `kind-incidentlab` and the owned `incidentlab-testbed` namespace were used. Docker confirmed the node's configured **2 CPU / 4 GiB** limits. All three deployments finish with one Ready/available replica and empty fault controls.

1. Initial setup failed because Python 3.14 was absent; Check failed because kind was absent. Automatic approval review blocked the Python installer command. The user installed both prerequisites manually, after which Check passed. No administrator-dependent Docker/WSL action was required in this session.
2. Cluster bootstrap failed on the engine's cgroup v1. A retained diagnostic retry confirmed the kubelet refusal. Logs were exported before removing only the owned failed node. Explicit local compatibility sets `failCgroupV1: false`, with a digest-pinned node image. [Kubernetes documents this temporary override and recommends migration to cgroup v2](https://kubernetes.io/blog/2026/07/31/kubernetes-v1-37-sneak-peek/). This is not a production configuration.
3. Quick `20261006T140359-a6e839` failed before training/fault injection: the health response waited about one second for port-forwarded connection EOF, exceeding the 0.3-second read timeout. Exact **Content-Length** headers now frame health/request responses. The small image was rebuilt, loaded, and the owned deployments restarted; unchanged YAML alone does not replace pods using the same development tag.
4. Quick `20261006T140735-d370bc` completed but did **not** establish inventory outage detection. Every client succeeded during scale-down; snapshots showed the terminating pod still serving during its 30-second grace period. Its automatic detected-trial flag is retained as a misleading proxy result, not credited as confirmed outage detection.
5. `Configure-LaptopTestbed.ps1` applies a one-second termination grace period only after namespace/deployment ownership checks. Revised Quick `20261006T141408-1b6632` then confirmed all three inventory faults: operational 3/3, ML 0/3; 32 active-cohort failed requests matched 32 dependency-failure spans in the outage. Seven successful chains lost their inventory span around deletion. The short grace period is a controlled experiment choice, not a production shutdown recommendation.

All failed runs, source snapshots, command times and cleanup receipts remain available. Validate used fresh 60-window healthy training and separate 60-window calibration; no thresholds were tuned against the known faults.

## Validate results and reviewed impact

Fractions below are **automatic fault-window fractions under command-completion proxy labels**, excluding windows crossing control boundaries. Evidence counts inspect actual requests; they are not new independent fault samples. Delay inspection uses >=200 ms for the configured 250 ms injection. Frontend unavailability has transport/lifecycle evidence rather than an application error span from a nonexistent server.

| Fault | Target | Operational fraction | ML fraction | Reviewed impact |
|---|---|---:|---:|---|
{chr(10).join(table)}

The first reviewed delay/error request starts were approximately 0.016–0.049 seconds after command completion. Downstream unavailability impact appeared approximately 2.06–2.07 seconds later. These are first observed request impacts, not exact underlying failure-onset estimates. Correct first-ranked services are investigation hypotheses; global missing telemetry and ordering heuristics do not establish causal diagnosis accuracy.

The two held-out controls each lasted three minutes, with all client requests returning 200:

| Control | Client requests | Operational warning windows | ML warning windows | Actual requests / planned second |
|---|---:|---:|---:|---:|
{chr(10).join(controls)}

The surge control had three ML novelty warnings despite no operational fault. Another ML warning in the frontend-delay phase occurred after recovery on ordinary checkout latency; it is not credited as delay detection. Zero operational warnings over six control minutes is a limited observation, not proof of a production false-alert rate. Serial polling lowers actual request rates below the nominal schedule; zero dropped requests refers to the runner's concurrency-cap counter.

## Chronology, capture quality and performance

- The stored checkpoint stayed unchanged from before the fault trials to completion: `{summary['checkpoint_sha256']}`.
- **{summary['scored_windows']} scored windows** were reconstructed using each stored arrival cutoff and rescored with the frozen model. Feature mismatches: **0**; score/decision mismatches: **0**; maximum score difference: **{summary['maximum_replayed_score_difference']}**. No captured event in a scored window arrived after its decision cutoff.
- Stored `(service, span)` keys and exports were unique. All **{summary['cleanup_receipts_restored']} cleanup receipts** are restored; counted dropped requests: **{summary['dropped_workload_requests']}**.
- **{summary['incomplete_successful_trace_chains']} successful request chains were incomplete**, seven in each scale-down phase. There were **{summary['missing_parent_links']} missing parent links** across frontend/checkout deletion. These are capture omissions even though those requests succeeded. Polling can lose a deleted pod's tail; exact replay proves consistency on captured data, not completeness. Do not label these omissions as application failures or reconstruct nonexistent records.
- Model inference p95: **{summary['inference_p95_ms']:.2f} ms**. Window-close-to-decision p95: **{summary['window_close_to_decision_p95_ms']/1000:.2f} seconds**, including collection grace and polling. The automatic report's window-end-based detection delay is not the actual alert-decision timestamp.
- Model inspection found no healthy variation in error fraction/concurrency and no corresponding tree splits. Absence has no ML score by implementation. The forest remains a limited novelty signal; operational latency/error/coverage checks produced the stronger result.

Review evidence: `artifacts/kubernetes/{args.run_id}/trace_review.json`; original automatic metrics: `report.json`. Client outcomes, raw spans, SQLite arrival watermarks, lifecycle snapshots, control timestamps and source snapshots remain beside them.

## Observed laptop resources

During Validate, **{summary['validation_resource_samples']} samples** recorded a maximum node memory report of **{summary['sampled_node_memory_max_mib']:.1f} MiB**, minimum available Windows memory of **{summary['sampled_windows_available_memory_min_gib']:.2f} GiB**, and minimum free disk of **{summary['sampled_free_disk_min_gib']:.2f} GiB**. Sampling ran from `{summary['resource_sample_first']}` to `{summary['resource_sample_last']}`.

These are sampled values, not instantaneous peaks or minimum laptop requirements. Node statistics exclude the rest of the Docker VM and host-side inference/dashboard. Ambient memory/disk availability changed during the session. The configured node/pod limits are not measured capacity requirements. No unrelated Docker resources were removed to make space.

## Reproduce the current source and experiment

The immutable transfer manifest remains intact. Three runtime source amendments and their original hashes are in `laptop_patch_manifest.json`; originals are in `artifacts/laptop_validation/originals/`. The explicit amendment option verifies changed runtime source without skipping or modifying dataset/checkpoint evidence.

From the extracted `IncidentLab` project directory:

```powershell
$env:PATH="$env:LOCALAPPDATA\\IncidentLab\\tools;$env:PATH"
powershell -ExecutionPolicy Bypass -File .\\Setup-Laptop.ps1 -PatchManifest .\\laptop_patch_manifest.json
.\\.venv-laptop\\Scripts\\python.exe -m scripts.test_laptop
powershell -ExecutionPolicy Bypass -File .\\Run-Cluster.ps1 -Mode Check
```

For a **new** cluster on this cgroup-v1 engine, run `Prepare-LaptopCluster.ps1 -AllowLegacyCgroupV1` first. It refuses to recreate an existing named cluster. Then deploy:

```powershell
powershell -ExecutionPolicy Bypass -File .\\Run-Cluster.ps1 -Mode Deploy
docker build -f deployment/Dockerfile.testbed-laptop-pinned -t incidentlab-testbed:dev .
kind load docker-image incidentlab-testbed:dev --name incidentlab
powershell -ExecutionPolicy Bypass -File .\\Configure-LaptopTestbed.ps1
```

After a rebuild using the same tag, restart only the three owned deployments in `kind-incidentlab` / `incidentlab-testbed` and wait for each rollout. Inspect ownership before reusing resources; Run-Cluster and Configure-LaptopTestbed perform their ownership checks. The pinned Dockerfile contains the captured base digest, and actual image/pod identities are archived under laptop_validation. Build attestations may vary on rebuild.

```powershell
foreach ($service in @('frontend','checkout','inventory')) {{
    kubectl --context kind-incidentlab -n incidentlab-testbed rollout restart "deployment/$service"
    kubectl --context kind-incidentlab -n incidentlab-testbed rollout status "deployment/$service" --timeout=120s
}}
powershell -ExecutionPolicy Bypass -File .\\Run-Cluster.ps1 -Mode Quick
powershell -ExecutionPolicy Bypass -File .\\Run-Cluster.ps1 -Mode Validate
.\\.venv-laptop\\Scripts\\python.exe -m scripts.review_laptop_cluster artifacts/kubernetes/<run-id> --rescore
```

For this saved experiment, rebuild the report with `python -m scripts.build_laptop_report --run-id {args.run_id}` using the laptop venv. Use `Setup-Laptop.ps1 -CheckOnly -PatchManifest .\\laptop_patch_manifest.json` for artifact/source verification without reinstalling. Start the dashboard separately with `Start-Laptop.ps1`; it reads saved evidence and does not launch training. Port 8891 is shared with native experiments, so run them separately. Numerical threads were bounded to two during collection. The resolved dependency receipt is `artifacts/laptop_validation/requirements-resolved.txt`.

## What remains beyond this experiment

The completed college-PC research remains distinct: RCAEval 735 acquired / 733 eligible cases, 439/147/147 case splits, approximately 49.7 million logs and 110.7 million spans; saved GRU/baseline experiments; weak external transfer; OpenStack development false alarms; and the 22-phase native run with operational/grouped 18/18 versus ML-only 10/18. None of those measurements were replaced by the laptop trials.

Industrial validation remains open: longer independent healthy periods; repeated unseen faults and systems; drift and workload shifts; reliable continuous collection across deletion/rotation and same-pod container restarts; production model-serving deployment and operational security/availability testing; and independent explanation-support review. This run exercised pod deletion/replacement, not log rotation or the previous-container restart path. It tested a known three-service application under bounded traffic, not company production or a full range of infrastructure failures.

Accepted saved LLM explanations with unsupported statements remain negative evidence. New generation is disabled, no final reliable diagnosis model is declared, and no autonomous remediation was added. The laptop deployment experiment is complete; the project remains a research prototype with explicit remaining industrial gates.
'''
    (ROOT/'docs/laptop_execution_20261006.md').write_text(body)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
