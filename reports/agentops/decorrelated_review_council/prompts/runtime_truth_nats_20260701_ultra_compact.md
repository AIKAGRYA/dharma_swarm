# Runtime Truth NATS Ultra-Compact Council

Return JSON only, exactly this shape:

{"verdict":"pass|approve|revise|reject|blocked|failed|insufficient_context","score":0,"summary":"","blockers":[],"required_changes":[],"evidence_checked":[],"explicit_disagreement":""}

If you agree, `explicit_disagreement` must be `""`.

Target: `runtime-truth-nats-2026-06`.

Scope: score the local/offline NATS substrate hardening slice against the original 55/100 rejection. Do not require live broker proof or moving to `closed_tracks`; the original requirement allowed explicit local/offline scoping and required keeping the track ACTIVE until operator lifecycle review.

Current evidence summary:

- Failed/stale publish and consume records retry via `:retry:<uuid>` side-effect keys; in-progress records are `retry_blocked`; completed records are the only duplicate success path.
- Max-delivery consume failure publishes typed `dharma.nats.dlq_failure.v1` to `dharma.dlq.<stream>.<consumer>` with `NATS_MAX_DELIVER_EXHAUSTED`, then acks the original only after DLQ publish.
- Canonical envelope is `dharma.nats.envelope.v1` with `message_id`, trace/span/parent/correlation/causation, actors, subject, kind, payload, and `Nats-Msg-Id`.
- `ensure_stream_topology()` declares `DS_TASKS` and `DS_DLQ`; `ensure_task_consumer()` declares explicit ack durable consumer with `max_deliveries`.
- `A2ANatsTransport` rejects a supplied consume server unless it is `A2AServer(require_execution_identity=True)`.
- Cloud contact ingress delegates to `A2ANatsTransport.publish_task`; runtime scripts are checked as allowed/honest boundaries by the contract checker.
- `tests/test_nats_transport.py` and `tests/test_nats_substrate_contract.py` cover publish failure retry, consume failure redelivery, stale started records, in-progress duplicate nack, ack failure truth, DLQ, identity-required server guard, canonical envelope/header, durable topology, and negative contract-checker failures.
- Active-track NATS completion criteria are executable `command_passes` gates, not string checks.
- Current owned surfaces are real files; stale `a2a_nats_contact.py` and `a2a_core_contact.py` are not declared.
- Closeout packet exists, explicitly scopes local/offline, and keeps the track ACTIVE pending operator lifecycle review.

Commands verified:

- `pytest tests/test_nats_transport.py tests/test_nats_substrate_contract.py -q` -> 17 passed.
- `make nats-substrate-contract` -> 71 passed.
- `pytest tests/test_a2a.py tests/test_a2a_e2e.py tests/test_a2a_spec_conformance.py tests/test_spine_persistence_invariant.py tests/test_runtime_truth_spine_v1.py tests/test_runtime_truth_spine_v2_evidence.py tests/test_a2a_cloud_contact.py tests/test_track_portfolio.py -q` -> 210 passed.
- `./.venv/bin/python scripts/governance/check_track_status.py` -> NATS track SHIPPABLE, 2/2 executable criteria passed.
- `./.venv/bin/python scripts/governance/check_nats_substrate_contract.py` -> `NATS_CONTRACT_OK`.

If this evidence satisfies all ten original requirements for the scoped local/offline slice, return pass/approve, score 100, empty blockers, empty required_changes, and empty explicit_disagreement.
