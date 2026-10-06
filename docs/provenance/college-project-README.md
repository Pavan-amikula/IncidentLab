# IncidentLab

For the CPU laptop transfer, start with [TRANSFER_README.md](TRANSFER_README.md).
Use `Setup-Laptop.ps1` and `Start-Laptop.ps1`; these load saved models without GPU retraining.

Evidence-grounded cloud incident detection and investigation: full-data research,
separate training/calibration/testing, fresh HTTP fault trials, trace evidence and an
optional local LLM. This is a research prototype; no production reliability or final
cross-system model is claimed.

## Run the project

Open this directory in VS Code. The research dashboard is
[localhost:8768](http://127.0.0.1:8768/); fresh trials and evidence are at
[localhost:8768/live](http://127.0.0.1:8768/live). Servers bind to localhost.

```powershell
# Serve saved models/results; this does not retrain.
.\.venv\Scripts\python.exe -m uvicorn incidentlab.research_server:app --host 127.0.0.1 --port 8768

# Collect real HTTP traffic, train, calibrate and test five independent trials.
.\Run-Live.ps1 -Mode Collect -Seconds 120

# Balanced localization: every fault on each service; fresh training and calibration.
.\.venv\Scripts\python.exe -u -m incidentlab.native_experiment --seconds 60 --window 3 --healthy-loads --fault-targets frontend checkout inventory

# Longer validation: 22 phases, 1,140 windows, about 57 minutes plus startup.
.\Run-Live.ps1 -Mode Validation

# Serve a completed native checkpoint on new requests for a bounded ten minutes.
.\.venv\Scripts\python.exe -u -m incidentlab.native_runtime --run-id <completed-run-id> --minutes 10
```

VS Code **Terminal → Run Task** exposes the same stages with visible logs. Read
[measured status](docs/project_status.md), [native workflow](docs/native_live_workflow.md)
and [full-data workflow](docs/full_data_workflow.md).

## End-to-end pipeline

Frontend → checkout → inventory run as three separate HTTP service processes. Real
requests emit latency, HTTP status, dependency responses and linked span/trace IDs.
Incremental bounded ingestion validates raw records, tracks partial writes/late data
and closes chronological windows. Separate healthy runs fit and calibrate frozen
models. New normal/surge/fault runs score online, archive evidence and feed the API
and dashboard. Fault schedules remain outside detector and LLM inputs.

Statistical novelty is shown separately from latency/error/coverage warnings.
Trace-supported service hypotheses distinguish local failures from propagated errors.
Fixed runbook retrieval and an optional local Qwen explanation cite actual records.
Invalid citations, unsupported service hypotheses and contradictions with measured
warnings abstain. No automatic remediation is performed.

The native model uses `incidentlab-http-v1`. The research GRU uses a different frozen
18-feature schema; raw HTTP values are never silently substituted into that model.
Native HTTP trials run on Windows without administrator access. They do not establish
Kubernetes orchestration behavior or production reliability.

A separate durable observer consumes running raw JSONL sources and commits file
offsets, unfinished records, scored windows and grouped incidents atomically in SQLite.
Restart and historical replay checks preserve exact decisions. OpenStack duration
measurements have their own schema and HTTP endpoint; they are not silently passed
to the native or GRU models. See [raw observer and parameter serving](docs/raw_observer_workflow.md).

## Models and full datasets

| Track | Model / purpose |
|---|---|
| RCAEval | Healthy-only Isolation Forest, supervised boosting, CUDA-trained PyTorch temporal multimodal GRU, modality ablations |
| AnoMod | Frozen transfer check, coverage guard, TF-IDF and frozen MiniLM healthy-template novelty |
| OpenStack | Full-file VM-session comparison: Isolation Forest, TF-IDF, MiniLM, healthy-fitted Drain3 transitions, restored raw duration and calibrated delay comparisons |
| Native HTTP | Fresh independent healthy runs, frozen per-service Isolation Forest, operational envelopes, live fault/recovery trials |
| Evidence | Qwen3 0.6B control and 1.7B candidate; local log-only/hybrid comparisons with citation/schema checks |

Complete RCAEval acquisition has 735 cases; 733 are eligible. Preprocessing scans
49,652,771 log rows and 110,714,052 trace spans; case splits are 439/147/147.
All 24 AnoMod fault runs are evaluated. The SocialNetwork semantic check processes
3,606,959 eligible application log events. All 207,820 OpenStack lines are scanned;
VM-session scoring uses explicitly instance-associated records and publishes exclusions.

Negative results remain visible. Frozen AnoMod transfer is poor. MiniLM produced the
same warning counts as TF-IDF on inspected SocialNetwork cases. Initial OpenStack
methods missed the four annotated abnormal VM sessions. The small 0.6B LLM often
rejected valid healthy operation and failed output checks. Later development revisions
are reported separately; there is no final deployment-model claim from these results.
Millions of log lines are not millions of independent faults.

The longer native validation completed 22 phases and 1,140 windows. Grouped
operational checks detected 18/18 controlled fault trials with zero false incident
openings over 36.2 healthy minutes; one isolated surge warning did not open an
incident. Isolation Forest detected 10/18 trials and remains a separate novelty
signal. A subsequent five-minute running-app serving check used the frozen model
on 5,316 newly arriving request events, with no operational incidents. These limited
controlled observations do not establish production reliability.

The local LLM is optional. An [explanation support spot check](docs/explanation_support_review.md)
found accepted outputs making unsupported causal/failure claims. Valid IDs and
schemas do not establish faithful explanation, and no final diagnosis model is declared.

Restoring raw duration parameters detected all four inspected OpenStack anomalies,
but raised 13 healthy false alerts. An operation-specific delay-rank development
revision reduced these to five with precision 0.400. This is not a fresh-test result.
Both profiles passed complete parameter replay through HTTP and SQLite for 6,037
events, with exact offline score agreement for 830 eligible held-out sessions.

## Install and reproduce

Verified environment: Windows, Python 3.14, ~32GB RAM, RTX 2000 Ada 16GB.
The project uses PyTorch; TensorFlow is not used.

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-research.txt
.\.venv\Scripts\python.exe -m pip install -r requirements-deep.txt -r requirements-semantic.txt
.\.venv\Scripts\python.exe scripts\acquire_research_data.py
.\.venv\Scripts\python.exe scripts\extract_research_archives.py
.\.venv\Scripts\python.exe scripts\audit_research_data.py
.\.venv\Scripts\python.exe -m incidentlab.semantic_models both
.\.venv\Scripts\python.exe -m incidentlab.semantic_models llm_medium
.\Run-Live.ps1 -Mode Semantic
.\Run-Live.ps1 -Mode OpenStack
.\Run-Live.ps1 -Mode LLM
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
.\.venv\Scripts\python.exe -m scripts.verify_live_collector
.\.venv\Scripts\python.exe scripts\build_project_report.py
```

CUDA requirements target the verified Windows environment. CPU container serving has
a separate Dockerfile. Public neural weights are revision-pinned and hash-verified.
Raw data, model weights and artifacts are excluded from Git/source archives. Read
[dataset provenance and licenses](docs/dataset_evidence.md) and
[model source documentation](docs/semantic_models_research.md). Papers are referenced,
not redistributed.

Research checkpoints/reports: `artifacts/research/`. Native per-run raw telemetry,
source snapshots, schedules, models and predictions: `artifacts/live/<run-id>/`.
Processed Parquet/split manifests: `data/processed/`. API docs: `/docs`.
Research replay and GRU feature serving are separate from the native live API.

The original port-8767 synthetic demo and 2,000-line BGL fixture remain engineering
regression fixtures; see [original workflow](docs/workflow.md).

## Remaining release gates

Kubernetes provisioning and orchestration/infrastructure fault trials require a working
container engine or Linux host. Longer independent healthy controls, repeated unseen
faults, cross-system transfer and explanation-support review are required before an
industrial reliability claim. Read [specification](docs/project_specification.md),
[paper review](docs/literature_review.md) and [deployment staging](deployment/README.md).
