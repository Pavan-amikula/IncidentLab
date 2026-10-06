# IncidentLab: end-to-end cloud incident intelligence

## Business use

Help an operations engineer investigate a failing distributed application. For example, a database connection bottleneck produces checkout timeouts in several services. The system should detect the incident, correlate errors with latency/resource evidence, rank likely originating services, show the observed propagation path, and recommend a documented investigation step with supporting timestamps and event IDs. Recommendations remain reviewable by the engineer.

The supplied cloud-log thesis is the strongest direct fit. Axis motivates structured relations and queryable evidence; TRATON motivates uncertainty and fallbacks; Volvo motivates temporal fusion and missing-input robustness. These transferable ideas do not make this a vehicle perception project. We will not claim all seven thesis topics are solved by one platform.

## Architecture and workflow

`Running application / historical replay -> telemetry collectors -> durable ingestion -> normalized logs, metrics, spans -> causal-time windows -> anomaly detector -> incident correlation -> service ranking -> retrieved evidence + optional LLM explanation -> API/dashboard -> outcome feedback`

Training is a separate pipeline:

`Verified raw data -> schema/label audit -> case-group split manifests -> train-only preprocessing -> baseline training -> validation / calibration -> frozen artifact -> held-out tests -> model registry -> serving`

The collector and inference path must accept actual service names and timestamps, multiple sources, and missing modalities. Research ingestion uses explicit dataset adapters. The native HTTP collector uses a separate versioned schema; models are never silently reused across schemas.

## Delivery gates

| Gate | Required artifact and acceptance evidence |
|---|---|
| 1. Data and papers | Complete author-published files; pinned revisions/checksums; actual schema/row inventory; paper design decisions; licensed provenance. |
| 2. Reproducible baseline | Whole-case train/validation/test manifests; Drain + statistical/ML log baseline; metric change baseline; service-prior ranker; frozen preprocessing; held-out reports. |
| 3. Learned comparison | Semantic log encoder / sequence model; multimodal fusion candidate; training curves and checkpoint selection; same splits/data access for comparisons. |
| 4. Evidence-grounded diagnosis | Ranked services and bounded evidence; retrieval from runbooks/dependencies; optional local LLM; evidence-support scoring and abstention. |
| 5. Live end-to-end system | Isolated Kubernetes app, load generator, telemetry collectors, controlled fault schedule, streaming detector, incident API, dashboard and replay. |
| 6. Thesis / portfolio release | Accuracy/latency/cost results, ablations, failure analysis, reproducible commands, demo recording, architecture and limitations. |

The earlier synthetic experiment and 2,000-line BGL experiment are development fixtures. Their scores are not the final project results. No improvement claim is valid until held-out evaluation is completed.

## Data roles

- Complete RCAEval: all 735 cases acquired; 360 RE2/RE3 cases form the multi-source diagnosis backbone, with metric-only RE1 for complementary testing.
- Full OpenStack: separate infrastructure-log benchmark. Audit its file-level annotations before claiming window labels.
- Full AnoMod: independent multi-source/code/database fault evaluation. Its setup is suitable for diagnosis comparisons but not automatic onset-delay estimation.
- Fresh live testbed: healthy workload periods, workload shifts, and controlled injected failures with time-separated trials.

## Evaluation contract

Keep every window from one case in the same split. Choose checkpoints and alert thresholds on validation only. In-system held-out repetitions, unseen fault types, and held-out systems are separate experiments. For normal-only baselines, anomaly labels are evaluation-only. Supervised neural methods may use training labels, with their additional information clearly declared.

Report incident recall, precision/PR-AUC, false alerts per healthy hour, detection delay, top-1/top-3 root-cause accuracy, evidence support, abstention/calibration, throughput, p50/p95 latency, peak RAM/VRAM, and model/token cost. Do not silently drop missing-source cases. Compare log-only, metrics-only, traces-only where available, fusion, and fusion without graph/LLM. Evaluate alert-triggered RCA separately from oracle-onset RCA.

## Hardware and deployment

Verified machine: ~32GB RAM, RTX 2000 Ada 16GB VRAM. Use Parquet batch reads and bounded temporal features rather than loading all raw telemetry into RAM. Begin with compact trainable models and cached semantic embeddings. Profile an LLM before committing to full fine-tuning.

Windows exposes the WSL command, but its Linux runtime is not installed and Docker
has no working engine. Live Kubernetes infrastructure is not running. The student
account cannot elevate to install the missing Windows components. Native HTTP
development and full-data research run without them; cluster execution requires
an administrator-provisioned runtime or an available Linux host.

## Partner work division

Student A: telemetry ingestion, dataset audit, splits, conventional baselines and live workload/fault testbed. Student B: semantic/temporal models, fusion, uncertainty and evidence diagnosis. Both review evaluation, compare results, and write the scientific report.

## Current status

Complete dataset acquisition, paper review, full-data preprocessing, Isolation Forest, supervised boosting and a CUDA temporal multimodal GRU are implemented and executed. The experiment uses 733 eligible cases and scans all 49,652,771 log rows and 110,714,052 trace spans; train/validation/test case counts are 439/147/147. A dashboard compares measured development results and replays telemetry. Durable sequential inference accepts normalized feature windows and persists predictions to SQLite. See `docs/multimodal_results.md` and `docs/streaming_serving.md`. A frozen MiniLM encoder, complete OpenStack session comparison, bounded raw HTTP collector, healthy training/calibration, frozen live trials and local Qwen explanations have also executed. Trace-supported dependency ranking and validated citations are implemented; neither proves causal or semantic correctness. Kubernetes execution, longer independent healthy controls, reviewed explanation support and production validation remain unfinished. No final model is declared from development data alone.


The first frozen-model AnoMod transfer check has executed on all 24 designed fault runs (355 windows): temporal alerts in 3 runs, boosting in 2. This poor conditional transfer result is documented in `docs/external_transfer_results.md`; it is not verified incident recall or a production accuracy result. Future tuning needs fresh final held-out data.

See [measured current status](project_status.md) for balanced three-target trials and negative cross-system results. Cluster manifests are staged in [deployment instructions](../deployment/KUBERNETES.md), but no successful cluster execution is claimed.

The raw native observer now persists file offsets, unfinished records, pending
events, predictions and grouped incident state atomically. Restart/replay checks
retain exact features and decisions; five minutes of fresh healthy observation also
executed. OpenStack numeric lifecycle durations are preserved in a separate schema,
with versioned residual, Isolation Forest and calibrated delay comparisons. Their
HTTP replay covers all 6,037 measurement events with exact offline agreement for
830 eligible sessions. Four inspected anomalies remain development evidence;
neither restored detections nor nominal rank calibration establishes deployment
reliability. See [serving contracts and verification](raw_observer_workflow.md).
