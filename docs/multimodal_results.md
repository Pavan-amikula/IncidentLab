# Measured multimodal development results — 5 October 2026

All 733 eligible RCAEval cases are processed, using 439 training, 147 validation and
147 development-test cases. Whole runs stay within one split. All 49,652,771 log rows
and 110,714,052 trace spans were scanned. Two insufficient-period cases are explicitly
excluded in the manifest. The external AnoMod evaluation is still reserved.

| Candidate | Window F1 | Incident recall | Service top-1 at first alert | False alert windows/healthy hour |
|---|---:|---:|---:|---:|
| Isolation Forest | 0.842 | 86.4% | 73.5% | 2.33 |
| Supervised histogram boosting | 0.953 | 98.6% | 91.2% | 0.40 |
| Gated multimodal temporal GRU | 0.972 | 100% | 91.2% | 1.27 |

The Isolation Forest learns only healthy windows and uses metrics/logs. Both supervised
candidates use training fault and service labels and metrics/logs/traces. Comparing the
GRU against the supervised reference is essential: improvement over Isolation Forest
alone would conflate architecture, supervision and extra sources. Boosting gives fewer
false alert windows and the same localization accuracy. The GRU gives higher detection
recall. There is no automatic deep-learning winner or final production model yet.

## Temporal architecture and training

Three shared GRUs encode five past service windows for metric, log and trace features.
Learned gates fuse available sources; service mean/max context supports a detection head
and a service-ranking head. Padding masks prevent absent services changing predictions.
Names, case IDs, injection timestamps and root-cause labels are not tensor inputs.
Training labels supervise the loss only. No future windows are used.

Training ran for 12 epochs on the RTX 2000 Ada GPU. The validation-selected checkpoint is
epoch 9. Logs/traces are randomly omitted during training to improve partial-source
behavior. All-source absence produces abstention. The conventional reference learns
current-window features and context without temporal history.

Log inputs are volume/error changes, not semantic text embeddings. Trace inputs are
volume, duration and status-change aggregates, not a learned dependency graph.
Null span status is unknown; available status is a fraction, not always a binary flag.
An audited frontend naming alias is resolved only where the corresponding service exists.

## Limitations and next decision gates

- This test split has already informed development; it is not untouched final evidence.
- Splits hold out runs within systems, not entirely new systems or unknown fault types.
- Five initial minutes are assumed healthy. Live warm-up and schema mapping need validation.
- One-minute windows bound resolution; median benchmark detection delay is 60 seconds.
- False alert windows/hour is not a deduplicated operator alert rate.
- Ranking weights are hypotheses, not calibrated causal probabilities.
- Missing-log F1 is 0.974 but false alert windows rise to 3.40/hour; missing-trace F1 is
  0.969 with 2.33/hour. Robustness has measurable trade-offs.
- Short benchmark healthy periods cannot establish operational reliability.

Next: freeze preprocessing/model artifacts; adapt an external dataset without training on
its fault cases; collect extended healthy workloads and controlled faults in an isolated
live application; compare detection, alert burden, localization, evidence and cost before
selecting a deployment model. Dependency evidence and semantic-log comparisons remain work.

Raw measured reports and checkpoints are under `artifacts/research/`. Training epoch
metrics, modality ablations and the model comparison are inspectable from the dashboard.
