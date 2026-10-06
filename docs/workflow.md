# Training, validation and testing in VS Code

Open `C:\Users\paam25\Downloads\dl project` as a folder. The `.venv` interpreter
is configured in `.vscode/settings.json`. Use **Terminal > Run Task** to choose
one numbered stage or **Run full synthetic experiment**.

## Separate stages

| Stage | Python entry point | Input | Output |
| --- | --- | --- | --- |
| Prepare | `incidentlab/datasets.py` | Generator | Three observation files, separate test labels, checksummed manifest |
| Train | `incidentlab/train.py` | `data/synthetic_v1/train.jsonl` | `artifacts/models/trained.joblib`, `training_report.json` |
| Validate | `incidentlab/validate.py` | Trained checkpoint + `validation.jsonl` | Calibrated `detector.joblib`, `validation_report.json` |
| Test | `incidentlab/test_model.py` | Calibrated checkpoint + `test.jsonl` | `evaluation.json`, `test_predictions.jsonl` |
| Serve | `incidentlab/server.py` | Calibrated checkpoint | Browser inference; no startup training |

From the project terminal:

```powershell
.\.venv\Scripts\python.exe -m incidentlab.datasets
.\.venv\Scripts\python.exe -m incidentlab.train
.\.venv\Scripts\python.exe -m incidentlab.validate
.\.venv\Scripts\python.exe -m incidentlab.test_model
```

Training uses 160 healthy windows to fit 120 trees and four log templates. Validation
uses 100 separate healthy windows to calibrate the 99th-percentile threshold.
Testing scores 240 held-out synthetic windows. Missing telemetry produces abstention;
those 40 windows are excluded from binary detection metrics and reported separately.
There are no neural-network epochs or loss curves in this tree-based baseline.

Set a breakpoint at `Detector().train(windows)` in `train.py` to inspect the data.
The actual learning call is `self.model.fit(...)` in `detector.py`. Break at
`model.validate(windows)` in `validate.py` to inspect threshold calibration, and at
`model.analyze(window)` in `test_model.py` to inspect inference. Debug configurations
are provided for VS Code installations with the Python debugger extension.

`Detector.fit()` remains a synthetic convenience fixture for correctness tests only.
The server and explicit training/testing scripts do not use that combined shortcut.
Model serialization uses joblib: only load locally generated trusted checkpoints.
Checksums detect file changes, but are not an authentication mechanism.

## Real logs: a separate experiment

```powershell
.\.venv\Scripts\python.exe -m incidentlab.real_logs
```

This downloads the 2,000-line BGL sample from a pinned Loghub revision and verifies
its reviewed SHA-256. BGL logs are not relabeled as our fictional four services.
This text-only baseline has no service diagnosis or latency estimates.

Rows are grouped by node, so no node appears in multiple splits. The resulting
1185/440/375 split sizes are uneven because splitting is by group. Only the 1134
normal training rows and 368 normal validation rows are used for fitting/calibration.
The label prefix is removed before feature extraction. Node IDs and timestamps are
also excluded from feature text. Validation/test vocabulary never fits TF-IDF.

The real-log script prints distinct training/validation/testing results through one
entry point; intermediate splits and the saved text-model checkpoint are inspectable.
It reloads the checkpoint for testing. There is no hyperparameter search yet.

Initial frozen result: 20 missed anomalies and one false alert among 375 test rows.
F1 is 0; ROC-AUC is about 0.562. This is a failed first baseline, retained honestly.
These logs are a small research sample, not a chronological Kubernetes workload.
Future model selection must use validation data; these evaluated test records are
already consumed and must not be advertised as a fresh independent test after tuning.

Source and citation: https://github.com/logpai/loghub
Jieming Zhu et al., *Loghub: A Large Collection of System Log Datasets for AI-driven
Log Analytics*, ISSRE 2023. Follow Loghub's academic/research usage conditions.

## Verify correctness

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Eight tests currently cover API persistence, frozen parser behavior, input validation,
missing-telemetry abstention, split separation, corrupted files, checkpoint round-trip,
and real-log label exclusion. These test software behavior, not model accuracy.
