# IncidentLab: complete project and interview guide

Read one numbered section at a time. You do not need to memorize every number. Learn the problem, the pipeline, the detector distinction, and the limitations first.

## 1. What is IncidentLab?

IncidentLab is a machine-learning and observability project for detecting service incidents and helping investigate them using telemetry evidence.

**Telemetry** means measurements produced while software runs. Here it includes logs, metrics, and request traces.

**An incident** means service behavior that needs investigation: slow requests, failed responses, or unavailable service.

**An anomaly** means behavior that differs from the model's learned reference. An anomaly is not automatically a fault.

The project connects data processing, model training, validation, testing, serving, deployment, fresh telemetry, controlled faults, and reproducible reporting.

## 2. What problem does it solve?

Requests can pass through several services. A failure in one service can affect others.

Example: Inventory becomes slow. Checkout waits for Inventory. Frontend waits for Checkout. All three appear slow, but the initiating problem may be downstream.

IncidentLab detects unusual behavior, preserves measurements, and helps a person investigate the affected dependency chain. It does not guarantee an automatic causal diagnosis.

## 3. The two main parts of the project

| Part | Purpose | Data and detector |
|---|---|---|
| Research | Compare ML approaches on historical benchmark cases | RCAEval metrics/logs/traces; research Isolation Forest, boosting reference and temporal GRU |
| Operational demonstration | Test detection and evidence collection on real running applications | Measured HTTP requests; separate native Isolation Forest plus operational checks |

These parts use different feature schemas and model checkpoints. Do not say the RCAEval GRU directly powers the one-minute HTTP demo.

## 4. The end-to-end pipeline

1. Acquire benchmark telemetry and preserve its source.
2. Process telemetry into numerical features.
3. Separate entire cases into training, validation and test partitions.
4. Train models and select settings using validation.
5. Evaluate saved predictions and preserve negative findings.
6. Load frozen checkpoints for CPU inference.
7. Run real HTTP services and collect request evidence.
8. Aggregate measurements into chronological windows.
9. Compare ML alerts with operational warnings.
10. Inspect traces to understand propagation and recovery.
11. Replay decisions and export figures/reports.

**Training** learns model parameters. **Inference** applies saved parameters to new input. Opening the dashboard does not train a model.

## 5. What data did you use?

The full RCAEval acquisition contained 735 cases. The existing processing workflow used 733 eligible cases.

It processed approximately 49.7 million log records and 110.7 million spans. The partitions contain 439 training, 147 validation, and 147 test cases.

The project also investigated OpenStack logs and external AnoMod data. These are additional investigations, not evidence of universal transfer.

Large raw collections remain on the college PC. The laptop contains processed inputs, scripts, provenance, saved checkpoints, predictions and reports. Do not claim every original raw record is stored on this laptop.

## 6. What are logs, metrics and traces?

| Term | Meaning | Example |
|---|---|---|
| Log | A recorded software event or message | An HTTP request failed |
| Metric | A numerical measurement over time | CPU activity or latency |
| Trace | Related request operations across services | Frontend → Checkout → Inventory |
| Span | One operation within a trace | Inventory handled this request |
| Trace ID | Identifier connecting operations in one request | Same ID across the service chain |
| Parent span ID | Link from an operation to its caller | Inventory links to Checkout |

The testbed uses an explicit custom HTTP request-event schema. Do not describe it as a verified OpenTelemetry, Prometheus or Grafana integration.

## 7. How did you process the research data?

Research features use 60-second windows. Initial five-minute warm-up data defines reference location and scale. Later values do not redefine that warm-up reference.

The pipeline uses bounded Arrow batches instead of loading all logs and spans into RAM at once. Processed features are stored in Parquet files.

Eight metric-change features cover CPU, memory, disk I/O, socket activity, workload, errors, and two latency measures. Three log features represent volume change, error-pattern change, and log availability. Six trace features represent volume, mean/max duration, status change, trace presence, and status availability.

The temporal model additionally receives metric missingness. That gives 18 values per service/time step. Missing-source information is explicit; missing telemetry is not automatically a zero-valued healthy measurement.

The trace status indicator needs protocol-specific interpretation. The research preprocessing alone does not create a learned service dependency graph.

## 8. Why separate train, validation and test?

- Training: fit the model.
- Validation: select a checkpoint and calibrate thresholds.
- Test: report performance after those choices.

Whole cases are assigned to partitions. Windows from the same incident should not be scattered across train and test.

This reduces leakage risk. It does not prove all possible leakage or benchmark bias has been eliminated.

The RCAEval test is explicitly a development comparison. External data is needed to assess transfer.

## 9. Which models did you compare?

**Isolation Forest:** a conventional anomaly detector fitted to healthy reference behavior.

**Supervised boosting reference:** a label-informed comparison model. It answers whether a conventional supervised approach is competitive under the available labels.

**Temporal GRU:** a PyTorch model that uses a sequence of previous and current telemetry windows.

**OpenStack parameter models:** additional domain-specific experiments with false alarms.

**Optional LLM investigation:** evaluated explanations, including unsupported statements. New generation remains disabled.

## 10. How does the research GRU work?

It uses five consecutive 60-second feature windows per service. Early sequences are padded when less history is available. It uses current and past windows, not future windows.

Three GRU encoders handle metric, log and trace feature groups. Each encoder has hidden size 32. Learned gates combine available modalities. Missing-source masks restrict which modalities and services contribute.

Mean and maximum service representations form detection context. Separate heads produce a detection score and a service ranking.

Case, system and service names are not learned input features. System identity is used for per-system threshold calibration, so do not claim the entire evaluation is independent of system-specific settings.

The model has 15,845 parameters. Training recorded 12 epochs and selected epoch 9 using validation. It was trained on the college GPU and reused on the laptop CPU.

## 11. Why use a GRU and Isolation Forest?

The GRU tests whether temporal and multimodal information helps detection and localization. Isolation Forest provides a simpler reference and supports small healthy-only deployment calibration.

The project compares measured results rather than selecting a model only because it sounds advanced.

The GRU performs strongly on RCAEval development-test data but transfers weakly externally. The small HTTP Isolation Forest misses several controlled faults. Operational checks provide useful additional detection in this testbed.

## 12. What are the research results?

| Detector | Precision | Recall | Window F1 |
|---|---:|---:|---:|
| Research Isolation Forest | 0.972 | 0.743 | 0.842 |
| Research temporal GRU | 0.988 | 0.956 | 0.972 |

The GRU result covers 2,535 windows from 147 development-test cases.

Its confusion counts are 881 true negatives, 19 false positives, 72 false negatives and 1,563 true positives.

The saved GRU report has 100% incident recall and approximately 91.2% top-1 service localization at the first alert on this partition. These are benchmark metrics. They are not universal incident recall or confirmed causal diagnosis.

## 13. What do the evaluation terms mean?

**Precision:** Of the alerts, how many were labeled faults?

**Recall:** Of the labeled fault windows, how many were alerted?

**F1:** A combined precision/recall measure. It is not accuracy.

**False positive:** Alert during a labeled healthy window.

**False negative:** No alert during a labeled fault window.

**Incident/trial detection:** Did the detector flag the incident/trial at least once? This is different from detecting every faulty window.

**Top-1 localization:** Did the first-ranked service match the benchmark root-cause label under the report's definition?

**ROC curve:** Detection versus false-positive rate across score thresholds.

**Precision–recall curve:** Precision versus recall across thresholds. Average precision summarizes score ranking.

**Training curve:** The recorded learning history. It does not prove deployment reliability.

Research curves are separated by system. Correlated windows mean 2,535 windows are not 2,535 independent incidents.

## 14. What happened on external data?

The frozen GRU alerted on 3/24 AnoMod fault runs. The boosting reference alerted on 2/24.

Independent healthy examples and exact onset labels were unavailable for that evaluation. Do not calculate or claim external precision/F1 from those run counts.

Answer to a challenge: “The development-test result was strong, but transfer was weak. I retained that finding because it shows the model needs further domain validation.”

## 15. What are the three running applications?

Frontend receives the request. Checkout processes it and calls Inventory. Inventory performs a stock-like check.

These are real HTTP applications in a controlled testbed. They are not a company's real commerce system.

Recorded request events include timestamps, duration, HTTP status, active request count, trace/span IDs and dependency outcome.

## 16. Which features power the HTTP detector?

The HTTP detector uses four features per service in three-second windows:

1. p95 request latency in milliseconds.
2. Error fraction.
3. Requests per second.
4. Maximum active request count.

The native detector fits a separate 150-tree Isolation Forest for each service. It normalizes using healthy training medians and robust scales. Separate healthy calibration sets a 99th-percentile anomaly threshold.

The cluster experiment fits fresh healthy references for its own deployment. It does not reuse RCAEval features or retrain the GRU.

## 17. What is an operational warning?

It is a warning from explicit checks in addition to the model.

The checks compare latency and error fraction with healthy calibration envelopes and flag missing completed requests for review.

The latency limit is the larger of twice the calibration p99 latency or 50 ms. The error limit is the larger of calibration p99 error fraction plus five percentage points or 5%.

These checks are distinct from Isolation Forest. Never attribute the operational trial result to ML alone.

When no requests are captured, the ML score is unavailable. A “Clear” ML column in that situation does not mean the service has been proved healthy.

## 18. How does investigation work?

The project compares service measurements and request evidence. Failed dependency responses can distinguish propagated errors from local failures.

It prioritizes hypotheses using observed local errors, coverage and affected dependencies. A slow observed downstream dependency should not be ranked below its caller simply because the caller's total latency is higher.

These are evidence-supported service hypotheses. They are not causal probabilities or a guarantee of root-cause correctness.

## 19. What faults did you test?

- Delay: a service adds waiting time.
- HTTP error: a service returns a failed response.
- Unavailability: a service is temporarily taken out of service.
- Healthy control: ordinary successful traffic.
- Surge control: increased traffic without an injected fault.

Controls test false alarms. Fault trials test whether warnings follow measured impact. Recovery observations test whether the service returns to normal after the fault is cleared.

## 20. What were the native and Kubernetes results?

| Experiment | Operational approach | ML alone |
|---|---:|---:|
| Original native HTTP experiment | 18/18 trials | 10/18 trials |
| Laptop Kubernetes validation | 9/9 trials | 4/9 trials |

The native experiment has 22 phases and 1,140 windows. Its operational result includes detection/grouping.

The Kubernetes validation has 13 phases and 420 windows: 60 healthy training, 60 calibration and 300 held-out scored windows. It records 3,413 client requests and 9,680 spans, with zero dropped workload requests.

Cluster numbers are trial flags, not nine independently grouped incident diagnoses. The two experiments differ in deployment/calibration and are not a paired before/after model improvement.

Healthy control had zero operational or ML warnings. Surge control had zero operational warnings but three ML warning windows. All cluster delay trials were missed by ML.

## 21. Why did the graph show lower latency during errors?

A failed request can finish quickly. Lower latency is not always better.

For checkout errors, Checkout and Frontend can both report errors. Inventory may have zero requests because Checkout stopped the chain before calling it.

For frontend errors, Checkout and Inventory may receive no requests.

Do not interpret every missing downstream request as a crashed downstream service. Inspect the trace path and collector evidence.

## 22. How did you verify replay and collection?

Collector state is durable in SQLite. Unique service/span identifiers reject duplicate events. Recorded arrival cutoffs allow replay to use only evidence available at that time.

The 300 scored cluster windows reproduced their saved features, scores and decisions with zero mismatches. This checks replay reproducibility; it does not prove the decisions were correct.

Capture review found 21 successful chains with missing spans near pod deletion and 14 missing parent links. A successful client request does not guarantee complete telemetry.

A separate same-pod Inventory container restart recovered all eight unpolled Inventory trace tails from previous-container logs. Repeat polling added zero duplicates. All 32 check requests succeeded.

One successful restart does not establish log-rotation or repeated-restart completeness.

## 23. Are the fault labels exact?

Cluster labels use control-command completion times as proxies. Real impact can start or end at a different moment.

Boundary-crossing windows are excluded from proxy-window matrices. Actual request traces confirmed trial impact, but every window has not received an independent human onset label.

Answer to a challenge: “I distinguish command-time proxies from observed request impact and report capture gaps before interpreting metrics.”

## 24. Where is Kubernetes?

Your actual local deployment has this hierarchy:

```text
Windows laptop
├── CPU inference, collector and FastAPI dashboard
└── Docker Linux engine
    └── incidentlab-control-plane  [kind Kubernetes node container]
        └── incidentlab-testbed   [owned namespace]
            ├── frontend pod
            ├── checkout pod
            └── inventory pod
```

Kubernetes runs inside the Docker node container. It is not a separate ordinary desktop application.

The project's kind cluster is separate from Docker Desktop's optional built-in Kubernetes cluster. Do not enable that feature merely to use this project.

Open the dashboard's **Kubernetes results** tab and find **Where is Kubernetes?** The live table shows pod readiness and container restarts. The graphs below it remain archived experiment measurements.

To inspect the actual pods yourself:

```powershell
kubectl --context kind-incidentlab -n incidentlab-testbed get pods
```

The context identifies the cluster. The namespace identifies the project's isolated area. A pod is Kubernetes' application execution unit. A Deployment manages its desired replicas. A Service supplies a stable application network endpoint. Readiness indicates whether the application is ready to receive traffic; it is not proof of model quality or perfect application reliability.

## 25. Must Docker be open every time?

| Activity | Docker engine needed? |
|---|---|
| Read saved research or Kubernetes results | No |
| Download figures or reports | No |
| Run the one-minute local HTTP demo | No |
| Collect fresh requests from Kubernetes pods | Yes |
| Run cluster Quick/Validate or build/deploy containers | Yes |

The dashboard's Python server must run to use its browser interface.

For cluster work, start Docker Desktop and wait for **Engine running**. You can minimize the window. Closing a window is different from quitting Docker Desktop; quitting or stopping its engine prevents kind cluster workloads from running.

The dashboard will show cluster status unavailable if the engine is stopped. Saved results can still be read. After starting Docker again, check pod readiness before starting a workload.

## 26. Is this a cloud deployment?

It is a cloud-relevant microservice and Kubernetes project running locally on the laptop.

It has not been deployed to AWS, Azure or GCP. Do not add a public-cloud provider to the resume unless you later actually deploy and verify it there.

In this deployment, the applications are Kubernetes pods. Inference and dashboard run on Windows. Do not claim the model server is Kubernetes-hosted.

## 27. Is it truly real time?

The HTTP demo collects fresh measurements in three-second windows and updates the dashboard. It is a near-real-time bounded local demonstration.

Saved research and cluster results are replay, not a current collector. Ready Kubernetes pods alone do not mean new requests are being generated or archived.

Cluster inference p95 measured 52.52 ms. Window-close-to-decision p95 measured 6.28 seconds. Those are different timing units; 52.52 ms is not the complete end-to-end alert delay.

No latency guarantee for production is claimed.

## 28. Why CPU on the laptop?

The laptop has no NVIDIA GPU. Frozen checkpoints can run on CPU, and bounded workloads avoid repeating expensive training or downloading large models.

The CPU configuration uses PyTorch 2.11.0+cpu with two numerical threads. Portability replay differences from saved GPU predictions were below 0.000002.

The cluster node was configured with two CPUs and 4 GiB. Measured samples saw a 928 MiB node memory maximum. That sampled maximum is not a guaranteed peak or a minimum hardware requirement. Docker and Windows add their own overhead.

## 29. Why is the LLM disabled?

The explanation experiments included unsupported statements. An accepted explanation was not necessarily a correct diagnosis.

The project preserves the saved evaluation but disables new generation on the laptop. It does not declare a reliable final LLM diagnosis model or allow automatic remediation.

This is a deliberate evidence-based limitation, not a feature to conceal in an interview.

## 30. What failed, and how did you debug it?

- Cluster bootstrap encountered a cgroup compatibility issue. The local compatibility configuration is documented.
- An HTTP framing problem was corrected with explicit Content-Length and a regression check.
- Pod termination grace initially obscured unavailability impact. A one-second grace was configured only for the owned testbed.
- Two extra checks did not trigger a container restart. The corrected check stopped the inspected owned container through the node runtime and verified previous-log recovery.
- The built-in LaTeX compiler failed with a platform-directory error. A readable two-column PDF was created; editable IEEEtran source is preserved.

Earlier attempts and negative results are retained. Debugging changed the implementation, not the historical evidence.

## 31. Is the project finished?

**Yes: research plus the controlled end-to-end laptop demonstration is complete.**

Completed: processing, trained checkpoints, validation/test evaluation, CPU inference, dashboard, fresh HTTP demo, actual Docker/kind deployment, controlled cluster trials, replay/capture review, one restart check, figures, report and resume description.

**No: it is not a production-ready enterprise monitoring platform.**

Open industrial work includes stronger external evaluation, long-duration testing, log rotation/repeated restarts, authentication, multi-user deployment and larger deployments.

The current lean CPU suite passes 75 tests. The original full college environment passed 80 tests; the laptop excludes the optional transformer diagnosis module. These are different suites, not an unexplained loss of five tests.

The editable report uses IEEEtran conference style. Its LaTeX compilation is unverified on this host due to the compiler error. The supplied PDF is a reviewed readable fallback, not a published IEEE paper.

## 32. How do I demonstrate it?

1. Start the dashboard using `Start-Laptop.ps1` from the project directory. Keep its server running.
2. Open `http://127.0.0.1:8768/` and choose **Live demo**.
3. Select healthy traffic. Start the one-minute demo. Explain requests, latency and errors.
4. Run the Inventory delay demo. Watch latency rise around 20 seconds and recover around 40 seconds.
5. Compare ML and rule warnings. Read request evidence before naming a cause.
6. Open Kubernetes results. Explain that the trial charts are saved measurements. Select a fault phase and compare an alert window with a recovered window.
7. Open Report figures. Explain the GRU confusion matrix and evaluation boundaries.

For showing current Kubernetes pods, keep Docker's engine running. For steps involving only native demo/saved replay, Docker is not required.

Do not rerun the 21-minute cluster validation solely to answer an interview question. Use the saved evidence unless a fresh experiment is specifically needed.

## 33. What should I say about my contribution?

Describe work you understand and can explain: processing pipeline, evaluation protocol, model comparisons, serving/collection, fault experiments, debugging, evidence review and reproducible reporting.

Attribute RCAEval to its creators. Do not claim to have created its dataset, invented GRU or Isolation Forest, or run company-production incidents.

If asked about development assistance, describe the tools and assistance used honestly. Ownership of the project does not mean every algorithm or line of code was invented without help.

## 34. Where is the evidence?

| Question | Project evidence |
|---|---|
| Research inputs and partitions | `data/processed/` and split manifests |
| GRU training and selection | `artifacts/research/temporal_training_report.json` |
| GRU test results | `artifacts/research/temporal_test_report.json` |
| Original native experiment | `artifacts/live/20261005T202755-0e2c27/` |
| Completed cluster validation | `artifacts/kubernetes/20261006T141939-0fc666/` |
| Replay/capture summary | `artifacts/laptop_validation/final_summary.json` |
| Separate restart check | `artifacts/kubernetes/infrastructure-20261006T194017-f133aa/` |
| Figures and exact data | `artifacts/report_figures/` |
| Laptop execution details | `docs/laptop_execution_20261006.md` |
| Latest delivery status | `docs/final_delivery_20261006.md` |
| Resume text | `docs/resume_project_description.md` |
| Report | `reports/IncidentLab-IEEE-readable.pdf` and `.tex` |

Original handoff notes can still say Kubernetes was pending. They record the old college-PC status. Use the dated laptop execution and final delivery documents for the latest completed work. Historical paths remain provenance.

## 35. Answers to common challenges

**“Why not claim 100% ML detection?”**

Because operational detection combines rules and coverage checks. ML alone flagged four of nine cluster trials.

**“Why can a model with F1 0.972 miss live faults?”**

Those are different detectors, features, data domains and deployments. The GRU benchmark F1 is not the live HTTP Isolation Forest result.

**“Does an alert prove the root cause?”**

No. It raises a hypothesis. Request traces, dependency responses and capture review supply evidence.

**“What is the most important negative result?”**

Weak external transfer. It shows why a benchmark score cannot establish universal reliability.

**“What is the most important engineering check?”**

Arrival-bounded replay reproduced 300 held-out decisions with zero mismatches. Collection still has known deletion gaps.

**“What would you improve next?”**

Independent labeled deployment evaluation, longer runs, robust capture through log rotation/repeated restarts, and secure multi-user serving.

**“What is useful about it now?”**

It is an executable demonstration of telemetry ML, operational detection, fault propagation, evidence collection and reproducible investigation. It is suitable for a project presentation and technical interview.

## 36. Your 30-second introduction

“IncidentLab connects ML research with real service behavior. I processed about 50 million logs and 111 million spans, compared conventional models with a temporal GRU, and served saved models on CPU. I then deployed three HTTP services in a local Kubernetes cluster and tested delays, errors and outages. Operational checks flagged all nine cluster fault trials; ML alone flagged four. I used request traces and chronological replay to review the results, while preserving false alarms, capture gaps and weak external transfer.”

## 37. The four facts to remember first

1. **Purpose:** detect unusual service behavior and investigate it using evidence.
2. **Research result:** GRU window F1 0.972 on RCAEval development-test data.
3. **Cluster result:** operational 9/9; ML-only 4/9 controlled trials.
4. **Status:** completed research and laptop demo; industrial reliability remains unverified.
