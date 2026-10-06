# Explanation support spot check

Run: `20261005T202755-0e2c27`, frozen policy V2, local Qwen3 1.7B. The policy and
implementation were frozen before fault collection. This review does not change
the archived generated outputs, acceptance decisions or detector scores.

Schema acceptance checks IDs, service membership, retrieved runbooks and consistency
with measured warning state. It does **not** verify the meaning of a generated
sentence. Every output retains `semantic_support_verified: false`.

This is an author/agent spot check, not independent blinded adjudication. For each
listed phase, select the first accepted hybrid review; otherwise select the first
hybrid abstention or clear output. These available completed cases are not a random
sample of all generations. Assess support against the cited records and the same
service-window observations, without using fault schedules to establish truth.

| Phase / window | Generated finding | Evidence assessment |
|---|---|---|
| healthy / 0 | Clear; requests completed successfully. | Completed requests, zero observed errors and no operational warnings. Supported as a bounded observation, not a future-health guarantee. |
| surge / 0 | Clear; requests completed successfully. | The selected window has zero errors and no warnings. This does not evaluate every surge window. |
| delay_frontend_r1 / 12 | Inspect frontend latency and measured warning. | Cited successful requests take about 337–340 ms; frontend p95 is 337.2 ms and warns. Supported inspection; ranking remains a heuristic. |
| delay_frontend_r2 / 12 | Inspect frontend latency and measured warning. | Cited requests take about 339–341 ms; frontend p95 is 339.3 ms and warns. Supported inspection. |
| delay_checkout_r1 / 12 | Checkout latency is due to downstream inventory exceeding its envelope. | **Unsupported causal claim.** Checkout p95 is 302.3 ms and warns; inventory p95 is 15.7 ms, without errors or warning. Cited caller records show successful dependency responses and do not establish inventory as the cause. |
| delay_checkout_r2 / 12 | Checkout latency is due to downstream inventory dependencies. | **Unsupported attribution.** Checkout warns at 303.0 ms; inventory is 15.7 ms without warning. A dependency edge alone does not establish the source of delay. |
| delay_inventory_r1 / 12 | Abstain after the generated runbook failed retrieval checks. | Rejection is retained. Inventory p95 is 266.3 ms and warns. This is a missed usable explanation, not a healthy-clear decision. |
| delay_inventory_r2 / 20 | Inspect inventory because a cited downstream request failed. | **Unsupported failure assertion.** Every cited request and dependency response is HTTP 200, with zero window error fractions. Slow successful requests support latency investigation, but the stated failed request is absent from the evidence. |
| error_frontend_r1 / 20 | Check frontend capacity/readiness because of 503 errors and missing requests. | Frontend citations contain actual 503 responses and a capacity-related message; checkout/inventory lack completed requests. A capacity/readiness check is a supported investigation step. Missing records do not prove an outage. |
| error_frontend_r2 / 12 | Inspect inventory because a cited downstream request failed. | **Unsupported failure and service attribution.** Cited measurements show frontend errors and zero checkout/inventory requests. No failed inventory response was observed. Coverage absence cannot establish inventory as the cause. |

Four selected accepted review outputs make unsupported causal/failure claims.
This rejects a claim that structural acceptance establishes faithful explanation.
It does not estimate overall semantic precision or certify the remaining outputs.
The uniformly sampled comparison is reported separately in [measured status](project_status.md),
including abstentions and wrong hypotheses.

The operational incident path does not depend on generated explanations. Keep
measured features, real spans and fixed investigation steps as the primary review
surface. Reliable free-text explanations require a separately frozen support
verifier and independent reviewed data. Do not tune on these inspected outputs and
then call them fresh final testing. No final diagnosis model is declared.
