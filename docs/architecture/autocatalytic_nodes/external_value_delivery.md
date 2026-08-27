---
title: External Value Delivery
status: active_reference
authority: external_gated
---

# External Value Delivery

Producer: the SADHANA program defines the only active operator-gated external-value lane. No schedule, participant record, outreach, or effect receipt is inferred by this binding. This candidate node is bound to `sadhana-10-day-program-2026-08`.

Contract: consume `authorized_action`; apply `deliver_and_observe`; emit `external_outcome` to [Learning & Promotion](learning_promotion.md).

Current proof surface: [`DARSHAN_CHARTER_2026-07-12.md`](../../plans/DARSHAN_CHARTER_2026-07-12.md). This is intent evidence only.

Current adapter projection: `darshan.effect_receipt_gate` snapshots the charter and checks for the required Issue One effect receipt. The receipt is absent, so it emits `external_gate_closed`; publication, response ingestion, and external outcome remain unobserved.

Promotion obligations:

- land an executable publisher and a typed response ingestor;
- require explicit operator GO for third-party posting;
- bind delivery and response to one exact external-effect receipt.

Forbidden claim: a draft, charter, enqueue, HTTP acceptance, or local rehearsal is not publication, readership, value, or external outcome.

Operator page: `/dashboard/organism/external_value_delivery`.
