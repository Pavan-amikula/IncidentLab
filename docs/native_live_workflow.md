# Fresh live telemetry without administrator access

IncidentLab now has an executable native HTTP testbed in addition to its full-data
research pipeline. Three separate Python service processes receive real network
requests on localhost ports 8891–8893: frontend → checkout → inventory. Each request
records measured completion time, HTTP status, dependency response, span/parent IDs
and a shared trace ID. The workload runner uses a bounded pool; it archives dropped
workload requests. The runner terminates only the child processes it owns.

This is a development testbed for application faults, not Kubernetes orchestration
or a production workload. It does not replace the complete RCAEval/AnoMod/OpenStack
datasets. WSL/Docker installation still requires an administrator on this machine.

## Run in the visible VS Code terminal

Open the `dl project` folder. Use **Terminal → Run Task → Live. Collect healthy runs,
train, calibrate and test real HTTP faults**, or run:

```powershell
.\Run-Live.ps1 -Mode Collect -Seconds 120
```

The thirteen phases take approximately 26 minutes plus process startup. Keep seconds a
multiple of three. Training and validation each collect a fresh healthy service run,
with loads of 3, 6, 12 and 24 requests/s. The model is frozen before eleven new trials:
normal, benign surge, and delay, local HTTP errors and actual termination/restart
at each of frontend, checkout and inventory. Each fault trial begins healthy,
injects a bounded fault at 30% of the run and recovers at 70%. Exact observed control
timestamps are archived separately and never passed to the detector or LLM.

For longer validation, use the VS Code task **Live. Longer validation (57 minutes)**,
or run this explicit command:

```powershell
.\.venv\Scripts\python.exe -u -m incidentlab.native_experiment --seconds 90 --healthy-seconds 300 --control-seconds 600 --repetitions 2 --window 3 --healthy-loads --fault-targets frontend checkout inventory
```

This collects five minutes each for healthy training and calibration, ten minutes
each for independent healthy and surge controls, and two 90-second repetitions of
each of nine target/fault combinations. There are 22 phases and 1,140 three-second
windows. Startup adds time. These are repeated known fault families on one controlled
application; they are not unseen-system validation or hours of production exposure.

## Training, calibration, testing and serving

`native_experiment.collect` collects raw request events. `live_monitor.aggregate`
uses only already-completed requests for three-second service windows. Features are
p95 latency, error fraction, throughput and maximum active requests. `live_monitor.fit`
fits one healthy-only Isolation Forest per service, plus robust training scaling.
Separate healthy validation supplies thresholds and latency/error envelopes.

`live_monitor.score` runs online during test collection. It keeps ML novelty and
operational warnings separate. A healthy workload increase can be novel without a
failure. Constant healthy error features are poorly handled by an Isolation Forest;
the independent HTTP-error check covers that known algorithm limitation. Missing
completed requests produce a review request, not proof of a service outage.

This model uses `incidentlab-http-v1`. The RCAEval temporal GRU uses a different frozen
18-feature schema and is **not** fed these raw HTTP values. Silent schema substitution
would invalidate its scores.

The dashboard at [localhost:8768/live](http://127.0.0.1:8768/live) polls collector
progress, shows measured service windows, archived evidence and separate ML/operational
results. The research server also serves `/api/live/status`, `/api/live/trial/{phase}`,
and `/api/live/diagnose`. All servers bind to localhost; do not expose them publicly.

## Grounded investigation and optional LLM

Trace evidence distinguishes a locally returned error from a propagated downstream
failure. Ranking reduces the priority of a slow caller whose observed dependency is
also affected. This is an investigation heuristic, not causal proof.

A pinned local Qwen model can propose a bounded structured explanation. It sees at
most two selected request records per service, plus retrieved fixed investigation
steps. The hybrid variant also receives measured warnings. It receives no run name,
fault schedule, fault label or injected target. Generated service names, evidence IDs,
schema and runbook IDs are validated. Rejections abstain and retain the raw model
output for analysis. Structural validity does not establish semantic support.
Hybrid explanations cannot override measured warning state, and citations must
refer to the proposed service. A contradiction causes abstention.

Policy V2 additionally receives service-window measurement citations (`M…`) distinct
from request/span citations (`E…`). It treats successful-but-slow requests as potential
review evidence, and abstains from service attribution when every source is absent.
The longer run retains a V2 source/prompt manifest frozen before its fault onsets.
Run `python -m incidentlab.llm_live_evaluation --run-id <completed-run-id> --policy-version v2`
after collection. This verifies the frozen implementation before generating sampled
log-only and hybrid comparisons. Accepted structure still needs semantic review.

The initial 0.6B experiment performed poorly; it is preserved as development evidence.
A 1.7B candidate and revised prompt are measured separately. Neither is an automatic
remediation engine or the default incident detector.

An [explanation-support spot check](explanation_support_review.md) found unsupported
causal and failed-request claims even in structurally accepted outputs. The archived
outputs remain unchanged. Citation membership and warning consistency do not verify
free-text meaning, and the LLM is not declared a reliable final diagnosis model.

## Artifacts and reproduction

Every run lives under `artifacts/live/<timestamp-id>/`: source hashes, raw service
JSONL, training/calibration windows, separate control schedules, frozen model, online
predictions and held-out report. `latest_report.json` is a convenience copy, not a
replacement for the immutable per-run evidence. New runs do not overwrite older runs.
The collector reads incrementally, validates the strict event schema, bounds buffers,
and counts late events. Exact source snapshots are retained for the balanced run.

```powershell
.\Run-Live.ps1 -Mode Inspect
.\.venv\Scripts\python.exe -m incidentlab.llm_live_evaluation --run-id <completed-run-id>
.\.venv\Scripts\python.exe -m unittest tests.test_live_monitor -v
```

Fault transition windows are excluded from scored intervals. Reports distinguish
fault-window recall, incident detection, delay and false **windows** per healthy hour.
Those false-window rates are not deduplicated operator incidents. Short healthy
periods and one trial per fault cannot establish stable production reliability.
Inference time excludes collection; newer predictions separately record the delay
from window close to decision. A sample of LLM windows is not a full-stream alert rate.

Kubernetes deployment, infrastructure faults, substantially longer independent healthy controls and
company-specific validation remain release gates. Cluster manifests and scoped fault
commands are prepared in [deployment instructions](../deployment/KUBERNETES.md);
they have not been executed on a cluster.
