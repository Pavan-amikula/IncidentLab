# IncidentLab measured status

Evidence-grounded cloud incident detection and investigation. Generated from saved reports; benchmarks and short local trials do not establish production reliability.

## Implemented and executed

- Complete source acquisition and hashes; whole-case research splits.
- Healthy-only Isolation Forest, supervised boosting, CUDA temporal multimodal GRU.
- Frozen AnoMod transfer check; coverage warnings and healthy-trained text novelty.
- Frozen MiniLM semantic encoder and complete OpenStack VM-session comparisons.
- Fresh HTTP services, workload, raw traces, fault/recovery schedule, online scoring and evidence API.
- Local log-only/hybrid LLM comparisons; citation/schema validation and fixed runbook retrieval.

## Full-data results

RCAEval: 733 eligible cases, 49,652,771 scanned log rows. Whole-case splits are retained.
AnoMod frozen transfer: 24 fault runs; temporal alerted in 3, boosting in 2. This is poor run-alert coverage, not verified incident recall.
Semantic log check: 3,606,959 events; MiniLM 51 versus TF-IDF 51 warning service-minutes. No warning-count gain. 83 distinct normalized texts embedded on cuda.

OpenStack: all 207,820 lines scanned. 557 training and 680 healthy calibration VM sessions; four author-annotated abnormal sessions.

| Method | Positive sessions detected | Precision | Recall |
|---|---:|---:|---:|
| isolation_forest | 0/4 | 0.000 | 0.000 |
| lexical | 0/4 | 0.000 | 0.000 |
| semantic | 0/4 | 0.000 | 0.000 |
| drain_sequence | 0/4 | 0.000 | 0.000 |

Only explicitly instance-associated events form VM sessions. Unassigned records and identity exclusions are published. Labels are not per-line fault labels. The sequence addition used already-inspected development cases.

## Restored OpenStack numeric parameters (development)

Text masking discarded measured lifecycle durations. A separate versioned adapter now preserves four operation durations in seconds. Training and calibration use the same healthy splits; the inspected anomaly labels remain development evidence.

| Method | Annotated sessions detected | Precision | Healthy normal2 false alerts |
|---|---:|---:|---:|
| parameter_residual | 4/4 | 0.222 | 13 |
| parameter_isolation_forest | 2/4 | 0.250 | 5 |

Improved detection does not establish a reliable deployment model: the residual detector still raises many false alerts. Missing durations remain explicit, capture boundaries can censor sessions, and completion records do not establish early detection. See [primary-source failure analysis](openstack_failure_research.md).

A subsequent operation-specific delay-rank development comparison at the existing nominal 1% budget detected 4/4, precision 0.400, with 5 healthy normal2 false alerts. It asks a one-sided delay question rather than two-sided novelty. The four-operation correction does not establish a guarantee under chronological/censored data. These are inspected development cases; see [calibration assumptions](parameter_calibration_research.md).

## Latest completed live run

Run `20261005T202755-0e2c27`: 100 independent healthy training windows, 100 separate healthy calibration windows. Checkpoint `118e99295e06b8afe45e4101140143ed1141a4cfe1d8bd670ba8086564d28711`.

| Trial | ML fault-window recall | Operational recall | ML false windows/hour | Operational false windows/hour |
|---|---:|---:|---:|---:|
| test_healthy | — | — | 18.000 | 0.000 |
| test_surge | — | — | 174.000 | 6.000 |
| test_delay_frontend_r1 | 1.000 | 1.000 | 141.176 | 0.000 |
| test_delay_frontend_r2 | 1.000 | 1.000 | 0.000 | 0.000 |
| test_delay_checkout_r1 | 1.000 | 1.000 | 0.000 | 0.000 |
| test_delay_checkout_r2 | 1.000 | 1.000 | 0.000 | 0.000 |
| test_delay_inventory_r1 | 1.000 | 1.000 | 141.176 | 0.000 |
| test_delay_inventory_r2 | 1.000 | 1.000 | 70.588 | 0.000 |
| test_error_frontend_r1 | 0.000 | 1.000 | 70.588 | 0.000 |
| test_error_frontend_r2 | 0.000 | 1.000 | 0.000 | 0.000 |
| test_error_checkout_r1 | 0.000 | 1.000 | 70.588 | 0.000 |
| test_error_checkout_r2 | 0.000 | 1.000 | 70.588 | 0.000 |
| test_error_inventory_r1 | 0.000 | 1.000 | 70.588 | 0.000 |
| test_error_inventory_r2 | 0.000 | 1.000 | 70.588 | 0.000 |
| test_unavailable_frontend_r1 | 0.000 | 1.000 | 70.588 | 0.000 |
| test_unavailable_frontend_r2 | 0.000 | 1.000 | 0.000 | 0.000 |
| test_unavailable_checkout_r1 | 1.000 | 1.000 | 0.000 | 0.000 |
| test_unavailable_checkout_r2 | 1.000 | 1.000 | 141.176 | 0.000 |
| test_unavailable_inventory_r1 | 1.000 | 1.000 | 141.176 | 0.000 |
| test_unavailable_inventory_r2 | 1.000 | 1.000 | 0.000 | 0.000 |

p95 model inference: 33.9 ms, excluding collection. Fault-transition windows are excluded. False windows/hour are not deduplicated incident alerts, and short observation periods make the estimates unstable.

Targets: {'frontend': 6, 'checkout': 6, 'inventory': 6}. The first operational hypothesis matched 18/18 injected targets; always choosing the most common target would achieve 33.3%. 2 repetition(s) per target/fault; these are known faults on one controlled application, not reviewed real-world root-cause accuracy.

## Grouped operational incidents

Two warning windows open and two clear windows close. Detected 18/18 fault trials; 0 healthy false incidents over 36.2 observed healthy minutes. Schedules classify decisions only afterwards. Opening-time incident detection differs from fault-window recall; this limited controlled exposure does not establish a production alert rate.

Artifact audit passed for 22 phases, 1,140 observation windows and 940 predictions: chronological phase order, archived source hashes and frozen checkpoint verified. Raw-file and canonical prediction receipts are retained per run. Archived runners omitted the final JSONL journal append; canonical predictions.json retains every window. The current runner repairs that journal behavior for future runs.

## Durable serving checks

Native observer SQLite commits offsets, partial records, future pending events, predictions and incident state together. Actual archived replay matched 30 windows exactly across 29 object restarts; duplicate scoring was rejected. A separate five-minute healthy observer collected 100 fresh windows. These checks verify serving behavior, not model generalisation.

OpenStack V4 HTTP replay: 6,037 raw duration events; 830 held-out sessions matched offline scores with maximum difference 0.0. 828 sessions were complete for ML decisions; two no-parameter sessions remain listed. Duplicate submission returned HTTP 409. This is historical replay through a real HTTP/SQLite serving path, not a live company OpenStack connection.

Bounded running-app verification with the latest native checkpoint: 100 chronological windows over 300 seconds, 5,316 validated request events, 0 operational warning windows, 1 ML novelty windows, 0 grouped incidents and 0 dropped workload requests. Source snapshots and checkpoint were verified. 15 records preceded the first observation window and remain counted. This actual new healthy workload validates the serving path, not fault detection or industrial reliability.

## Latest local LLM comparison

`Qwen/Qwen3-1.7B` on run `20261005T202755-0e2c27`. 8 uniformly spaced completed windows per trial, chosen without fault labels or detector scores. No fault labels or schedule fields enter prompts.

| Trial | Mode | Structural acceptance | Policy acceptance | Healthy review fraction | Fault review fraction | p95 seconds |
|---|---|---:|---:|---:|---:|---:|
| healthy | logs_only | 1.000 | 1.000 | 0.000 | — | 2.55 |
| healthy | hybrid | 1.000 | 1.000 | 0.000 | — | 1.59 |
| surge | logs_only | 1.000 | 1.000 | 0.000 | — | 2.49 |
| surge | hybrid | 1.000 | 1.000 | 0.000 | — | 1.54 |
| delay_frontend_r1 | logs_only | 1.000 | 1.000 | 0.000 | 0.000 | 2.71 |
| delay_frontend_r1 | hybrid | 1.000 | 1.000 | 0.000 | 1.000 | 2.05 |
| delay_frontend_r2 | logs_only | 1.000 | 1.000 | 0.000 | 0.000 | 2.65 |
| delay_frontend_r2 | hybrid | 1.000 | 1.000 | 0.000 | 1.000 | 2.01 |
| delay_checkout_r1 | logs_only | 1.000 | 1.000 | 0.000 | 0.333 | 2.36 |
| delay_checkout_r1 | hybrid | 1.000 | 1.000 | 0.000 | 1.000 | 2.13 |
| delay_checkout_r2 | logs_only | 1.000 | 1.000 | 0.000 | 0.333 | 2.45 |
| delay_checkout_r2 | hybrid | 1.000 | 1.000 | 0.000 | 1.000 | 2.13 |
| delay_inventory_r1 | logs_only | 0.750 | 0.750 | 0.000 | 0.000 | 2.87 |
| delay_inventory_r1 | hybrid | 0.625 | 0.625 | 0.000 | 0.000 | 2.13 |
| delay_inventory_r2 | logs_only | 0.750 | 0.750 | 0.000 | 0.000 | 3.01 |
| delay_inventory_r2 | hybrid | 0.750 | 0.750 | 0.000 | 0.333 | 2.56 |
| error_frontend_r1 | logs_only | 1.000 | 1.000 | 0.000 | 1.000 | 2.28 |
| error_frontend_r1 | hybrid | 1.000 | 0.750 | 0.000 | 0.333 | 2.00 |
| error_frontend_r2 | logs_only | 1.000 | 1.000 | 0.000 | 1.000 | 2.27 |
| error_frontend_r2 | hybrid | 1.000 | 1.000 | 0.000 | 1.000 | 2.22 |
| error_checkout_r1 | logs_only | 1.000 | 1.000 | 0.000 | 1.000 | 2.87 |
| error_checkout_r1 | hybrid | 1.000 | 1.000 | 0.000 | 1.000 | 3.12 |
| error_checkout_r2 | logs_only | 1.000 | 1.000 | 0.000 | 1.000 | 2.84 |
| error_checkout_r2 | hybrid | 1.000 | 0.875 | 0.000 | 0.667 | 2.60 |
| error_inventory_r1 | logs_only | 1.000 | 1.000 | 0.000 | 1.000 | 2.54 |
| error_inventory_r1 | hybrid | 1.000 | 1.000 | 0.000 | 1.000 | 3.13 |
| error_inventory_r2 | logs_only | 1.000 | 1.000 | 0.000 | 1.000 | 2.38 |
| error_inventory_r2 | hybrid | 1.000 | 1.000 | 0.000 | 1.000 | 3.07 |
| unavailable_frontend_r1 | logs_only | 1.000 | 1.000 | 0.000 | 0.000 | 2.59 |
| unavailable_frontend_r1 | hybrid | 1.000 | 1.000 | 0.000 | 0.000 | 1.58 |
| unavailable_frontend_r2 | logs_only | 1.000 | 1.000 | 0.000 | 0.000 | 2.22 |
| unavailable_frontend_r2 | hybrid | 1.000 | 1.000 | 0.000 | 0.000 | 1.72 |
| unavailable_checkout_r1 | logs_only | 1.000 | 1.000 | 0.000 | 1.000 | 2.34 |
| unavailable_checkout_r1 | hybrid | 1.000 | 1.000 | 0.000 | 1.000 | 2.66 |
| unavailable_checkout_r2 | logs_only | 1.000 | 1.000 | 0.000 | 1.000 | 2.30 |
| unavailable_checkout_r2 | hybrid | 1.000 | 1.000 | 0.000 | 1.000 | 2.83 |
| unavailable_inventory_r1 | logs_only | 1.000 | 1.000 | 0.000 | 1.000 | 2.91 |
| unavailable_inventory_r1 | hybrid | 1.000 | 1.000 | 0.000 | 1.000 | 2.84 |
| unavailable_inventory_r2 | logs_only | 1.000 | 1.000 | 0.000 | 1.000 | 2.47 |
| unavailable_inventory_r2 | hybrid | 1.000 | 1.000 | 0.000 | 1.000 | 2.82 |

Policy v2: fresh known-fault trials after candidate freeze. Frozen pretrained weights; no fine-tuning. The policy/source manifest is retained when available. Valid evidence IDs and schemas do not prove semantic support. The initial smaller-model probe is retained in its original run directory. No final LLM diagnosis model is declared.

An [explanation support spot check](explanation_support_review.md) found accepted outputs making unsupported downstream-cause and failed-request claims. This is an author/agent review of selected outputs, not an independent semantic-accuracy estimate. The LLM does not control operational incidents.

320 total generations in 10.4 minutes. Log-only reviewed 32/54 sampled fault windows; hybrid reviewed 40/54, naming the injected target in 39 and abstaining in 14. Both had zero reviews in their 106 sampled healthy windows. These sampled outcomes are neither incident recall nor semantic accuracy; some abstentions intentionally avoid attributing global source absence.

## Remaining release gates

1. Kubernetes/WSL/Docker provisioning requires a Windows administrator or an available Linux host.
2. Reproduce orchestration and infrastructure faults on that cluster; native HTTP faults do not cover them.
3. Collect hours/days of independent healthy workloads and unseen-system/fault trials; tune only development/calibration data.
4. Resolve weak cross-system transfer and validate semantic explanation support before claiming reliable AI diagnosis.
5. Record an industrial release demo after those acceptance gates; the local research demo guide and source handoff are available, retaining negative results.

## Reproduce and inspect

See [native live workflow](native_live_workflow.md), [full-data workflow](full_data_workflow.md), [external transfer](external_transfer_results.md), [model source research](semantic_models_research.md), and [project specification](project_specification.md).

Run `python scripts/build_project_report.py` to regenerate this report after new experiments.
