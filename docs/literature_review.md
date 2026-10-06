# Paper-grounded design review

Date: 5 October 2026. Proposed project: evidence-grounded incident detection and diagnosis for cloud microservices. This review records what was read and how it changes our implementation; it does not report reproduced research results.

## Institutional research access

Used the user's [BTH database portal](https://bibliotek.bth.se/databases?q=scopus), followed its Scopus entry, and searched `( "log anomaly detection" OR "root cause analysis" ) AND ( microservices OR OpenStack OR Kubernetes )`. Scopus returned 230 documents. Opened AnoMod's document record and followed its publisher link to ACM. Both Scopus and ACM recognized Blekinge Institute of Technology access. The ACM page exposed the full paper, including dataset construction, tables, and limitations. No credentials were requested or copied.

## Selected readings and resulting decisions

| Reading | Mechanism / evidence inspected | Decision for our project |
|---|---|---|
| [RCAEval, WWW 2025](https://arxiv.org/html/2412.17015v2) | Sections 3–5: Kubernetes fault injections; RE1/RE2/RE3; pre-fault telemetry; resource/network/code faults; published RCA baselines and AC@k evaluation. | Acquire the full release. Use whole cases for splits. Separate onset-known RCA reproduction from a detector-triggered pipeline. Compare a conventional ranker before adding neural/LLM complexity. |
| [AnoMod, ACM MSR 2026](https://dl.acm.org/doi/10.1145/3793302.3793324) | Full publisher text: five modalities; chaos injection; EvoMaster workloads; database and code failures; faults active before workloads; modified SocialNetwork logging. | External diagnosis and modality-ablation evaluation. Do not use its case boundaries as proof of live onset detection. Keep code coverage as an optional offline debugging input. |
| [LogLLM](https://arxiv.org/html/2411.08561v2) | Sections III–V: regex parameter masking; BERT representations; projector into Llama 3 8B; three-stage supervised training with QLoRA; chronological splits for several datasets. | Evaluate a semantic log model against Drain-based features. Preserve meaningful error codes/values when masking. Treat its 8B architecture as a candidate with a memory/latency gate; 16GB VRAM alone does not establish trainability. A log-sequence classifier does not establish root-cause accuracy. |
| [Eadro, ICSE 2023](https://zbchern.github.io/papers/icse23c.pdf) | Modal-specific representations, temporal convolutions, gated fusion, dependency graph attention, joint detection/localization. | Test whether multi-source fusion helps over log-only and metric-only methods. Include missing-modality experiments and a graph-free ablation. Attention weights are not causal proof. |
| [AIOpsLab, Microsoft](https://github.com/microsoft/AIOpsLab) | Maintainer deployment and evaluator documentation: live Kubernetes applications, workloads, faults, telemetry, detection/localization tasks. | Use an isolated live testbed after offline baselines. Reproduce failures while collecting observations and score at the detector's actual alert time. |

These are complementary approaches, not a recipe to combine every architecture. We will begin with a reproducible conventional baseline and add one component at a time.

## Research question

Can semantic log representations plus metric/trace evidence improve incident detection and root-cause ranking over conventional log parsing and statistical methods, while maintaining useful latency, calibrated uncertainty, and robustness to missing telemetry?

Testable subquestions:

1. Does semantic log encoding improve unseen-template detection under held-out runs and systems?
2. Does multi-source fusion improve diagnosis, especially for dependency and code faults?
3. Does a bounded evidence-grounded LLM diagnosis stage add measurable value over ranked evidence alone?
4. How much do accuracy, false alerts, latency, and cost deteriorate when telemetry is delayed or missing?

## Evaluation pitfalls

The [September 2026 RCAEval critique](https://arxiv.org/abs/2609.27069) is a preprint, not a result reproduced here. It raises testable concerns about target-service priors and schemas. Include prior-only and random rankers, audit schemas, and test across systems. Never pass case filenames, fault names, injection timestamps, or ground-truth labels to an inference model. Fit preprocessing only on training data. Count independent failures as cases rather than presenting log-line counts as sample independence.

## Scope and evidence limits

LogLLM's preprocessing ablation states that Drain was fitted on the entire dataset. That is a transductive experiment; our deployment-oriented comparison will fit templates on training only and handle unknown templates explicitly. Its computational-cost table also motivates measuring latency rather than assuming an LLM is practical because it reports stronger benchmark F1.

Benchmarks are controlled experiments on running software. They do not establish effectiveness on a company's production traffic. Live tests can demonstrate ingestion, alerting, bounded latency and diagnosis under controlled workloads. A company pilot with longer healthy traffic would be a further validation stage.

See [dataset evidence](dataset_evidence.md) for acquisition sources, licenses and missing modalities, and [project specification](project_specification.md) for the end-to-end implementation gates.
