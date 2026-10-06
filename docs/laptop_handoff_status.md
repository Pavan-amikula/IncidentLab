# CPU laptop handoff verification, 6 October 2026

The ZIP was extracted into a new folder, outside the working project's source/data directories. A separate virtual environment installed the CPU requirements and used PyTorch **2.11.0+cpu**, with CUDA version **None**. Verification loaded the transferred native and OpenStack checkpoints, replayed baseline/GRU research cases and checked the disabled generation endpoint.

Three profiles (ob, ss, tt) replayed 65, 7 and 11 windows. Maximum CPU/GPU score differences were respectively 0.000000611, 0.000000002 and 0.000001371. These checks verify portability of existing predictions, not generalization to another company.

The extracted server also served actual localhost HTTP requests on temporary port 8770. Research/live status loaded and the cluster endpoint correctly reported `not_executed`. Only the verification's own server process was stopped afterward.

A fresh one-minute running HTTP application used the transferred frozen native checkpoint: 20 observation windows, zero dropped workload requests, zero operational warnings, zero ML warnings and zero opened incidents. Its final collector read 1,104 records; 51 records preceded the aligned observation interval and were accounted for as late. There were no remaining partial/pending records at the final observation. This is a short CPU pipeline check on the college PC, not a long-term false-alert estimate or a test on the user's laptop.

The full development suite passed 80 tests in the research environment. The lean CPU suite passed 70 tests. The excluded module imports the optional transformer diagnosis dependencies, which are intentionally absent from laptop requirements. Eight new capture/restoration tests are included in both suites. All three new laptop PowerShell scripts passed parser validation.

The transfer package retains trained checkpoints, processed inputs, reports (including negative results), source snapshots, raw measured HTTP evidence and research/acquisition scripts. Host-specific serving databases, credentials, personal documents, virtual environments, large raw research collections and transformer weight directories are excluded. The CPU runtime evidence is under `artifacts/live_runtime/running-app-20261006T132410-f17054`; immutable verification receipts are under `artifacts/handoff`.

Pending actual laptop execution: Docker image build, kind provisioning, pod collection/restarts, controlled cluster faults, resource measurement, trace review and final deployment report. Generated assets and unit tests alone do not prove these stages succeeded. Start with [the transfer guide](../TRANSFER_README.md).
