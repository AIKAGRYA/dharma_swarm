# Runtime Truth NATS Closeout Packet

Status: SHIPPABLE local/offline substrate evidence; track remains ACTIVE pending operator lifecycle review.

Track: `runtime-truth-nats-2026-06`
Generated: 2026-07-01 JST

## Scope

This packet closes the rejected local substrate slice from the 55/100 review. It does not claim fresh live human-usable NATS contact. No current broker `HANDLER_ACKED` or `DOMAIN_RECEIPTED` proof was collected in this run, so live-contact graduation remains scoped to the next operator/live-broker evidence item.

## Implemented Gates

- Canonical NATS envelope: `dharma.nats.envelope.v1`, stable `message_id`, trace/span/causality fields, actor fields, subject, payload, and `Nats-Msg-Id`.
- Publish idempotency: failed/stale publish records retry through a new retry side-effect key; completed records are the only duplicate-success path; in-progress records emit `retry_blocked`.
- Consume idempotency: failed/stale handler attempts are retryable on broker redelivery; in-progress duplicate deliveries are nacked and visible; duplicate ack failure records `duplicate_ack_failed` instead of duplicate success.
- A2A handler idempotency: failed/rejected/cancelled handler results now complete the handler side-effect as `failed`, allowing legitimate redelivery retry through the inner A2A server path.
- NATS consume identity boundary: `A2ANatsTransport` rejects a supplied `A2AServer` unless it was constructed with `require_execution_identity=True`, preventing legacy/local ingress from minting identity on the broker consume path.
- Durable topology helpers: `ensure_stream_topology()` and `ensure_task_consumer()` declare `DS_TASKS`, `DS_DLQ`, explicit ack policy, stable durable consumer, and `max_deliveries`.
- DLQ behavior: max-delivery exhaustion publishes a typed `dharma.nats.dlq_failure.v1` envelope to `dharma.dlq.<stream>.<consumer>` and acks the original only after DLQ publication.
- Governance checker: `scripts/governance/check_nats_substrate_contract.py` is callable, has `--repo-root`, checks the transport, cloud-contact delegation, Makefile target, and negative-test coverage.
- Active-track criteria: NATS completion gates are executable `command_passes` checks, not spec string checks.

## Verification

- `pytest tests/test_nats_transport.py -q` -> 13 passed.
- `pytest tests/test_nats_substrate_contract.py -q` -> 3 passed.
- `pytest tests/test_track_portfolio.py -q` -> 36 passed.
- `./.venv/bin/python scripts/governance/check_nats_substrate_contract.py` -> `NATS_CONTRACT_OK`.
- `./.venv/bin/python scripts/governance/check_track_status.py` -> NATS track `SHIPPABLE`, 2/2 executable criteria passed.
- `make nats-substrate-contract` -> 70 passed.
- `pytest tests/test_a2a.py tests/test_a2a_e2e.py tests/test_a2a_spec_conformance.py tests/test_spine_persistence_invariant.py tests/test_runtime_truth_spine_v1.py tests/test_runtime_truth_spine_v2_evidence.py tests/test_a2a_cloud_contact.py -q` -> 174 passed.

## Lifecycle Boundary

Do not move `runtime-truth-nats-2026-06` to `closed_tracks` from this packet alone. The track stays ACTIVE/SHIPPABLE until an explicit operator lifecycle review accepts either:

- fresh live broker evidence with current `HANDLER_ACKED` or `DOMAIN_RECEIPTED`; or
- an explicit decision that this slice graduates only as local/offline substrate hardening.
