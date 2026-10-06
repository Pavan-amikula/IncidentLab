# Using your IncidentLab workspace

## Simple explanation

This project watches three real test apps on your laptop. They imitate an online shop: Frontend receives a request, Checkout handles it, and Inventory checks stock. The demo sends requests automatically.

Your job is to investigate. Run healthy traffic first. Then run the delay test. Compare response time and warnings. Check the evidence before deciding which app caused the problem.

Requests means work received. Latency means time taken. Errors means failed work. ML warnings come from the model. Rule warnings come from fixed checks. A warning is a reason to investigate, not proof of a cause.

The duplicate custom black tooltip has been removed. Each control uses one browser tooltip. Saved-run and cluster selections update their data; research selections load once available cases have arrived. Choosing a live test changes its explanation; click Start to run it.

Open http://127.0.0.1:8768/ after running `Start-Laptop.ps1` from the project folder. The dashboard itself does not train a model. Hover over buttons or focus them with Tab to read their purpose.

For a fresh CPU setup of this amended project, use `Setup-Workspace.ps1` (or `Setup-Workspace.ps1 -CheckOnly` to verify an existing environment). It calls the original laptop setup with the explicit source amendment manifest. All 2,502 transferred files are still checked; only recorded source/UI amendments use new hashes. Optional figure tools are needed only to regenerate exports, not to view or download them.

## First demonstration

1. Open **Live demo**, keep **Healthy requests**, and click **Start one-minute demo**.
2. Watch **Collected windows** increase to 20. Each window is three seconds. New requests run through three owned localhost HTTP service processes. The calibrated native Isolation Forest remains frozen; this is separate from the research GRU and cluster-trained checkpoint.
3. Inspect requests, p95 latency, errors and the two alert columns. p95 is the request duration below which 95% of captured requests finished. Upstream latency includes downstream waiting. An ML warning means a score exceeded its calibration threshold. An operational warning can instead arise from latency/error envelopes or missing coverage.
4. **Operational incident state** opens after two warning windows and closes after two clear windows. A raw warning appears immediately. This grouping does not make a service ranking a proven cause.
5. Expand **Inspect latest request evidence and collector audit**. Trace/span IDs connect measured requests; collector counters reveal late or pending data. Missing requests may be an application issue or missing telemetry.
6. After completion, start **Controlled inventory delay**. Around 20 seconds a 250 ms inventory delay begins; around 40 seconds it clears. The graph should show inventory and upstream durations increasing. Compare both detectors, including misses and false warnings.
7. The worker closes its services at the end. **Stop and clean up** asks it to clear its injected fault and close only its owned child processes. Saved observations remain. A server restart is not a request to stop the separate worker; it still has a fixed one-minute lifetime.

The banner and observation timestamp distinguish **running fresh collection** from **saved completed observations**. A frozen historical result is never proof that a service is currently healthy. Concurrent demos and occupied service ports are rejected rather than taking over another workload. Controls accept only fixed healthy/delay scenarios, require localhost access and reject cross-origin browser actions.

Use **View observations** to revisit previous demos. After an interruption, a saved incident can remain open because no clear recovery window was collected; the UI marks that as historical even though the worker cleared the control and closed its services.

## Kubernetes investigation

**Kubernetes results** reads the completed laptop run `20261006T141939-0fc666`. It does not launch a cluster experiment or current collector. Select a phase, click **Inspect phase**, and select an observation window. Alert windows are marked. Compare each service's latency/error/coverage and inspect its actual trace evidence.

There were nine trace-confirmed injected fault trials: operational detection found nine; ML alone found four. Twenty-one successful client request chains had missing spans near pod deletion. Control-command completion timestamps are evaluation proxies, not exact observed request onset. Review raw traces and lifecycle evidence before interpreting a missing service as an outage. The detailed downloadable laptop report preserves failures, replay checks and negative results.

## Research archive

**Research archive** retains the detailed RCAEval results and saved held-out incident replay. Choose a model and case, click **Load telemetry**, then **Next minute** or **Play archive**. Playback speeds up archived observations; it does not create current cloud traffic. Candidate services and feature changes guide investigation, not a causal diagnosis. Historical CUDA labels describe original training, not current CPU serving.

The retained `/live` page is the advanced native experiment archive. New optional LLM generation is disabled on the laptop. Saved LLM explanations may contain unsupported statements.

## Figures and report

**Report figures** contains ten measured figures, each with a caption and PNG/SVG/PDF exports. **Download all figures** includes metadata, exact confusion counts and SHA-256 hashes of the input reports/predictions. Cite the captions and dataset provenance in your report.

- Confusion matrices count observation windows: healthy/fault labels are rows, clear/alert decisions are columns. False alarms are top-right; missed faults are bottom-left.
- RCAEval ROC and precision–recall curves use continuous saved scores separately for OB, SS and TT systems. AP denotes average precision. Curves do not establish cross-system transfer. Frozen calibration decisions are used in confusion matrices.
- Training curves show actual original GPU training loss and validation history. They are not newly created training results and are not sample-size learning curves.
- Cluster confusion matrices use control-proxy windows and exclude windows crossing injection/recovery boundaries. Capture gaps remain an evaluation limitation. Operational matrices include rules; they must not be described as ML-only results.
- Native versus cluster trial detection compares different experiments and denominators, not a paired model improvement.
- External AnoMod has no independently verified healthy labels/exact onset in this evaluation, so precision/F1/confusion plots are not invented.

To regenerate exports without retraining:

```powershell
.\.venv-laptop\Scripts\python.exe -m pip install -r requirements-report.txt
.\.venv-laptop\Scripts\python.exe -m scripts.build_report_figures
```

## Completion boundary

Completed: research processing/training/development testing, saved CPU inference, dashboard serving, durable raw observation, controlled native trials, actual laptop Docker/kind deployment, held-out Kubernetes faults, chronological replay verification, trace review and report exports.

This is a functional end-to-end research and controlled-lab project, not a universally reliable production detector. Independent external evaluation, long-duration/company-scale reliability, robust capture across rotation/restarts and authenticated multi-user deployment remain industrial validation work. Do not imply these were completed. Preserve weak external transfer, missed ML trials and capture gaps. No automatic remediation is enabled.
