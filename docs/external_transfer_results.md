# AnoMod frozen-model transfer results

All 24 designed fault runs were processed: 12 TrainTicket and 12 SocialNetwork, totaling 355 complete windows. No runs were silently excluded. Models and healthy-reference statistics were fixed before fault inference. No model was retrained or threshold tuned on the external outcomes.

| Model | Fault runs with alerts | Alert windows |
|---|---:|---:|
| temporal | 3/24 | 44/355 |
| boosting | 2/24 | 5/355 |

**Transfer performance is poor.** These are fault-run alert coverage counts, not verified incident recall. Designed faults are run-level annotations; independently reviewed active-fault window labels, recovery times and a separate healthy test run are unavailable. Precision, F1, false alerts/hour, onset delay and root-cause accuracy are therefore not reported.

The temporal alerts occur in the three SocialNetwork code-stop runs. Boosting alerts occur in two TrainTicket runs. A code-stop alert is not proof the ranked service is the true cause.

## Source coverage

| System | Windows | Metrics present | Logs present | Traces present |
|---|---:|---:|---:|---:|
| TT_data | 171 | 171 | 0 | 56 |
| SN_data | 184 | 184 | 180 | 175 |

Coverage means at least one eligible service in that minute, not complete service coverage. Six metric kinds remain missing. Trace presence requires a usable healthy service reference.

## Why alerts were missed

An additional diagnostic compared score distributions without retraining or changing
thresholds. TrainTicket's temporal model had median score **0.0065**, 95th percentile
**0.4195**, and maximum **0.8900** across fault-run windows. Its frozen threshold is
**0.8923**: the strongest score missed by 0.0023. The supervised model's TrainTicket
95th percentile was 0.4818 with threshold 0.9565. On SocialNetwork, the temporal model
reached the threshold only in the three code-stop runs; the boosting model did not reach
its threshold on any SocialNetwork run.

Healthy-reference inputs score near zero (temporal medians 0.0026 TrainTicket and
0.0007 SocialNetwork). These scores are **in-sample diagnostics**: the same short healthy
runs defined the input scaling. They cannot estimate an independent false alert rate.
They do show that relative feature values center healthy observations as designed;
the weak fault scores are a transfer/calibration problem, not an inactive GPU or failed
serving call.

A separate input-range guardrail calibrated on RCAEval validation's 0.1–99.9 percentile
ranges flags 5/24 fault runs for review at its 99th percentile window cutoff. It misses
the other 19, so it does not solve transfer. It is a development diagnostic only; the
validation set shares systems with model development. See
`artifacts/research/anomod_score_diagnostics.json` and
`artifacts/research/input_shift_guardrail.json`.

This identifies the next correction: implement portable workload, request latency,
error-rate and dependency metrics from verified dataset series; add a semantic log
sequence baseline; compare matched-modality variants; then fit a newly versioned model
using a whole-system transfer protocol and independent healthy calibration runs. Keep
the original checkpoints frozen as the control. Any new model needs a fresh independent
holdout after this AnoMod inspection.

## Interpretation and next experiments

- Only CPU/memory transferred among eight metric kinds; disk/network/request-latency evidence is absent from those slots
- TrainTicket log modality deliberately omitted; diagnosis under this source gap is not the original all-source experiment
- Short trace collection periods and unreferenced services reduce usable evidence
- Healthy full-run scaling differs from five-minute warm-up; reference policy and system shifts are confounded
- Frozen supervised models do not establish cross-system robustness from the RCAEval results
- No new external tuning; these cases become development evidence for future work

SocialNetwork clock audit verified zero offset for every matched raw/CSV span across all 12 fault runs. TrainTicket logs stay excluded. Its error boolean uses a documented synthetic status indicator; this differs from HTTP codes.

Next implement portable workload/latency/dependency evidence, a trained log semantic baseline, and service-level evidence retrieval. Validate feature equivalence before further learning. Future model selection must use a fresh held-out dataset or new controlled trials, since these AnoMod results have now been inspected. Lowering thresholds to improve these counts would require an independent healthy test to assess the added alert burden.

## Reproduce and inspect

```powershell
.\.venv\Scripts\python.exe -m incidentlab.external_evaluation
.\.venv\Scripts\python.exe scripts\analyze_external_transfer.py
```

The external protocol refuses silent changes to its thresholds or checkpoint/reference hashes. Raw policy, case preparation audits, predictions, results and source diagnostics are saved under `artifacts/research/anomod_external_*.json` and `anomod_transfer_analysis.json`. Repeating evaluation is verification, not a fresh holdout.
