# IncidentLab — Cloud Incident Detection and Evidence-Supported Investigation

## Ready-to-use resume entry

**IncidentLab | End-to-End ML, Cloud Observability & Kubernetes**

**Python, PyTorch, scikit-learn, FastAPI, Docker, Kubernetes (kind), SQLite, GRU, Isolation Forest**

- Built an end-to-end telemetry ML pipeline, processing **49.7M log records and 110.7M spans** across **733 eligible RCAEval cases**, with separate **439/147/147 training, validation and test partitions**.
- Trained and evaluated temporal **GRU** and conventional anomaly-detection models; achieved **0.972 window F1** on the RCAEval development-test partition and documented weak external transfer through independent dataset experiments.
- Implemented **CPU model serving**, a **FastAPI dashboard**, chronological inference and durable **SQLite telemetry ingestion**, with duplicate rejection, restart state and trace-based investigation.
- Deployed a **three-service HTTP testbed on Docker/kind Kubernetes** and evaluated delay, HTTP-error and unavailability faults; operational checks flagged **9/9 controlled trials**, compared with **4/9 for ML alone**.
- Verified **300 held-out observation windows** through arrival-bounded feature/score replay with **zero mismatches**; produced confusion matrices, ROC/PR curves, training curves and reproducible experiment reports.

Use three or four bullets if your resume has limited space. Keep the detector distinction and development-test qualification when shortening.

## Short project description

IncidentLab is an end-to-end ML and observability project for detecting cloud service incidents and investigating them using measured request evidence. It combines large-scale telemetry processing, conventional and temporal anomaly detection, held-out evaluation, CPU inference, a FastAPI dashboard, and a real Docker/kind Kubernetes testbed. Controlled faults reveal how service failures propagate through frontend, checkout and inventory. The project preserves false alarms, capture gaps and weak external transfer rather than claiming production reliability.

## Whole project explained

**Problem:** Cloud requests pass through multiple services. A downstream fault can make several services appear faulty. An alert alone does not identify the cause.

**Data:** Processed RCAEval logs and traces into multimodal model inputs, with case-separated train/validation/test partitions and source provenance. Also investigated OpenStack and external AnoMod data. Large raw data remains on the original college PC; portable processed inputs and checkpoints are retained.

**ML:** Compared Isolation Forest, supervised boosting and a PyTorch temporal GRU. Used validation for model selection and calibration. Preserved checkpoints, predictions and measured test results. Investigated external transfer and retained negative findings.

**Serving:** Loaded frozen models on CPU. Built APIs and a dashboard for saved replay and fresh bounded HTTP demonstrations. Implemented durable chronological observation, duplicate rejection and restart state.

**Deployment:** Containerized frontend, checkout and inventory services and ran them in a dedicated local kind Kubernetes namespace. Collector, model inference and dashboard run on the Windows host in this deployment; the model itself is not a Kubernetes pod.

**Fault evaluation:** Collected fresh cluster healthy training and separate calibration windows before held-out healthy/surge controls and nine fault trials. Recorded 3,413 client requests, 9,680 spans and 420 windows. Used operational rules and ML as distinct detectors.

**Investigation:** Compared timing, errors and dependency traces to confirm trial impact. Distinguished missing request spans from verified outages. Preserved 21 incomplete successful trace chains near pod deletion and control-timestamp proxy limitations.

**Reproducibility:** Preserved original file hashes and source amendments, independently replayed 300 held-out decisions, and exported report figures and exact figure data. A separate real container-restart check recovered all eight unpolled Inventory trace tails with zero duplicate insertions. The current lean CPU test suite passes 75 tests; the optional transformer diagnosis module is excluded.

**Boundaries:** This is completed research plus a controlled local deployment demonstration. External transfer was weak. Long-duration reliability, log rotation, repeated restarts, independent healthy/onset labels, authenticated multi-user serving and company-scale validation remain open. New LLM generation and automatic remediation are disabled.

## Keywords supported by the work

Machine Learning Engineering; End-to-End ML Pipeline; Data Engineering; Telemetry Processing; Multimodal Features; Anomaly Detection; Time-Series Modeling; GRU; PyTorch; Isolation Forest; scikit-learn; Model Calibration; Train/Validation/Test Splits; External Validation; CPU Inference; Model Serving; FastAPI; REST APIs; Docker; Kubernetes; kind; Microservices; Distributed Tracing; Cloud Observability; Fault Injection; Incident Investigation; SQLite; Durable Ingestion; Deduplication; Chronological Replay; Reproducible Experiments; ROC-AUC; Precision-Recall; Confusion Matrix.

Do not add AWS/Azure/GCP deployment, production-scale reliability, reliable LLM diagnosis, automated remediation or ML-only 100% fault recall: those are not demonstrated.

## Interview explanation (about 30 seconds)

“I built IncidentLab to connect ML research with real service behavior. I processed about 50 million logs and 111 million spans, trained a temporal GRU and compared it with conventional models. Then I served frozen models on CPU and deployed three HTTP services in a local Kubernetes cluster. I injected delays, errors and outages and used traces to investigate the impact. Operational checks caught all nine cluster fault trials, while ML alone caught four. I also documented false alarms, missing telemetry and weak external transfer, so the results stay reproducible and honest.”
