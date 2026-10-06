# Sequential research-model serving

The research server now exposes `POST /api/stream/windows`, `GET /api/stream/schema`
and `GET /api/stream/{stream}/history`. The input is the exact 18-value ordered
feature vector expected by the frozen temporal model. Schema discovery returns the names.
This is a normalized-feature boundary; it does not accept raw OTLP telemetry or claim
to be a working collector. A production adapter must reproduce the frozen causal
normalization, duration units, source availability and healthy reference calculation.

Each input identifies a stream, a benchmark threshold profile (`ob`, `ss`, `tt`), an
epoch-minute end timestamp and service vectors. Profiles select research thresholds;
they are not calibrated for an arbitrary company deployment. Fault labels and extra
fields are rejected. Values must be finite and nonnegative, services unique, and
availability fields within their declared ranges.

SQLite persists the last five causal windows and prediction history. A lock serializes
sequence transitions and GPU inference. Serve this local prototype with one worker.
Duplicates, out-of-order windows, profile changes and missing whole windows are rejected.
After a collection gap, begin a new stream only after a fresh healthy warm-up. All-source
absence abstains. The local limits are 1,000 streams and 10,000 archived predictions;
capacity exhaustion refuses new work rather than silently deleting evidence.

## Executed verification

`scripts/verify_streaming.py` submitted 19 archived feature windows through actual HTTP
and checked the same alert decisions as offline replay. Maximum score difference was
0.000238, within the declared 0.001 tolerance for different CUDA batch kernels. Local
HTTP p50 was 34 ms and p95 42 ms, including SQLite commits. These exclude source
collection, raw normalization and remote transport; they are not end-to-end production
latencies. Duplicate submission returned HTTP 409. The report is saved as
`artifacts/research/streaming_verification.json`.

19 automated tests pass, covering source absence, padding, service permutation, causal
preprocessing, label rejection, durable restart and rejection without state mutation.

## Infrastructure gate

Linux/WSL and Docker are not installed. The WSL launcher being present does not provide
a container runtime. Kubernetes collection, a real workload generator and isolated fault
injection have not run. Environment provisioning may require administrator action and
a restart; no restart has been performed. Keep the API bound to localhost while this
prototype lacks authentication and deployment validation.
