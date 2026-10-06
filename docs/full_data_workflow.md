# Full-data workflow

Run from the project directory with its Python environment. These commands use the complete acquired RCAEval release, not synthetic logs or the BGL parsing sample.

```powershell
.\.venv\Scripts\python.exe -m incidentlab.research_pipeline prepare
.\.venv\Scripts\python.exe -m incidentlab.research_pipeline train
.\.venv\Scripts\python.exe -m incidentlab.research_pipeline validate
.\.venv\Scripts\python.exe -m incidentlab.research_pipeline test
.\.venv\Scripts\python.exe -m uvicorn incidentlab.research_server:app --host 127.0.0.1 --port 8768
```

VS Code has matching tasks named `Research 1` through `Research 4` and `Research. Run full experiment`. Earlier commands in `incidentlab.train` still belong to the synthetic fixture.

## What this first baseline implements

Metrics are aggregated into complete 60-second windows. Every available log row is scanned in bounded batches for per-service volume and error indicators. Features measure resource, latency, error and log changes relative to the first five minutes of each run. This causal warm-up never reads later observations. The statistical baseline does not yet use traces, log-template learning, semantic encoders or an LLM.

Split assignment is deterministic, by whole case, stratified by published dataset, with a 60/20/20 allocation. This is an in-system held-out-run experiment, not a held-out-system generalization claim. Cases with inadequate normal/fault periods are recorded in the manifest rather than silently dropped. Pre-fault labels select healthy training/calibration rows; inference receives only numeric features. Injection time and root-cause labels are stored in a separate evaluation table and used only for training-window selection and scoring.

The model is an IsolationForest fitted on healthy training service windows. Validation selects a 99.5th percentile threshold separately for each system using the maximum service score in a window. Frozen test evaluation reports alert precision/recall, PR-AUC, per-system results, incident recall, and diagnosis ranking at the first detected fault window. The prior-only ranker uses training-case service counts as a bias baseline.

False alert windows per healthy hour is a benchmark measure; it is not a deduplicated production incident rate. The initial five minutes must be healthy, and this assumption must later be tested and removed for continuously operating deployments. Resource changes indicate a candidate service, not proven causation.

## Where the work is saved

- `data/processed/rcaeval/split_manifest.json`: exact case allocation and exclusions.
- `data/processed/rcaeval/evaluation_labels.parquet`: separated ground truth.
- `data/processed/rcaeval/<case>.parquet`: per-service window features.
- `artifacts/research/preprocessing_report.json`: case inventory and actual log rows processed.
- `artifacts/research/full_training_report.json`: fit count and runtime.
- `artifacts/research/full_validation_report.json`: frozen alert thresholds.
- `artifacts/research/full_test_report.json`: held-out metrics.
- `artifacts/research/full_test_predictions.json`: predictions and diagnosis outcomes.
- `artifacts/research/rcaeval_calibrated.joblib`: locally trusted fitted model.

The separate dashboard on port 8768 displays those reports and replays held-out observations chronologically. Each replay window ranks services and exposes the largest feature changes. Historical replay is not live Kubernetes ingestion.

## Temporal comparison and serving

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-deep.txt
.\Run-Research.ps1 -Mode Temporal
.\Run-Research.ps1 -Mode Inspect
.\.venv\Scripts\python.exe scripts\verify_streaming.py
```

The last command requires the research server already running. It submits real archived
features chronologically to the HTTP inference API, compares predictions, checks duplicate
rejection and measures local HTTP latency. It does not generate a live application incident.
VS Code tasks reveal a dedicated terminal for inspection or temporal training. Commands run
by the coding agent appear in its terminal; they do not automatically appear in an existing
VS Code terminal. Training curves are saved in `artifacts/research/temporal_training_report.json`.

`Run-Research.ps1` prints each executed command and saves its transcript under
`artifacts/logs/latest-research-run.log`. Inspect mode reads results without retraining.
