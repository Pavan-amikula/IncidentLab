# IncidentLab: actual laptop deployment and validation, 6 October 2026

## Outcome and execution boundary

The CPU startup, Docker image build, isolated Kubernetes deployment, revised Quick experiment, and full Validate experiment completed on the user's laptop. The final run **`20261006T141939-0fc666`** contains **13 phases, 420 three-second observation windows, 3,413 real client requests and 9,680 captured service spans**. The planned observation duration was 21 minutes, plus startup, polling, control and cleanup overhead.

Operational checks flagged **9/9** trace-supported controlled trials. ML-only IsolationForest flagged **4/9** under the prepared evaluation protocol. These are trial/window flags, not grouped incident counts. Every intended fault produced reviewed client or service evidence, but the automatic window labels still use command-completion proxies; this report does not replace them with independently adjudicated exact onset labels.

Three HTTP application services run in Kubernetes. Collection, fresh small-model fitting, CPU inference and the FastAPI dashboard run on Windows. The research GRU and other transferred checkpoints were not retrained. New LLM generation remains disabled, confirmed by actual HTTP 503 from its endpoint. No automatic remediation was enabled.

## Laptop verification

- All **2,502** transferred files passed SHA-256 and byte-count verification before changes. The folder was already extracted; this check compares files with the embedded manifest.
- Python **3.14.8 x64**, PyTorch **2.11.0+cpu**, CUDA version **None**, two numerical threads. Saved native and OpenStack checkpoints loaded. Three temporal profiles replayed 65, 7 and 11 windows; maximum CPU/GPU score difference was **0.000001371**. These are portability checks, not transfer/generalization evidence.
- The original lean CPU suite passed **70 tests**. After the HTTP framing fix, **71 tests** passed, including a real-HTTP response-length regression. The optional transformer-dependent module was excluded; the historical full 80-test result belongs to the college PC.
- Actual localhost HTTP returned 200 for research, native and Kubernetes status endpoints. The dashboard remains at [localhost:8768](http://127.0.0.1:8768/); [cluster results](http://127.0.0.1:8768/api/kubernetes/status) report the completed run.
- One-minute frozen native-model run `running-app-20261006T135636-9a73f9`: 20 windows, zero dropped workload requests, zero operational warnings/opened incidents, one ML warning. Its final collector accounted for 48 pre-window late records and had zero pending/partial records. This is a bounded healthy check, not a false-alarm-rate estimate.

Receipts and terminal logs are in `artifacts/laptop_validation/`. Original research and college-PC measured results remain unchanged.

## Deployment and preserved failures

Docker Desktop **4.90.0**, Linux Docker engine **29.7.2**, kind **0.33.0**, kubectl client **1.36.1**, Kubernetes server **1.37.0**. Only `kind-incidentlab` and the owned `incidentlab-testbed` namespace were used. Docker confirmed the node's configured **2 CPU / 4 GiB** limits. All three deployments finish with one Ready/available replica and empty fault controls.

1. Initial setup failed because Python 3.14 was absent; Check failed because kind was absent. Automatic approval review blocked the Python installer command. The user installed both prerequisites manually, after which Check passed. No administrator-dependent Docker/WSL action was required in this session.
2. Cluster bootstrap failed on the engine's cgroup v1. A retained diagnostic retry confirmed the kubelet refusal. Logs were exported before removing only the owned failed node. Explicit local compatibility sets `failCgroupV1: false`, with a digest-pinned node image. [Kubernetes documents this temporary override and recommends migration to cgroup v2](https://kubernetes.io/blog/2026/07/31/kubernetes-v1-37-sneak-peek/). This is not a production configuration.
3. Quick `20261006T140359-a6e839` failed before training/fault injection: the health response waited about one second for port-forwarded connection EOF, exceeding the 0.3-second read timeout. Exact **Content-Length** headers now frame health/request responses. The small image was rebuilt, loaded, and the owned deployments restarted; unchanged YAML alone does not replace pods using the same development tag.
4. Quick `20261006T140735-d370bc` completed but did **not** establish inventory outage detection. Every client succeeded during scale-down; snapshots showed the terminating pod still serving during its 30-second grace period. Its automatic detected-trial flag is retained as a misleading proxy result, not credited as confirmed outage detection.
5. `Configure-LaptopTestbed.ps1` applies a one-second termination grace period only after namespace/deployment ownership checks. Revised Quick `20261006T141408-1b6632` then confirmed all three inventory faults: operational 3/3, ML 0/3; 32 active-cohort failed requests matched 32 dependency-failure spans in the outage. Seven successful chains lost their inventory span around deletion. The short grace period is a controlled experiment choice, not a production shutdown recommendation.

All failed runs, source snapshots, command times and cleanup receipts remain available. Validate used fresh 60-window healthy training and separate 60-window calibration; no thresholds were tuned against the known faults.

## Validate results and reviewed impact

Fractions below are **automatic fault-window fractions under command-completion proxy labels**, excluding windows crossing control boundaries. Evidence counts inspect actual requests; they are not new independent fault samples. Delay inspection uses >=200 ms for the configured 250 ms injection. Frontend unavailability has transport/lifecycle evidence rather than an application error span from a nonexistent server.

| Fault | Target | Operational fraction | ML fraction | Reviewed impact |
|---|---|---:|---:|---|
| delay | frontend | 1.000 | 0.000 | 61 delayed target spans |
| delay | checkout | 1.000 | 0.000 | 57 delayed target spans |
| delay | inventory | 1.000 | 0.000 | 61 delayed target spans |
| error | frontend | 1.000 | 1.000 | 61 local error spans; 61 failed clients |
| error | checkout | 1.000 | 1.000 | 61 local error spans; 61 failed clients |
| error | inventory | 1.000 | 0.000 | 62 local error spans; 62 failed clients |
| unavailable | frontend | 1.000 | 0.000 | 59 transport failures; frontend pod removed |
| unavailable | checkout | 1.000 | 0.143 | 59 failed dependency spans; 59 failed clients |
| unavailable | inventory | 1.000 | 0.250 | 58 failed dependency spans; 58 failed clients |

The first reviewed delay/error request starts were approximately 0.016–0.049 seconds after command completion. Downstream unavailability impact appeared approximately 2.06–2.07 seconds later. These are first observed request impacts, not exact underlying failure-onset estimates. Correct first-ranked services are investigation hypotheses; global missing telemetry and ordering heuristics do not establish causal diagnosis accuracy.

The two held-out controls each lasted three minutes, with all client requests returning 200:

| Control | Client requests | Operational warning windows | ML warning windows | Actual requests / planned second |
|---|---:|---:|---:|---:|
| test_healthy | 468 | 0 | 0 | 2.60 |
| test_surge | 650 | 0 | 3 | 3.61 |

The surge control had three ML novelty warnings despite no operational fault. Another ML warning in the frontend-delay phase occurred after recovery on ordinary checkout latency; it is not credited as delay detection. Zero operational warnings over six control minutes is a limited observation, not proof of a production false-alert rate. Serial polling lowers actual request rates below the nominal schedule; zero dropped requests refers to the runner's concurrency-cap counter.

## Chronology, capture quality and performance

- The stored checkpoint stayed unchanged from before the fault trials to completion: `9629e93d01a422fd5beef264d3a459341631669cbf6c9ec7ba8ad96e45b91c61`.
- **300 scored windows** were reconstructed using each stored arrival cutoff and rescored with the frozen model. Feature mismatches: **0**; score/decision mismatches: **0**; maximum score difference: **0.0**. No captured event in a scored window arrived after its decision cutoff.
- Stored `(service, span)` keys and exports were unique. All **13 cleanup receipts** are restored; counted dropped requests: **0**.
- **21 successful request chains were incomplete**, seven in each scale-down phase. There were **14 missing parent links** across frontend/checkout deletion. These are capture omissions even though those requests succeeded. Polling can lose a deleted pod's tail; exact replay proves consistency on captured data, not completeness. Do not label these omissions as application failures or reconstruct nonexistent records.
- Model inference p95: **52.52 ms**. Window-close-to-decision p95: **6.28 seconds**, including collection grace and polling. The automatic report's window-end-based detection delay is not the actual alert-decision timestamp.
- Model inspection found no healthy variation in error fraction/concurrency and no corresponding tree splits. Absence has no ML score by implementation. The forest remains a limited novelty signal; operational latency/error/coverage checks produced the stronger result.

Review evidence: `artifacts/kubernetes/20261006T141939-0fc666/trace_review.json`; original automatic metrics: `report.json`. Client outcomes, raw spans, SQLite arrival watermarks, lifecycle snapshots, control timestamps and source snapshots remain beside them.

## Observed laptop resources

During Validate, **50 samples** recorded a maximum node memory report of **928.0 MiB**, minimum available Windows memory of **2.08 GiB**, and minimum free disk of **19.99 GiB**. Sampling ran from `2026-10-06T14:20:13.4082650+02:00` to `2026-10-06T14:41:56.1089321+02:00`.

These are sampled values, not instantaneous peaks or minimum laptop requirements. Node statistics exclude the rest of the Docker VM and host-side inference/dashboard. Ambient memory/disk availability changed during the session. The configured node/pod limits are not measured capacity requirements. No unrelated Docker resources were removed to make space.

## Reproduce the current source and experiment

The immutable transfer manifest remains intact. Three runtime source amendments and their original hashes are in `laptop_patch_manifest.json`; originals are in `artifacts/laptop_validation/originals/`. The explicit amendment option verifies changed runtime source without skipping or modifying dataset/checkpoint evidence.

From the extracted `IncidentLab` project directory:

```powershell
$env:PATH="$env:LOCALAPPDATA\IncidentLab\tools;$env:PATH"
powershell -ExecutionPolicy Bypass -File .\Setup-Laptop.ps1 -PatchManifest .\laptop_patch_manifest.json
.\.venv-laptop\Scripts\python.exe -m scripts.test_laptop
powershell -ExecutionPolicy Bypass -File .\Run-Cluster.ps1 -Mode Check
```

For a **new** cluster on this cgroup-v1 engine, run `Prepare-LaptopCluster.ps1 -AllowLegacyCgroupV1` first. It refuses to recreate an existing named cluster. Then deploy:

```powershell
powershell -ExecutionPolicy Bypass -File .\Run-Cluster.ps1 -Mode Deploy
docker build -f deployment/Dockerfile.testbed-laptop-pinned -t incidentlab-testbed:dev .
kind load docker-image incidentlab-testbed:dev --name incidentlab
powershell -ExecutionPolicy Bypass -File .\Configure-LaptopTestbed.ps1
```

After a rebuild using the same tag, restart only the three owned deployments in `kind-incidentlab` / `incidentlab-testbed` and wait for each rollout. Inspect ownership before reusing resources; Run-Cluster and Configure-LaptopTestbed perform their ownership checks. The pinned Dockerfile contains the captured base digest, and actual image/pod identities are archived under laptop_validation. Build attestations may vary on rebuild.

```powershell
foreach ($service in @('frontend','checkout','inventory')) {
    kubectl --context kind-incidentlab -n incidentlab-testbed rollout restart "deployment/$service"
    kubectl --context kind-incidentlab -n incidentlab-testbed rollout status "deployment/$service" --timeout=120s
}
powershell -ExecutionPolicy Bypass -File .\Run-Cluster.ps1 -Mode Quick
powershell -ExecutionPolicy Bypass -File .\Run-Cluster.ps1 -Mode Validate
.\.venv-laptop\Scripts\python.exe -m scripts.review_laptop_cluster artifacts/kubernetes/<run-id> --rescore
```

For this saved experiment, rebuild the report with `python -m scripts.build_laptop_report --run-id 20261006T141939-0fc666` using the laptop venv. Use `Setup-Laptop.ps1 -CheckOnly -PatchManifest .\laptop_patch_manifest.json` for artifact/source verification without reinstalling. Start the dashboard separately with `Start-Laptop.ps1`; it reads saved evidence and does not launch training. Port 8891 is shared with native experiments, so run them separately. Numerical threads were bounded to two during collection. The resolved dependency receipt is `artifacts/laptop_validation/requirements-resolved.txt`.

## What remains beyond this experiment

The completed college-PC research remains distinct: RCAEval 735 acquired / 733 eligible cases, 439/147/147 case splits, approximately 49.7 million logs and 110.7 million spans; saved GRU/baseline experiments; weak external transfer; OpenStack development false alarms; and the 22-phase native run with operational/grouped 18/18 versus ML-only 10/18. None of those measurements were replaced by the laptop trials.

Industrial validation remains open: longer independent healthy periods; repeated unseen faults and systems; drift and workload shifts; reliable continuous collection across deletion/rotation and same-pod container restarts; production model-serving deployment and operational security/availability testing; and independent explanation-support review. This run exercised pod deletion/replacement, not log rotation or the previous-container restart path. It tested a known three-service application under bounded traffic, not company production or a full range of infrastructure failures.

Accepted saved LLM explanations with unsupported statements remain negative evidence. New generation is disabled, no final reliable diagnosis model is declared, and no autonomous remediation was added. The laptop deployment experiment is complete; the project remains a research prototype with explicit remaining industrial gates.
