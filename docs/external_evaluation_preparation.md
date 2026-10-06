# AnoMod external evaluation preparation

**Status update:** The first frozen-model transfer evaluation has now run on all 24
fault cases. The paragraphs below record preparation-stage history. See
[external results](external_transfer_results.md) for measured coverage, failed transfer
and the current holdout status. No external accuracy or industrial reliability claim
is supported by the run-level annotations alone.

The complete release was already downloaded. This stage reads only the two
author-designated normal reference runs. Fault-run telemetry has not been used for
model fitting, thresholds, checkpoint selection or external performance measurement.
Reading a healthy reference is preprocessing/domain-reference access, not a claim of
completely data-blind zero-shot evaluation.

## Executed healthy-reference audit

| System | Metric records | Log lines | Trace spans |
|---|---:|---:|---:|
| TrainTicket | 217,605 | 34,098 | 8,458 |
| SocialNetwork | 11,015 | 317,055 | 2,060 |

These are healthy-reference counts, not the entire dataset size. The machine-readable
report records source schemas, services, timestamp ranges and per-file SHA-256 hashes:
`artifacts/research/anomod_normal_audit.json`.

Important compatibility findings:

- TrainTicket CPU is exposed as a cumulative seconds counter. Calculate causal,
  per-series rates before window aggregation; do not feed a counter into a utilization
  feature. Counter resets make that interval unavailable.
- Host metrics must not be replicated across every service as if service-specific.
- TrainTicket spans use milliseconds; SocialNetwork spans use microseconds. The
  adapter normalizes durations to microseconds.
- TrainTicket reports an error boolean. Its normalized 0/500 indicator is explicitly
  synthetic and does not pretend to be an observed HTTP status code.
- 1,481 TrainTicket spans in the designated normal run carry an error indicator.
  Normal operation can contain request failures; error presence alone isn't an incident.
- TrainTicket normal traces cover approximately 203 seconds, despite longer metrics.
  Do not fabricate full-period trace coverage or fit a healthy trace baseline from
  zeros across the missing interval.
- SocialNetwork's 2,060 spans have timezone-naive timestamps. The adapter preserves
  local time and leaves epoch seconds unavailable until the source timezone is verified.
- 1,650 SocialNetwork spans lack HTTP status; they remain unknown rather than success.
- TrainTicket log files include startup/continuation lines and mixed timestamp forms,
  including explicit +08:00 offsets. Multiline parsing and time alignment need validation.
- Kubernetes collection reports/events and chaos infrastructure must be excluded from
  model evidence where they could reveal fault scheduling or case identity.

## Implemented adapter boundary

`incidentlab/anomod_adapter.py` exports healthy spans to typed Parquet under
`data/processed/anomod-normal/`. It preserves service and parent span identifiers,
duration units, status provenance and unresolved timestamps. These files are **not yet
complete model-ready windows**. The adapter does not train or run the detector.

```powershell
.\.venv\Scripts\python.exe scripts\audit_anomod_normal.py
.\.venv\Scripts\python.exe -m incidentlab.anomod_adapter
.\.venv\Scripts\python.exe -m unittest discover -s tests -q
```

22 automated tests pass, including duration conversion, unknown timestamps/status,
strict boolean interpretation and causal counter-reset handling.

## Remaining gates before external fault evaluation

1. Verify timezone correspondence, service aliases and collector sampling intervals.
2. Implement same-series counter rates, multiline logs and complete-window aggregation.
3. Define a healthy-reference normalization policy before inspecting faulty predictions.
   This cannot use the first five minutes of a fault run: faults precede the workload.
4. Freeze feature mapping and threshold policy, then evaluate all supported external
   fault cases with explicit exclusions and source coverage. Keep labels out of inputs.
5. Report transfer failure as well as success; do not tune on external fault performance
   and continue calling the same cases untouched final evaluation.

No external accuracy or live deployment result has been produced at this stage.

## Subsequent normalization and window preparation

The author collection code was inspected at revision
`fdece0e54d9a0a0d286ed16f9fe52b493be88277`. Both SocialNetwork metric and CSV trace
exporters call `datetime.fromtimestamp`. All 2,060 healthy CSV span IDs were matched
against original Jaeger microsecond timestamps; all offsets were exactly zero. This
establishes UTC for that healthy collector export. SocialNetwork logs have matching
run wall times; their UTC alignment is explicitly inferred, not an independently
configured container timezone. TrainTicket naive application logs remain excluded.
Source: [author collection scripts](https://github.com/EvoTestOps/AnoMod/tree/fdece0e54d9a0a0d286ed16f9fe52b493be88277).

Implemented `incidentlab/anomod_healthy.py` normalizes:

- 6,166 TrainTicket CPU/memory records across 46 application services. CPU derivatives
  are computed per original label series, with first samples, resets and duplicates
  handled separately. Infrastructure and unrelated metric types are excluded.
- 4,293 SocialNetwork CPU/memory records, excluding monitoring infrastructure. The
  author's CPU query already computes a five-minute rate; no second derivative is taken.
- 317,055 SocialNetwork log events, supporting timestamped records and continuation
  lines. Explicit CamelCase-to-service conversion aligns application names. Nginx's
  differing identities remain separate pending evidence for a merge.
- SocialNetwork trace epoch recovery using the verified healthy collector offset.

`incidentlab/anomod_windows.py` now generates complete epoch-minute windows and healthy
reference statistics: 9 TrainTicket windows (414 service rows) and 19 SocialNetwork
windows (532 service rows). These counts describe the available normal run, not a small
replacement for the full downloaded dataset. Partial boundary minutes are excluded.
All 946 service/window rows have unique keys and finite 18-feature vectors.

The entire designated healthy reference is used for robust location/scale fitting.
This unsupervised reference adaptation must be disclosed in external results. It cannot
also serve as an unbiased healthy false-alert test. Missing dimensions remain explicit:
only CPU and memory are mapped among the eight metric categories. Trace coverage is
short and sparse. No windows from a faulty run are used to define a reference.

```powershell
.\.venv\Scripts\python.exe -m incidentlab.anomod_healthy
.\.venv\Scripts\python.exe -m incidentlab.anomod_windows
```

Reports: `artifacts/research/anomod_healthy_normalization.json` and
`artifacts/research/anomod_window_preparation.json`. Normalized records, healthy windows
and reference statistics are under `data/processed/anomod-normal/`. 25 tests pass.
The original GRU and boosting checkpoint hashes are unchanged.

Before external inference: freeze per-case clock validation, service mapping, exclusions,
reference application and threshold policy. Verify TrainTicket log timezone or explicitly
evaluate that system without logs. Do not claim a completed external evaluation yet.
