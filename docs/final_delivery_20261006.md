# Final laptop demonstration and report delivery

Research and the controlled laptop end-to-end demonstration are complete. This is not company-production validation.

The original held-out Kubernetes run remains `20261006T141939-0fc666`: 9/9 operational trial flags, 4/9 ML-only flags, 300 replayed scored windows with zero feature/score/decision mismatches. Its capture gaps and timing-proxy limitations remain unchanged.

## Additional bounded restart verification

`artifacts/kubernetes/infrastructure-20261006T194017-f133aa/report.json` records a passed real Inventory container restart within the same pod. The check recovered all eight unpolled Inventory request traces through previous-container logs, recorded 32/32 successful check requests, and inserted zero spans during duplicate polling. All three pods are Ready after the check; Inventory has one restart.

Two earlier checks failed to trigger a container restart, and are preserved under `infrastructure-20261006T160255-803e4d` and `infrastructure-20261006T193813-30c2ae`. The service remained running. The corrected check validates the owned pod/container identity and stops only that inspected container through the kind node runtime. These checks do not train models or modify the nine-trial results. One restart does not verify log rotation or repeated restart completeness.

## Dashboard

The Kubernetes results page now separates current pod readiness from archived experiment data. It explains Docker → kind node container → three application pods. The read-only health API uses the dedicated context/namespace and caches status for 15 seconds. Docker's engine must run for cluster workloads; saved replay, figure downloads and the native HTTP demo do not require it.

The Report figures page links the report PDF, editable IEEE source ZIP and complete resume description. HTTP PDF download matched the original artifact SHA256. A real browser inspection confirmed the download controls and all three current Ready pod rows.

## Documents

- `reports/IncidentLab-IEEE.tex`: standalone IEEEtran conference-style source, inline graph coordinates, author and affiliation provided by the user, measured results, references and limitations.
- `reports/IncidentLab-IEEE-source.zip`: editable single-file source and input provenance. No publication or acceptance is claimed.
- `reports/IncidentLab-IEEE-readable.pdf`: readable two-column PDF with confusion matrix, recorded training plots, per-system ROC/PR curves and measured latency timeline. A fallback renderer was necessary because the built-in LaTeX compiler returned `Unable to find standard directories for platform`. This PDF is not a confirmed IEEEtran compilation. Source remains open/editable for an external IEEEtran compiler.
- `docs/resume_project_description.md`: ready-to-copy bullets, whole project description, supported keywords, and a short interview explanation.

Author: Amikula Pavan Kumar Goud, MSc Computer Science Student, Blekinge Institute of Technology, Karlskrona, Sweden.

## Verification and boundaries

The lean CPU suite passed 75 tests with zero errors or failures. Its optional transformer diagnosis module remains excluded, as documented previously. Original transferred research evidence hashes remain unchanged; six authorized original source amendments are recorded separately.

Remaining industrial work: independent external holdouts with healthy/onset labels, long-duration operation, log rotation and repeated restarts, authentication/multi-user deployment, and company-scale evaluation. External transfer, false alarms and capture losses prevent a production-ready claim. New LLM generation and automatic remediation remain disabled.
