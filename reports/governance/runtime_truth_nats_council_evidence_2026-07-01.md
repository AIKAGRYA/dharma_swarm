# Runtime Truth NATS Council Evidence Bundle

This bundle is a compact index for the full repo evidence. It exists because the original rejection packet contains stale file names (`a2a_nats_contact.py`, `a2a_core_contact.py`) that are no longer declared in the current active track.

## Scope Boundary

The claim is 100/100 for the local/offline NATS substrate hardening slice. It is not a claim of fresh live human-usable broker contact.

Requirement 10 allowed either fresh live broker evidence or explicit local/offline scoping. The closeout packet takes the second option:

- no current live broker `HANDLER_ACKED` or `DOMAIN_RECEIPTED` proof was collected in this run;
- the track remains `ACTIVE`/`SHIPPABLE`;
- operator lifecycle review is still required before any move to `closed_tracks`.

Do not require moving this track to `closed_tracks` for this review. The original requirement explicitly says to keep the track ACTIVE until operator lifecycle review.

## Current Active Track Surfaces

The current `runtime-truth-nats-2026-06` owned surfaces are:

- `docs/governance/NATS_SUBSTRATE_MASTER_SPEC.md`
- `dharma_swarm/a2a/nats_transport.py`
- `dharma_swarm/a2a/a2a_server.py`
- `dharma_swarm/operator_core/nats_live_contact.py`
- `dharma_swarm/operator_core/nats_substrate_status.py`
- `scripts/runtime/a2a_send.py`
- `scripts/runtime/a2a_inbox_bridge.py`
- `scripts/runtime/a2a_domain_reply_worker.py`
- `scripts/runtime/a2a_reply_capture.py`
- `scripts/governance/check_nats_substrate_contract.py`
- `tests/test_nats_transport.py`
- `tests/test_nats_substrate_contract.py`
- `reports/governance/runtime_truth_nats_closeout_packet_2026-07-01.md`

The current active track does not declare `dharma_swarm/a2a/a2a_nats_contact.py` or `dharma_swarm/a2a/a2a_core_contact.py`.

## Current Active Track Gates

The current completion criteria are both executable:

- `nats_substrate_contract_checker_passes`: `./.venv/bin/python scripts/governance/check_nats_substrate_contract.py`
- `nats_transport_regression_tests_pass`: `pytest -q tests/test_nats_transport.py tests/test_nats_substrate_contract.py`

`reports/governance/active_track_evidence.md` shows:

- NATS track `SHIPPABLE`;
- 5/5 file prerequisites passed;
- 2/2 executable `command_passes` criteria passed;
- no `track-stale:runtime-truth-nats-2026-06` finding.

## Runtime Script Marker Proof

The contract checker verifies these live script boundaries:

- `scripts/runtime/a2a_send.py`: `classify_contact_evidence`, `NATS_CLI_JETSTREAM_PUB_ACK`, `live_contact_claim`.
- `scripts/runtime/a2a_inbox_bridge.py`: `DELIVERED_AND_ACKED`, `semantic_reply_claim`.
- `scripts/runtime/a2a_domain_reply_worker.py`: `target-owned`, `DOMAIN_REPLY_PUBLISHED`, `dharma.a2a.domain_receipt.v1`.
- `scripts/runtime/a2a_reply_capture.py`: `NO_REPLY`, `DOMAIN_RECEIPTED`.
- `dharma_swarm/a2a/a2a_cloud_contact.py`: `A2ANatsTransport`, `publish_task`, `JETSTREAM_PUBLISH_CONTRACT`, `operator_transport_required`.

These checks are enforced in `scripts/governance/check_nats_substrate_contract.py`; the checker returns `NATS_CONTRACT_OK` locally.

## Behavioral Tests

`tests/test_nats_transport.py` includes behavioral tests for:

- canonical envelope and `Nats-Msg-Id`;
- publish failure retry, not duplicate success;
- identity-required NATS consume server guard;
- consume handler failure nack;
- consume failure redelivery retry;
- stale started consume record retry;
- in-progress duplicate consume nack, not ack;
- duplicate ack failure truth via `duplicate_ack_failed`;
- max-delivery DLQ publish and original ack after DLQ;
- durable stream/consumer declaration;
- post-broker-ack finalization error does not nack.

`tests/test_nats_substrate_contract.py` includes negative tests proving the checker fails when:

- `Nats-Msg-Id` wiring is removed from the transport;
- the consume redelivery regression test marker is disconnected.

## Verification Commands

- `pytest tests/test_nats_transport.py tests/test_nats_substrate_contract.py -q` -> 17 passed.
- `pytest tests/test_track_portfolio.py -q` -> 36 passed.
- `./.venv/bin/python scripts/governance/check_nats_substrate_contract.py` -> `NATS_CONTRACT_OK`.
- `./.venv/bin/python scripts/governance/check_track_status.py` -> NATS track SHIPPABLE, 2/2 executable criteria passed.
- `make nats-substrate-contract` -> 71 passed.
- `pytest tests/test_a2a.py tests/test_a2a_e2e.py tests/test_a2a_spec_conformance.py tests/test_spine_persistence_invariant.py tests/test_runtime_truth_spine_v1.py tests/test_runtime_truth_spine_v2_evidence.py tests/test_a2a_cloud_contact.py tests/test_track_portfolio.py -q` -> 210 passed.
- `./.venv/bin/python -m py_compile dharma_swarm/a2a/nats_transport.py dharma_swarm/a2a/a2a_server.py scripts/governance/check_nats_substrate_contract.py scripts/governance/check_track_status.py` -> passed.

## JSON Field Warning For Critics

If you have no disagreement, set `explicit_disagreement` to the empty string `""` exactly. Do not write `No disagreement`, `None`, or explanatory prose in `explicit_disagreement`, because the council runner treats any non-empty value as disagreement.
