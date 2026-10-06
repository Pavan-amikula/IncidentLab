# Guided dashboard delivery — 6 October 2026

The existing IncidentLab research and measured laptop cluster results are preserved. The dashboard root now opens a guided workspace; the advanced research view remains at `/research` and native archive at `/live`. Button/select/navigation help explains purpose and side effects. Start here explains what to inspect, current versus saved observations, and the project completion boundary.

Added a one-minute CPU localhost demonstration with real frontend → checkout → inventory requests, frozen native model inference, durable SQLite observation, operational grouping and span evidence. Healthy and controlled inventory-delay scenarios are fixed and bounded. No research training or model fitting is launched. The delay control activates near 20 seconds and clears near 40 seconds; graceful stop clears it and closes owned children. Fixed scenarios, occupied-port checks, concurrent-run rejection, localhost/Host and same-origin checks constrain the controls. This is a localhost research application, not authenticated industrial deployment.

The Kubernetes view is pinned to the reviewed full-validation run through `artifacts/laptop_validation/final_summary.json`. Later quick experiments cannot silently replace its nine-trial summary. It reads saved phase predictions, observed service timelines and trace evidence. It is not a currently running cluster collector.

Ten figures were generated from saved predictions and original training history: two RCAEval confusion matrices; ROC/precision–recall figures for OB, SS and TT; recorded GRU training/validation history; separate operational and ML cluster matrices; measured inventory-delay latency timeline; and native/cluster trial detection comparison. PNG/SVG/PDF exports, captions, exact counts and input hashes are in `artifacts/report_figures/report-figures.zip`. Matplotlib is an optional regeneration dependency; serving imports no plotting package. No training occurred, no thresholds were tuned and no external accuracy labels were invented.

Verification on this laptop:

| Dashboard run | Windows | Actual spans | Dropped requests | Operational warning windows | ML warning windows | Opened incidents |
|---|---:|---:|---:|---:|---:|---:|
| Healthy `demo-20261006T150714-2d40ca08` | 20 | 1,098 | 0 | 0 | 0 | 0 |
| Delay `demo-20261006T150827-62a88c69` | 20 | 1,089 | 0 | 8 | 8 | 1 |
| Interrupted delay `demo-20261006T150951-a9b60a36` | 9 | 513 | 0 | 3 | 3 | 1 |

The complete delay run contains 118 measured inventory spans lasting at least 250 ms during the control proxy interval. Its operational incident opened and closed after observed recovery. The stop test contains 47 such spans before interruption; cleanup cleared the control and released ports 8891/8892/8893. Its last observed incident state remains saved as open because collection stopped before recovery could be observed. This is explicitly explained in the UI. These short verification runs are not long-term false alarm estimates.

The CPU suite passed **74 tests**. Confusion counts reproduce the original reported precision/recall/window counts. APIs reject unsupported scenarios, extra command fields, unsafe figure/trial names and cross-origin controls. All **2,502 transferred files** passed verification with six recorded source/UI amendments; original research evidence and immutable handoff manifest were retained. Three CPU research replay profiles remained within 0.000002 of saved GPU predictions.

Actual HTTP checks passed for the workspace, research/native archives, cluster phase evidence, PNG and ZIP exports. Downloaded ZIP bytes matched the local export hash. Browser checks verified navigation, help text, real data updates, fault opening/recovery, graceful stop, previous-run selection and rendered figures. Evidence receipts are `artifacts/laptop_validation/guided-dashboard-verification.json`, `dashboard-cpu-verification.txt` and `dashboard-tests.txt`; screenshots include `guided-dashboard-home.png` and `guided-dashboard-delay.png`.

Use [dashboard_user_guide.md](dashboard_user_guide.md) for startup and operation. `Setup-Workspace.ps1` passes the explicit amendment manifest to laptop setup; `Start-Laptop.ps1` serves the workspace. `requirements-report.txt` is needed only to regenerate exports. Regenerate figures with `python -m scripts.build_report_figures`, and audit completed demos with `python -m scripts.review_guided_demos` using the laptop environment.

The functional research/controlled-lab deliverable is complete. Industrial validation remains open: independent external holdouts, long-duration/company-scale workloads, robust restart/log-rotation capture and multi-user security. Existing weak transfer, missed cluster ML trials, false warnings and capture gaps are retained. No reliable final LLM diagnosis or automatic remediation is claimed.
