# Research basis and experiment plan

Reviewed 2026-10-05. Primary sources were available openly, so institutional browser
access was not required for this first iteration. A broader literature review remains.

## Initial sources

1. He et al., **Drain: An Online Log Parsing Approach with Fixed Depth Tree**, ICWS 2017.
   Implementation and paper link: https://github.com/logpai/Drain3
   Drain3 supplies streaming template mining. We learn templates only on training
   observations, then use `match` during calibration and evaluation to avoid adapting
   the parser to held-out anomalies.
2. Du et al., **DeepLog: Anomaly Detection and Diagnosis from System Logs through Deep
   Learning**, CCS 2017, DOI 10.1145/3133956.3134015.
   Author-hosted paper: https://www2.cs.utah.edu/~lifeifei/papers/deeplog.pdf
   DeepLog models sequences of normal log events. It motivates a later sequence-model
   comparator; our IsolationForest baseline is not an implementation of DeepLog.
3. **Log-based Anomaly Detection with Deep Learning: How Far Are We?**, 2022.
   https://arxiv.org/abs/2202.04301
   This study examines multiple models and datasets; its experimental scope motivates
   evaluating generalization and simple alternatives instead of assuming DL superiority.
4. OpenTelemetry demonstration: https://opentelemetry.io/docs/demo/
   A realistic instrumented microservice environment is a candidate for later integration.

## Research question

Can selective LLM diagnosis improve evidence-supported fault diagnosis over a
conventional pipeline, without unacceptable alert burden, processing delay, or cost?

## Scope of the first build

Four illustrative services: gateway, reservation, worker, database. Observations are
synthetic; a windowed pipeline runs through actual parsing, model scoring, API storage,
and UI display. No service outage is physically induced by the demo controls.
An IsolationForest alone may miss features constant during healthy training. A separate
template-novelty trigger handles unseen messages; reports retain ML-only alert counts
so the contribution of this extra trigger is visible.

## Planned fair comparison

- Rules-only diagnostic/detection baseline.
- Frozen Drain3 + conventional ML, with novelty ablation.
- LLM-only using bounded identical log evidence.
- Hybrid conventional detection + selected evidence + LLM diagnosis.

Keep model versions, prompts, retrieval contents and sampling parameters recorded.
Evaluate held-out complete runs and held-out fault configurations. Additional telemetry
must be treated as a separate experimental factor, not a model-only improvement.
Include benign traffic changes, format changes and collection failures. Fault injection
metadata is stored separately from observations; the inference process cannot read labels.
Evaluate diagnosis on false alerts as well as genuine incidents; require evidence pointers,
measure unsupported explanations, and allow abstention. No automatic repair in initial scope.

## Gaps before thesis-level claims

Real cluster collection and fault scenarios; traffic diversity; realistic label ambiguity;
unseen faults; model persistence/versioning; calibrated uncertainty; incident grouping;
end-to-end latency; throughput and resource limits; human evaluation of diagnostic utility.

## Second iteration: explicit stages and a real-log check

Added separate prepare/train/validate/test commands, saved checkpoints, checksummed
datasets, per-window predictions, and a server that only loads a calibrated model.
A node-grouped BGL 2,000-line experiment uses TF-IDF + IsolationForest, excluding
the anomaly label prefix, node IDs, and timestamps from features. The initial real-log
baseline misses all 20 held-out anomalies. This negative finding is not corrected by
tuning against the test set. It motivates validation-based model comparisons on
a larger dataset, followed by a genuinely independent evaluation.

Source: https://github.com/logpai/loghub
Zhu et al., *Loghub: A Large Collection of System Log Datasets for AI-driven Log
Analytics*, ISSRE 2023. Dataset is provided for academic/research use.
