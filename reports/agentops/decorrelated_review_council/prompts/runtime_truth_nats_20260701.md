# Runtime Truth NATS 100/100 Council Review

Review target: `runtime-truth-nats-2026-06`

You are a decorrelated critic for a governance closeout. Score 0-100 using the attached rubric and return only the required JSON object:

- `verdict`: `pass`, `approve`, `revise`, `reject`, `blocked`, `failed`, or `insufficient_context`
- `score`: integer 0-100
- `summary`
- `blockers`
- `required_changes`
- `evidence_checked`
- `explicit_disagreement`

Pass/approve at 100 only if the implementation fully resolves the original 55/100 rejection packet for the explicitly scoped target. Treat cosmetic string checks, stale evidence, false duplicate success, silent message loss, or untested governance claims as blockers.

## Original Rejection Requirements To Check

1. Failed/stale publish and consume attempts must be retryable or DLQ-visible, never converted into duplicate ack/dedup success.
2. Regression tests must cover consume failure redelivery, stale started records, publish failure retry, concurrent duplicate delivery, ack failure, and duplicate ack truth.
3. Canonical NATS envelope must be implemented and tested end to end: `dharma.nats.envelope.v1`, `message_id`, causality fields, actors, subject, payload, `Nats-Msg-Id`.
4. Durable stream/consumer setup and DLQ behavior must match the spec, including MaxDeliver/operator-visible blockers.
5. Production A2A publish/consume should route through one governed abstraction, or bypasses must be documented/tested equivalently.
6. `tests/test_nats_substrate_contract.py` must exist with negative tests proving the contract checker fails when wiring is disconnected.
7. Active-track criteria must be executable behavioral gates, not spec string checks.
8. `ACTIVE_TRACK.yaml` owned surfaces must point at real modules.
9. A real closeout packet must exist while keeping the track ACTIVE until operator lifecycle review moves it.
10. Fresh live broker evidence must show current `HANDLER_ACKED`/`DOMAIN_RECEIPTED`, or the slice must explicitly scope itself as local/offline partial substrate.

## Implemented Scope Claim

This implementation claims 100/100 for the local/offline NATS substrate hardening slice, not fresh live human-usable NATS contact. The closeout packet explicitly states no current live broker `HANDLER_ACKED` or `DOMAIN_RECEIPTED` proof was collected and keeps the track ACTIVE/SHIPPABLE pending operator lifecycle review.

## Local Evidence Commands Already Run

- `pytest tests/test_nats_transport.py tests/test_nats_substrate_contract.py -q` -> 17 passed.
- `pytest tests/test_track_portfolio.py -q` -> 36 passed.
- `./.venv/bin/python scripts/governance/check_nats_substrate_contract.py` -> `NATS_CONTRACT_OK`.
- `./.venv/bin/python scripts/governance/check_track_status.py` -> NATS track SHIPPABLE, 2/2 executable criteria passed.
- `make nats-substrate-contract` -> 71 passed.
- `pytest tests/test_a2a.py tests/test_a2a_e2e.py tests/test_a2a_spec_conformance.py tests/test_spine_persistence_invariant.py tests/test_runtime_truth_spine_v1.py tests/test_runtime_truth_spine_v2_evidence.py tests/test_a2a_cloud_contact.py tests/test_track_portfolio.py -q` -> 210 passed.
- `./.venv/bin/python -m py_compile dharma_swarm/a2a/nats_transport.py dharma_swarm/a2a/a2a_server.py scripts/governance/check_nats_substrate_contract.py scripts/governance/check_track_status.py` -> passed.

## Changed Surfaces To Inspect

- `dharma_swarm/a2a/nats_transport.py`
- `dharma_swarm/a2a/a2a_server.py`
- `tests/test_nats_transport.py`
- `tests/test_nats_substrate_contract.py`
- `scripts/governance/check_nats_substrate_contract.py`
- `scripts/governance/check_track_status.py`
- `tests/test_track_portfolio.py`
- `docs/governance/ACTIVE_TRACK.yaml`
- `reports/governance/active_track_evidence.md`
- `reports/governance/runtime_truth_nats_closeout_packet_2026-07-01.md`
- `Makefile`

Reject if the attached evidence is insufficient to verify any required item. If you approve below 100, list the exact remaining changes needed for 100/100.
