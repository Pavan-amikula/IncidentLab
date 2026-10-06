# Dataset evidence for an operational cloud incident project

Research date: 2026-10-05. Scope: primary dataset papers, maintainer repositories, and authoritative download records. This note does not claim that any dataset was downloaded, validated locally, or used for training by this research task. A small dataset used for debugging is not an adequate thesis evaluation.

## Recommendation

Use the **complete RCAEval RE2 and RE3 suites** for incident diagnosis, **complete OpenStack Loghub logs** for a separate cloud-infrastructure log anomaly benchmark, and **AnoMod** as an independent multi-source evaluation. Add a live instrumented test deployment for real-time collection and fault-injection experiments. This is a proposed design, not a result established by the papers. Avoid claiming production effectiveness from any benchmark alone.

Millions of lines are not millions of independent failures. The independent unit for diagnosis is a failure case or experimental run. RCAEval is materially better matched to labeled root-cause diagnosis than BGL, although all selected resources have representativeness limitations.

## RCAEval: main diagnosis benchmark

The WWW 2025 paper describes 735 controlled failures: RE1 has 375 metric-only cases; RE2 has 270 multi-source cases; RE3 has 90 code-fault cases. Systems are Online Boutique, Sock Shop, and Train Ticket. Faults are injected into Kubernetes deployments; workloads are 10–200 requests/second. Normal telemetry precedes injected faults. This is data emitted by running systems under controlled faults, not an archive of naturally occurring commercial incidents. Labels identify root-cause services and indicators. The paper provides AC@k and Avg@k evaluation and conventional baselines. [Paper, sections 3–4](https://arxiv.org/html/2412.17015v2)

Full original archives total 5.2 GB. RE2-OB is 1.2 GB, RE2-TT 2.8 GB, RE2-SS 245.6 MB; RE3 files total roughly 534 MB. The original record reports millions of log lines and trace observations; exact counts should be recomputed from acquired files. Download files have published MD5 checksums. [Original dataset record](https://zenodo.org/records/14590730)

The current maintainer Parquet release totals 3.44 GB and declares MIT licensing. Its 735-row `train` viewer is a **case index**, not a defensible training split. It exposes timestamps, repetitions, fault type, root-cause service, row counts, and modality availability. Sock Shop has no traces. One RE2-TT case has no logs. RE3 is not a balanced fault/service grid. Audit these conditions rather than silently dropping cases. [Maintainer dataset card](https://huggingface.co/datasets/phamquiluan/RCAEval)

Concrete acquisition options:

- [All maintainer Parquet files](https://huggingface.co/datasets/phamquiluan/RCAEval/tree/main), preserving the revision and `cases.parquet` index.
- [RE2-OB.zip](https://zenodo.org/records/14590730/files/RE2-OB.zip?download=1), MD5 `b9e23f8842c404b396ffd2becff15de4`.
- [RE2-TT.zip](https://zenodo.org/records/14590730/files/RE2-TT.zip?download=1), MD5 `a7fbcd1ada406067dcc50771ae398408`.
- [All original archives](https://zenodo.org/records/14590730), including RE2-SS and RE3; acquire complete suites rather than a hand-picked successful case.

The repository recommends Ubuntu, eight CPU cores, 16 GB RAM, and approximately 50 GB disk space; original archives reportedly expand to approximately 38 GB. This is a planning estimate from the maintainers, not a local measurement. [Code and reproducibility documentation](https://github.com/phamquiluan/RCAEval)

## OpenStack: separate infrastructure-log benchmark

The complete Loghub OpenStack dataset contains **207,820 lines, 58.61 MiB raw**. It is labeled and much larger than the 2,000-line parsing example, but still a bounded historical experiment. Loghub grants research/academic access and asks for attribution. Do not infer unrestricted commercial data redistribution from that statement. [Dataset inventory and usage terms](https://github.com/logpai/loghub)

It was generated on CloudLab, with normal operation and injected failures; cite DeepLog (ACM CCS 2017) and Loghub (IEEE ISSRE 2023). It is appropriate for testing cloud log processing, not sufficient by itself for general multi-source root-cause ranking. [OpenStack provenance](https://github.com/logpai/loghub/blob/master/OpenStack/README.md)

The example uses `openstack_normal1.log`, `openstack_normal2.log`, and `openstack_abnormal.log`; it learns event IDs from normal1 and processes separate normal/abnormal tests in one-minute windows. File-level normal/abnormal organization must not be misrepresented as per-line root-cause truth. Inspect fault timestamps and labels before deciding how to score windows. The example is implementation guidance, not an immutable evaluation standard. [Original preprocessing example](https://raw.githubusercontent.com/nailo2c/deeplog/master/example/preprocess.py)

Complete archive: [OpenStack.tar.gz](https://zenodo.org/records/8196385/files/OpenStack.tar.gz?download=1). Zenodo API metadata verified: **5,394,691 bytes compressed**, MD5 `66bd42c07837a094d9b0ea2d036b5713`; [direct content endpoint](https://zenodo.org/api/records/8196385/files/OpenStack.tar.gz/content). Verify acquired bytes and extracted contents before reporting acquisition success.

## AnoMod: complementary 2026 benchmark

AnoMod is accepted at MSR 2026. It covers SocialNetwork and TrainTicket with logs, metrics, traces, API responses, and code coverage. Table 3 reports 444.6K TrainTicket log lines and 3,958.5K SocialNetwork lines. The paper describes 24 designed anomaly cases across resource, service, database, and code levels. These are controlled chaos experiments with EvoMaster workloads. Limitations include only two systems and modified SocialNetwork logging. Failure activation occurs before workload execution, so it does not automatically provide realistic onset-detection episodes. Code coverage may be useful for offline debugging but unavailable in production streams. [Paper and dataset construction](https://arxiv.org/html/2601.22881v1)

Zenodo API metadata verified: `AnoMod.zip`, **201,917,396 bytes**, MD5 `30c5835190c3550c5efc34d6be4f9238`, dataset license **CC BY 4.0**. [Author deposit](https://zenodo.org/records/18342898), [direct archive](https://zenodo.org/api/records/18342898/files/AnoMod.zip/content). The collection code repository declares MIT; keep code and dataset licenses separate. [Author repository](https://github.com/EvoTestOps/AnoMod)

## Other candidates and reasons not to silently substitute them

| Candidate | Verified characteristics | Decision / unresolved details |
|---|---|---|
| Nezha (FSE 2023) | Fault-free and faulty phases; OnlineBoutique and TrainTicket; logs, metrics, traces, service and inner-service labels. [Author README](https://github.com/IntelligentDDS/Nezha/blob/main/README.md) | Useful external diagnosis benchmark. Exact current size and case count still require a file manifest; avoid quoting conflicting counts from downstream projects. |
| LEMMA-RCA | IT and OT domains; cloud data contains metrics and logs. Product Review experiments last at least 49 hours; paper describes simulated fault scenarios. [Paper](https://arxiv.org/html/2406.05375v2) | Valuable longer-duration evaluation. Licensing conflicts: website says CC BY-ND, README introduction says CC BY-NC while its license section says CC BY-ND. Resolve authoritative dataset terms before redistribution. [Website](https://lemma-rca.github.io/), [repository](https://github.com/KnowledgeDiscovery/rca_baselines). |
| AIOps Challenge 2020 | Failure labels, business/infrastructure metrics and traces; stage one downloadable, stage two unavailable; noncommercial usage restriction. [Organizer repository](https://github.com/NetManAIOps/AIOps-Challenge-2020-Data) | Poor main choice for a log-focused comparison because no log modality is listed. Exact full size not verified. |
| AIOps Challenge 2022 | Organizer teaching material identifies microservice shopping failure identification/classification. [NetMan course](https://netman.aiops.org/~peidan/ANM2024/Week1/AIOpsCourse2024.pdf) | Original repository/download and license not verified. Do not treat a third-party mirror as authoritative without provenance. |
| GAIA | Maintainer reports 6,500+ metrics, 7M logs, traces and two weeks; later August addition omits traces. [Maintainer README](https://github.com/CloudWise-OpenSource/GAIA-DataSet) | Need a release-specific modality audit. README says Apache 2.0 while GitHub recognizes GPL-2.0; resolve this inconsistency. Injection records embedded in run logs must be excluded from model input. |
| PetShop | 41 components, 68 annotated performance injections, metric-only; dataset CC BY 4.0, code Apache 2.0. [Amazon Science repository](https://github.com/amazon-science/petshop-root-cause-analysis) | Useful metric-RCA external test, not a log/LLM comparison backbone. Repository is archived. |

## Audits and evaluation protocol we must implement

Proposed protocol:

1. Inventory every acquired case: modalities, row counts, timestamp units/ranges, schema, root-cause annotations, and missing files. Publish manifest plus hashes.
2. Remove case-path/fault-name metadata, injection controller logs, label files, and other ground-truth artifacts from features and LLM prompts.
3. Split by whole run/case; keep all windows from a case together. Fit log templates, normalizers and thresholds using training/validation only.
4. Use held-out repetitions for in-system evaluation, held-out fault types for unknown-fault tests, and held-out systems for transfer. Declare the different question each split answers.
5. Separate oracle-onset RCA reproduction from end-to-end detection. The live system must determine alert time itself, and only consume observations available at decision time.
6. Include random and **service-prior-only** rankers, error-rate heuristics, a conventional reference baseline, LLM-only, and hybrid methods. Compare feature/model complexity using identical data access.
7. Measure false alerts per healthy hour, detection delay, incident recall, top-1/top-k diagnosis, evidence faithfulness, latency, throughput, and cost. Add long healthy runs; benchmark case windows alone do not establish a production false-alert rate.

A **September 2026 preprint**, not verified here as peer-reviewed or reproduced, alleges that RCAEval's limited fault-target services create a strong service-prior baseline and that schema inconsistencies can affect results. Treat it as an audit hypothesis, not established rejection of the benchmark. It strengthens the case for prior-only baselines, schema checks, cross-system evaluation, and a second dataset. [Preprint](https://arxiv.org/abs/2609.27069)

For real-time validation, AIOpsLab can deploy microservice environments, inject faults, generate workloads, collect telemetry, and evaluate agents, including a local kind cluster. It is MIT-licensed. It is a testbed, not proof of readiness for commercial deployment. [Microsoft AIOpsLab](https://github.com/microsoft/AIOpsLab)
