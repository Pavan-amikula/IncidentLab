# First full-data baseline — 5 October 2026

Implemented and executed preprocessing, training, validation and held-out testing using the complete RCAEval release. This is a conventional metrics/log baseline, not a deep-learning or LLM model and not production validation.

## Data and separation

- 735 acquired cases; 733 eligible cases. Two RE1 cases lack adequate pre-fault/post-fault observations and are listed in the split manifest.
- All 49,652,771 available log rows scanned, alongside per-case metric tables. No trace features used yet.
- 439 training cases, 147 validation cases, 147 test cases. No case appears in multiple splits.
- 375,292 prepared service/window rows. IsolationForest fitted on 78,158 healthy training service windows.
- First five minutes of each run provide a causal healthy warm-up. Models consume 11 numeric change features; fault names and injection/root-cause annotations are excluded from scoring.
- Preprocessing took 508.19 seconds; model fitting took 4.25 seconds on this machine. Fast fitting reflects aggregate features and sampled IsolationForest trees, not deep training on every raw message.

## Held-out results

| Measure | Result |
|---|---:|
| Window precision | 97.2% |
| Window recall | 74.3% |
| Window F1 | 0.842 |
| Window PR-AUC | 0.963 |
| Incidents detected | 127/147 (86.4%) |
| Correct service ranked first at first detected fault window | 108/147 (73.5%) |
| Correct service in top three, including missed incidents as failures | 123/147 (83.7%) |
| Training-service-prior-only top one | 28/147 (19.0%) |
| False alert windows per healthy hour | 2.33 |

The main ranker's top-five rate is 85.7%; the service-prior top-five rate is 89.1%. Those figures have different detection conditioning: the main metric includes missed incidents as failures, while the prior ranking assumes an incident is already known. This is a bias diagnostic, not a fair claim that either pipeline universally outperforms the other.

| System | Window F1 | Recall | False alert windows / healthy hour |
|---|---:|---:|---:|
| Online Boutique | 0.936 | 88.7% | 0.79 |
| Sock Shop | 0.899 | 82.2% | 0.93 |
| Train Ticket | 0.617 | 47.0% | 6.17 |

Results are on in-system held-out cases. No cross-system, unknown-fault or external AnoMod/OpenStack comparison has been completed. Ground-truth boundaries are used for evaluation and selecting healthy fitting/calibration examples, not the replay detector. Straddling onset windows are excluded from window metrics.

## Working application

The full-data dashboard serves reports and chronological historical replay at `http://127.0.0.1:8768/`. Browser verification confirmed populated metrics, loading a held-out case and stepping forward through its windows. A separate HTTP check replayed `re2ob_checkoutservice_delay_1`: 19 ordered windows, 12 alerts, and checkoutservice as the highest-scoring service at its last window. One request took 46.2 ms; this is a smoke measurement, not a sustained latency benchmark.

11 correctness tests pass, including causal feature independence from future observations, deterministic whole-case splits, and absence of ground-truth fields in the feature list.

## Next research-driven implementation

The aggregate statistical model misses many Train Ticket fault windows and generates excessive false alerts there. Next compare semantic log/temporal representations and trace evidence against this fixed baseline, using validation for selection. Preserve this test report; repeated tuning after inspecting it requires a fresh final holdout or clearly declared exploratory evaluation. Add held-out-system experiments, missing-modality tests, then live isolated Kubernetes collection and fault trials.

Machine-readable evidence: `artifacts/research/full_training_report.json`, `full_validation_report.json`, `full_test_report.json`, and `full_test_predictions.json`. Commands: `docs/full_data_workflow.md`.
