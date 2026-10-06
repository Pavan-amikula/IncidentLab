# Diagnostic coverage results — AnoMod development revision

The initial temporal/boosting detector alone had poor transfer. A frozen-score
diagnostic showed most signals lay below RCAEval's original thresholds. Changing those
thresholds against the 24 inspected AnoMod fault cases would turn the check into tuning,
so those scores remain the original control.

I extended the diagnostic in two ways using healthy references only to fit them:

1. **Expected-service telemetry coverage:** learn a set of consistently measured
   services from healthy CPU/memory observations, then flag consecutive missing service
   metrics only while at least 80% of expected peer services remain observed. The
   output asks an operator to check collection and readiness; missing metrics alone do
   not prove the service is down or caused the incident.
2. **Healthy-trained log-content novelty:** learn TF-IDF message templates from the
   first 70% of the SocialNetwork normal run, set the novelty threshold using the final
   30% of that same run, require at least 20 events in a minute, over 10% novel messages,
   and two consecutive minutes. It retrieves the actual messages as evidence. This is
   lexical novelty; it does not understand semantic meaning or causal paths.

## Results on already-inspected fault runs

The independent coverage signal generated warnings in all three designed SocialNetwork
service-stop runs, each on the matching service: media-service 17 windows, text-service
12, and user-service 12. Across all 24 runs it produced 41 service-minute warning
events, with five minutes of insufficient overall telemetry coverage. This is promising
diagnostic evidence, not proof of outages or a general recall result. Multiple warning
minutes belong to the same event.

The lexical log baseline found novel-content warnings in those same three runs: 51
service-minute warnings across 3.61 million processed application log events. The leading
ranked evidence service was compose-post-service, a downstream caller in these
scenarios; it must not be reported as the fault source without separate support. A
reviewer can inspect the original messages and evidence IDs in
`artifacts/research/log_content_evidence.json`.

The revised run preserves the original model checkpoints and thresholds. On 24 runs and
without discarding an initial five minutes, the existing supervised detector alerted in
3 runs rather than 2. The temporal detector still alerted in 3. Window counts changed,
so run-alert counts are not directly comparable accuracy measures. Detailed per-case
results are in `artifacts/research/anomod_development_v2_report.json`.

## What is valid and what comes next

These AnoMod cases have now been used for feature and diagnostic development; they are
not a final holdout. The healthy references are short and share one run per system. The
log model fits 70% of that run, validates on its remaining 30%, then is checked against
fault runs. No independent healthy workload verifies alert burden, drift or service
coverage variation.

Next build a runnable workload testbed after Docker is enabled, collect fresh healthy
periods, inject repeatable isolated failures, and record exact onset/recovery times.
Evaluate coverage warnings and retrieved log evidence against those fresh trials. Add a
semantic log model only after the lexical baseline and workload controls are measured.
Keep operator-facing language as “check” or “log content changed” until causal diagnosis
has independent evidence.

## Reproduction

```powershell
.\.venv\Scripts\python.exe -m incidentlab.development_monitor
.\.venv\Scripts\python.exe -m incidentlab.log_content
```

The reports describe development experiments on already-inspected AnoMod data. They
must not be presented as independent external-test accuracy or production performance.
