# Runtime Truth NATS Final Adversarial Production Review

You are performing a hostile production-readiness review of `runtime-truth-nats-2026-06`.

Do not trust prior summaries or closeout language. Only pass if current code plus fresh live evidence proves end-to-end readiness for the scoped live broker profile.

Review the attached evidence and return JSON only per the council schema. Be severe.

The model/provider recorded in the live matrix is the model-backed handler under test. Your council lane model is only the critic model. Do not reject because the handler model differs from your reviewer lane; reject only if the handler model/provider is missing, inconsistent with the semantic receipt, simulated, stale, or not live.

Pass requires:

- Fresh live NATS/JetStream broker evidence.
- `DS_TASKS` and `DS_DLQ` topology evidence.
- Durable explicit-ack consumer evidence for `a2a_task_handler`.
- Live publish through `A2ANatsTransport.publish_task`.
- Canonical envelope with `dharma.nats.envelope.v1`, stable message id, identity/causality fields, typed payload, and `Nats-Msg-Id`.
- Live `A2AServer(require_execution_identity=True)` handler execution.
- Live model-backed semantic handler receipt.
- Ack after handler success.
- Handler failure nack and redelivery.
- Stale idempotency retry.
- Concurrent in-progress duplicate blocked/nacked truthfully.
- Broker ack failure surfaced truthfully.
- MaxDeliver typed DLQ envelope and original ack after DLQ publish.
- DLQ publish failure does not falsely ack original and leaves operator-visible state.
- Restart/recovery redelivery without lost work.
- Governance-negative tamper path fails.
- Active-track and Makefile gates require live evidence.
- Compatibility publishers cannot claim production readiness.

Reject or revise if any evidence is stale, simulated without disclosure, not tied to current code, or still allows a bypass to claim stronger semantics than proven.
