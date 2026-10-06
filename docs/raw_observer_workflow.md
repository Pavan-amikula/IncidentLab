# Restart-safe raw telemetry and parameter serving

The native observer connects measured HTTP JSONL to a frozen native model and SQLite.
It retains raw source offsets, partial newline records, future completed events,
prediction history and incident state in one transaction. A crash before commit
leaves the previous offsets intact. A later process reconstructs them from storage.

Duplicate or overlapping windows, collection gaps, source/checkpoint changes,
file replacement, truncation and configured capacity exhaustion are rejected. A
malformed event cannot commit advanced offsets. Restarting the collector does not
make a missed collection period disappear: start a new stream after a gap. File
rotation needs a new explicit stream; seamless rotation is not implemented.

Only `incidentlab-http-v1` input is accepted. This model is calibrated for the
development HTTP app, not arbitrary company services. Joining an existing log file
counts pre-start events as outside the requested windows, without scoring them.

```powershell
# Use an existing running emitter directory and a completed native model run.
.\.venv\Scripts\python.exe -m incidentlab.native_observer --run-id <model-run-id> --source-directory <telemetry-folder> --stream demo --windows 200
```

The command observes ten minutes; it does not create a workload or inject faults.
The native validation runner is one compatible emitter. Do not launch another runner
while its fixed application ports are occupied. The dashboard shows whether an
observer record is current or archived and exposes its selected checkpoint hash.

To start the application, workload and observer together without retraining:

```powershell
.\.venv\Scripts\python.exe -u -m incidentlab.native_runtime --run-id <completed-model-run-id> --minutes 10
# Or use the latest completed model, with a visible VS Code task / terminal:
.\Run-Live.ps1 -Mode Runtime -Minutes 10
```

This bounded demo starts the three HTTP services, sends actual requests at 6/s,
loads the selected frozen checkpoint, and scores new three-second windows through
the durable observer. It injects no faults. Select its `running-app-…` stream in the
dashboard to follow fresh measurements. The default is ten minutes and the limit
is one hour; it closes only its own child processes on completion or interruption.
It requires the application ports to be free. Runtime telemetry, exact source
snapshots and completion status remain under `artifacts/live_runtime/`.

A five-minute execution on the longer run's checkpoint completed 100 chronological
windows with 5,316 validated request events. It produced zero operational warning
windows/incident openings, one ML novelty window and zero dropped workload requests.
Fifteen records preceding the first observation window remained explicitly counted.
Checkpoint, source snapshots and consecutive windows were verified. This is new
healthy traffic through the complete serving path, not a fault-detection result.

`GET /api/native/observers` and `GET /api/native/observers/{stream}/history` read
bounded observer history. The API does not accept arbitrary filesystem paths.

Two consecutive operational-warning windows open a grouped incident; two clear
windows close it. Raw warnings remain available immediately. The grouping rule is
a development policy, not proof of a fault or a tuned production notification budget.
Service hypotheses can be wrong, particularly when workload/collection stops globally.

## Executed checks

The archived checkout-error trial was replayed from actual raw HTTP records with a
new observer object at each of 20 windows. All feature values and detector decisions
matched exactly, offsets survived 19 restarts, and duplicate scoring was rejected.
The SQLite grouping produced one opened and closed incident. This is archived replay,
not fresh accuracy data. A separate observer also followed five minutes of actual
healthy traffic during the longer validation run; its stream is labelled accordingly.

The completed longer run's checkout-error repetition was subsequently replayed for
all 30 windows across 29 object restarts, again with exact feature/decision agreement,
one opened/closed incident and duplicate rejection. Its selected checkpoint is
`118e99295e06b8afe45e4101140143ed1141a4cfe1d8bd670ba8086564d28711`.
The verification script accepts explicit `--run-id` and `--phase` arguments.

Run the checks with `python -m scripts.verify_native_observer` and
`python -m unittest tests.test_native_observer tests.test_incident_groups`.
Reports remain in `artifacts/live/`; observer state is `artifacts/native_observer.sqlite3`.

## OpenStack numeric measurements through HTTP

The original text comparison masks numbers. A separate schema preserves measured
spawn, build, destruction and network-deallocation durations **in seconds**. Healthy
training and calibration use the original split identities. See the [failure analysis](openstack_failure_research.md)
and [measured results](project_status.md). Four previously inspected anomalies remain
development data; restoring them does not establish production reliability.

`POST /api/openstack/parameters` accepts a bounded batch of raw structured duration
events: instance ID, operation, duration, original source timestamp and source line
number. `GET /api/openstack/schema` declares the contract. Labels and extra fields,
nonfinite durations, invalid dates, duplicate/out-of-order lines and checkpoint
changes are rejected. SQLite stores each parameter prefix and prediction atomically.
Later events in a batch cannot change earlier scores. Source timestamp timezone and
fault onset are unspecified; no UTC onset or early-detection claim is inferred.

The residual score uses observed parameters. Isolation Forest decisions abstain until
all four operations are observed, because the model is calibrated mainly on complete
sessions. Missing parameters remain visible and do not become invented zero durations.
Upstream emitters still need explicit VM association; unassigned raw events are not
guessed into a session.

```powershell
.\Run-Live.ps1 -Mode Parameters
.\.venv\Scripts\python.exe -m scripts.verify_parameter_serving
```

Actual HTTP verification sent all 6,037 duration events from normal2 and abnormal
files. Final scores matched the frozen offline comparison exactly for 830 eligible
held-out sessions; 828 were complete for ML decisions. Two sessions had no parameter
records and are explicitly listed. Duplicate submission returned HTTP 409. All
normal2 events were ingested, but the score comparison used only held-out identities.
No labels entered requests. This is complete-file historical replay, not a live
company OpenStack connection.

The API also accepts `calibration_profile: "v4"` for operation-specific upper-tail
delay ranks; V3 remains the default two-sided residual comparison. V4 retains the
original Isolation Forest as a separate diagnostic. Its four-operation correction
stays fixed even when measurements are missing. Tail ranks are not probabilities of
fault, and chronological/censored data do not establish the calibration assumptions.
Changing a checkpoint requires a new stream.

```powershell
.\.venv\Scripts\python.exe -m incidentlab.parameter_calibration
.\.venv\Scripts\python.exe -m scripts.verify_parameter_serving --profile v4
```

Both profiles passed the complete 6,037-event HTTP replay with zero offline score
difference and atomic duplicate rejection. V4 reduced normal2 healthy false alerts
from 13 to 5 while retaining four annotated detections, with precision 0.400. These
are inspected development labels, and the two methods ask different questions.
See [primary-source assumptions](parameter_calibration_research.md).

Storage is bounded at 1,000 streams and 20,000 predictions for each serving store.
Export/archive before exhaustion; evidence is not silently deleted. These single-worker
SQLite prototypes need deployment load testing and lifecycle/retention design before
use as production services.
