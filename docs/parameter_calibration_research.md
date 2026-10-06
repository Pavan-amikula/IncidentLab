# Healthy duration rank calibration: development protocol

Research date: 2026-10-05. This note describes a proposed comparison, without choosing thresholds from fault labels or claiming an empirical guarantee for these historical logs.

## Per-operation upper-tail ranks

Define one duration score per VM and operation using a fixed rule, such as the maximum observed duration of that operation within the session. Let `c[1], ..., c[n]` be finite scores from **healthy calibration sessions**, and `s` the same operation score for a new session. Compute:

```text
p_operation = (1 + count(c[i] >= s)) / (n + 1)
```

Large durations produce small upper-tail ranks. The `+1` prevents a zero value when a score exceeds every calibration observation. Using `>=` includes ties and gives conservative ranks; replacing it with `>` can incorrectly treat many identical normal scores as rare. No random tie breaking is needed for this deterministic comparison.

This is the upper-tail version of the split-conformal outlier rank construction, with score direction reversed from Bates et al.'s convention. The original paper distinguishes **marginal** validity across random calibration sets from stronger validity conditional on one particular calibration set; the simple formula does not supply the latter. [Bates et al., original paper, equation (3) and surrounding discussion](https://arxiv.org/pdf/2104.08279).

Keep normalization or learned score fitting separate from calibration. If the score is raw duration, no duration model fitting is needed. Freeze extraction, per-session aggregation, operation list and calibration observations before scoring held-out records. Pooling repeated records as independent samples would change the unit from VM sessions and overweight sessions with repeated operations.

## Four-operation comparison at the existing 0.01 budget

For a **prespecified family of four operations**, use:

```text
p_combined = min(1, 4 * min(p_operation_1, ..., p_operation_4))
warning = p_combined <= 0.01
```

This is equivalent to warning when any operation has a rank at most `0.0025`. Bonferroni merging does not require independence among the four p-values, but it does require each to be valid under its corresponding healthy null. [Vovk and Wang, author-hosted original paper, equation (1)](https://sas.uwaterloo.ca/~wang/papers/2019Vovk-Wang-BIOM.pdf).

The union-bound argument is explicit: if each healthy operation obeys `P(p_j <= t) <= t`, then `P(any p_j <= 0.01/4) <= sum_j 0.01/4 = 0.01`. This concerns one prespecified session/family, rather than the probability of ever alerting during indefinite repeated monitoring. The minimum possible per-operation value is `1/(n+1)`: with the inclusive comparison above, at least 399 calibration observations are needed for that operation to reach `0.0025`. Sparse operations may therefore never meet the warning criterion, which must be reported rather than bypassed by removing `+1`.

## Missingness and realistic limits

- Preserve absent, malformed, unsupported and censored durations as distinct quality states. Do not replace missing duration with zero or issue a healthy-clear assertion. An unavailable operation has no empirical rank; for combination bookkeeping its non-warning contribution can be represented as 1, with an explicit unavailable status and coverage counts. Retain the fixed factor four rather than lowering the multiplicity penalty after seeing which operations are missing.
- Rank validity requires calibration and healthy future scores to be exchangeable within the prespecified operation/missingness regime. Conditioning on observed completion can select a different duration population; healthy calibration cannot establish behavior for missing or unfinished operations.
- Workload, host, software and chronological drift can change duration distributions. Shared infrastructure also correlates sessions. Identity-disjoint splits prevent identity leakage but do not establish exchangeability. Research on conformal prediction beyond exchangeability explicitly treats distribution change and dependence as additional problems. [Barber et al., original paper](https://arxiv.org/pdf/2202.13415).
- Consequently, these ordered and potentially censored OpenStack sessions do **not** justify a claim of guaranteed 1% false alarms. Measure held-out healthy warning counts and rates, preserve the calibration sample and evaluate independent future captures. The formula is an auditable rank score here; its mathematical assumptions must remain visible.

A small `p_combined` describes unusual duration relative to the healthy reference. It is **not** the probability that the VM is faulty, that a particular component caused the delay, or that a warning is correct. Those conclusions would require a different probabilistic model and appropriate labeled evidence.

The preceding V3 residual detector reportedly found all four inspected positives but warned on 13 of 634 healthy test sessions. Those observations motivate a **development** comparison; they cannot be used to tune the four-operation rule or to call a revised result fresh final testing. Retain the existing 0.01 nominal budget and versioned V1–V3 reports. Confirm benefits and limits on a new acquisition after freezing the revised design.
