# IncidentLab laptop handoff

This bundle includes source, trained checkpoints, processed research data, saved predictions, and measured HTTP trial evidence. It runs on Windows x64 using CPU inference. No GPU, Docker or retraining is needed to explore the dashboard. Docker and Kubernetes are a separate final deployment experiment, which could not be executed on the college PC.

## First run on your laptop

1. Copy `IncidentLab-laptop.zip` and its `.sha256` receipt. Extract into a writable folder, for example `C:\IncidentLab`. Open PowerShell inside the extracted `IncidentLab` folder. The project folder contains this document, `Setup-Laptop.ps1`, `incidentlab`, `data` and `artifacts`.
2. Install official **64-bit Python 3.14**, including its `py` launcher, if absent. The pinned dependency versions match the trained artifacts. Internet access is needed once to install CPU dependencies.
3. Run:

```powershell
powershell -ExecutionPolicy Bypass -File .\Setup-Laptop.ps1
powershell -ExecutionPolicy Bypass -File .\Start-Laptop.ps1
```

Open `http://127.0.0.1:8768/` for held-out research replay, or `http://127.0.0.1:8768/live` for measured HTTP trials. Setup checks every transferred file hash, requires a CPU PyTorch build, loads checkpoints and compares CPU inference with saved GPU scores. The dashboard reads saved evidence; opening it does not launch training. The startup script limits numerical threads to two and disables new LLM generation. Saved LLM evaluations remain readable.

The original GPU environment stays on the college PC. **Use requirements-laptop.txt on your laptop**; the older research/deep requirements are for development on the GPU PC. Do not copy either virtual environment.

Optional CPU checks: `.\.venv-laptop\Scripts\python.exe -m scripts.test_laptop`. This runs the 70 serving, model-pipeline, capture and restoration tests that do not import optional transformer diagnosis. The full 80-test suite passed in the college-PC research environment; its transformer-dependent test module requires the separate semantic dependencies and is excluded from this lean CPU runner.

## Real Kubernetes experiment on your laptop

Prerequisites: Docker Desktop with a working Linux container engine, `kind`, and `kubectl` on PATH. Docker installation may require administrator access on your own laptop. These scripts do not install WSL or change college-PC permissions. Use the official [Docker Windows installation guide](https://docs.docker.com/desktop/setup/install/windows-install/), [kind guide](https://kind.sigs.k8s.io/docs/user/quick-start/), and [kubectl Windows guide](https://kubernetes.io/docs/tasks/tools/install-kubectl-windows/).

With Docker running, execute these commands one at a time:

```powershell
powershell -ExecutionPolicy Bypass -File .\Run-Cluster.ps1 -Mode Check
powershell -ExecutionPolicy Bypass -File .\Run-Cluster.ps1 -Mode Deploy
powershell -ExecutionPolicy Bypass -File .\Run-Cluster.ps1 -Mode Quick
powershell -ExecutionPolicy Bypass -File .\Run-Cluster.ps1 -Mode Validate
```

Deploy creates/reuses only the named `incidentlab` kind cluster, builds and loads the small HTTP-service image, and applies the owned `incidentlab-testbed` namespace. It verifies ownership before reusing resources and limits the single node to **2 CPUs / 4 GB**. That limit is a configuration choice, not a measured laptop memory requirement. Three application pods each have a 128 MiB memory and 500m CPU limit. The dashboard can run directly on Windows in its separate terminal.

Quick runs seven phases of 36 seconds each (about five minutes plus command/capture overhead): healthy training, separate healthy calibration, held-out healthy and surge controls, and inventory delay/error/unavailability trials. Validate covers all three services: four 180-second healthy/control phases and nine 60-second fault phases (about 21 minutes plus overhead). Only the small IsolationForest is fitted to fresh cluster healthy windows; the trained research GRU and other checkpoints are reused unchanged. CPU fitting is necessary because cluster latency differs from localhost latency.

The runner produces `artifacts/kubernetes/<run-id>/`: pod lifecycle snapshots, deduplicated request events, capture database with arrival timestamps, client request outcomes, features, predictions, control-command records, cleanup outcome, frozen checkpoint and report. See `http://127.0.0.1:8768/api/kubernetes/status` while the dashboard is running. Terminal progress names each phase. Cluster results are kept separate from the college-PC HTTP results.

Stop with Ctrl+C if needed; cleanup attempts to restore only the experiment's own fault and closes its own port-forward process. Inspect `cleanup.json` and `failure.json` after an interruption. A failed recovery requires checking the target deployment before rerunning. Port 8891 must be free; do not run a native HTTP testbed and the cluster experiment simultaneously.

Collection uses timestamped pod logs and restart watermarks, with duplicate span rejection and a recorded arrival cutoff for each decision. Previous-container logs can be requested after a restart. Pod deletion or rotation between polls can still lose tail records; snapshots expose these changes but cannot reconstruct missing data. Labels in the automatic report use **control-command completion as a proxy**, not reviewed actual fault onset. Review traces and lifecycle changes before making research claims. References: [kubectl logs](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_logs/), [port-forward](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_port-forward/), [Docker resource update](https://docs.docker.com/reference/cli/docker/container/update/).

## Storage and what stays on the college PC

Your laptop has approximately **24 GB free**. The transfer archive and extracted project are small compared with the original datasets; Python packages and Docker images consume additional space. Keep free space available and check `Run-Cluster.ps1 -Mode Check` before downloading container images. This handoff is not an offline installer: Python dependencies and base images are fetched from their official registries.

Included: processed inputs, trained GRU and conventional models, full saved evaluation reports (including negative transfer findings), measured raw HTTP telemetry and source snapshots, optional LLM evaluation outputs, research notes and acquisition/preprocessing scripts. File hashes are in `handoff_manifest.json`.

Excluded: large raw research collections, GPU virtual environments, CUDA dependencies, transformer/LLM weight directories, credentials, personal documents and old host-specific serving databases. Raw research collections and large neural weights remain on this college PC. Fresh laptop serving databases are created on first use. Historical reports/source snapshots retain their original provenance paths; inference resolves the transferred project path.

To rerun original dataset acquisition or large neural experiments, use the GPU PC and the documented source/protocol files. The laptop package supports checkpoint replay and the small real cluster experiment without repeating those expensive steps.

## What is finished and what remains

Completed on the college PC: real-data acquisition/preprocessing, train/validation/test experiments, stored checkpoints, transfer diagnostics, measured native HTTP trials, durable observation and CPU artifact verification. The optional LLM still produced unsupported statements in review; it remains disabled for laptop operation.

Remaining: actual Docker builds, cluster deployment, real pod-log capture and controlled fault trials on your laptop, then trace review and a final deployment report. Unit tests of capture and fault restoration are not substitutes for that execution. This is a research prototype with measured development evidence, not an industrial deployment or proof of reliable causal diagnosis.
