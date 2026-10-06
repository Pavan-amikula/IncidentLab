# Demonstrating IncidentLab

Start the research API with the VS Code task **Research. Serve real telemetry replay**.
Open http://127.0.0.1:8768/ and http://127.0.0.1:8768/live.

1. Explain the operations problem: distinguish a failing service from callers that
   inherit its errors, using measured logs, metrics and traces.
2. Show full-dataset provenance, whole-case splits, PyTorch training and frozen
   held-out comparisons in the research dashboard. Show the poor AnoMod transfer
   and OpenStack results alongside stronger in-system results.
3. In the live dashboard, inspect the healthy and surge controls. The surge alerts
   show why ML novelty alone does not establish an incident.
4. Load `test_error_checkout_r1` in the longer run (or `test_error_checkout` in a
   single-repetition run). Inspect local checkout responses and propagated
   frontend errors, real span IDs and the independently recorded evaluation schedule.
5. Compare all three fault targets. Operational checks and ML scores are separate.
   The target distribution prevents an always-inventory hypothesis from looking good.
6. Inspect grouped incident counts separately from raw warning windows. The durable
   observer labels its completed healthy observation as archived; it is not a
   currently connected company source. Its checkpoint and restart evidence remain
   inspectable in [the serving workflow](raw_observer_workflow.md).
7. Inspect the saved local LLM comparison or generate an explanation for the loaded
   window. Follow cited IDs back to request records. Show abstention when a generated
   conclusion contradicts measured warnings; valid structure does not prove accuracy.
8. Follow measurement citations (`M…`) to aggregate p95/status/count evidence, and
   request citations (`E…`) to their actual spans. Global source absence abstains from
   attributing a service; the LLM does not control the warning detector.
9. In the research dashboard, compare initial text-only OpenStack misses with restored
   raw durations. Retain the false alerts and clearly identify later revisions as
   development comparisons; parameter serving uses a separate feature contract.
10. Open [measured status](project_status.md), [workflow](native_live_workflow.md) and
   [cluster staging](../deployment/KUBERNETES.md). State the remaining validation gates.

To demonstrate actual new collection, run `Run-Live.ps1 -Mode Collect -Seconds 60`
in the visible VS Code terminal. Thirteen phases take about thirteen minutes plus
startup. This changes the latest dashboard run, while preserving earlier run folders.
Run `Run-Live.ps1 -Mode LLM` after collection for the matching comparison.

For longer known-fault validation, `Run-Live.ps1 -Mode Validation` takes about 57
minutes plus startup: two independent healthy fitting/calibration runs, two ten-minute
controls and 18 fault trials. Run `Run-Live.ps1 -Mode LLM -PolicyVersion v2` afterwards
only when the desired V2 freeze manifest was created before that run's fault collection.
Otherwise its explanation evaluation is explicitly development rather than pre-frozen
fresh trials. Older run artifacts remain intact.

This document is a demo guide, not evidence that a video or cluster deployment was
recorded. Per-run source snapshots, raw telemetry and reports are the experiment evidence.
