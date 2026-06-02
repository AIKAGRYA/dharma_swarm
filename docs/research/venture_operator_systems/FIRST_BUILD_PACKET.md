# First Build Packet: Darshan-Go External Reader Gate

Date: 2026-06-02
Status: first brick implemented and verified

## Mission

Implemented smallest native brick of the VentureCell Operator OS:

Darshan artifacts cannot advance to DONE unless `decision_delta.json` contains at least one countable external-reader event backed by an accepted `go_evidence_receipt.v0`.

## Files To Read First

- `docs/governance/VENTURE_CELL_DARSHAN.md`
- `dharma_swarm/venture_cell/darshan/schema.py`
- `dharma_swarm/venture_cell/darshan/bundle.py`
- `dharma_swarm/venture_cell/darshan/substrate.py`
- `dharma_swarm/venture_cell/darshan/operator_log.py`
- `dharma_swarm/operator_core/go_evidence_bridge.py`
- `tools/go_sdk/receipt/receipt.go`
- `dharma_swarm/operator_core/control_surface_go.py`
- `tests/test_darshan_operator_log.py`
- `tests/test_go_evidence_ingestor_bridge.py`
- `tests/test_go_world_signal_bridge.py`

## Implementation Receipt

Implemented in:

- `dharma_swarm/venture_cell/darshan/schema.py`
- `dharma_swarm/venture_cell/darshan/external_reader_gate.py`
- `dharma_swarm/venture_cell/darshan/bundle.py`
- `dharma_swarm/operator_core/control_surface_go.py`
- `dharma_swarm/chetana/provenance.py`
- `tests/test_darshan_external_reader_gate.py`
- `tests/test_control_surface.py`

Verified on 2026-06-02:

```bash
pytest -q tests/test_darshan_external_reader_gate.py
pytest -q tests/test_darshan_operator_log.py tests/test_go_evidence_ingestor_bridge.py tests/test_go_world_signal_bridge.py
pytest -q tests/test_control_surface.py -k "GoReceiptRows or external_reader"
```

Result:

```text
10 passed
9 passed
1 passed, 74 deselected
```

## Implementation Steps Now Satisfied

1. Schema models in `schema.py`:
   - `ExternalReaderEventType`
   - `GoEvidenceReceiptRef`
   - `ExternalReaderEvent`
   - `DecisionDelta.external_reader_events`

2. `external_reader_gate.py`:
   - `ExternalReaderGateResult`
   - `validate_external_reader_gate(bundle_path)`
   - helpers for loading decision delta and Go receipts

3. `validate_bundle()` remains draft-only.

4. Stricter advancement function:
   - `validate_bundle_for_done(bundle_path)`
   - this calls `validate_bundle()` and `validate_external_reader_gate()`

5. Control-surface projection:
   - row id `darshan.external_reader_go_receipts`
   - missing, rejected, partial, and bound states
   - receipt IDs/event UIDs/source refs in row evidence

6. Chetana staged ingest hook:
   - stage privacy-redacted atom only after gate pass
   - do not auto-promote

7. Focused tests added.

## Test Matrix

| Test | Expected |
|---|---|
| bundle with no reader events | `validate_bundle` passes; DONE gate fails |
| URL only, no receipt | DONE gate fails |
| missing receipt path | DONE gate fails |
| malformed receipt JSON | DONE gate fails |
| rejected Go receipt | DONE gate fails and preserves reason |
| wrong `schema_version` | DONE gate fails |
| wrong `source` | DONE gate fails |
| artifact mismatch | DONE gate fails |
| `contact_attempt` only | warns but fails countable gate |
| accepted `reply` receipt | DONE gate passes |
| accepted `inspection` receipt | DONE gate passes |
| passing gate | Chetana staged atom created |
| control surface missing receipts | row is `declared_only` or `partial` |
| control surface accepted receipt | row is `bound` |

## Fixture Shape

Use JSON fixtures in a new test file rather than requiring live email/social systems.

Accepted countable receipt:

```json
{
  "receipt_id": "goev_reader_reply_001",
  "correlation_id": "darshan-artifact-001",
  "source": "darshan_external_reader",
  "source_url": "fixture://darshan/external-reader/reply-001",
  "observed_at": "2026-06-02T00:00:00Z",
  "content_hash": "sha256:test",
  "event_uid": "evt_reader_reply_001",
  "schema_version": "go_evidence_receipt.v0",
  "status": "accepted",
  "payload": {
    "artifact_id": "darshan-artifact-001",
    "event_type": "reply",
    "reader_label": "external_reader_001",
    "contact_surface": "email",
    "summary": "Reader replied with substantive inspection.",
    "human_approved_contact": true,
    "privacy_redacted": true,
    "consent_public": false
  }
}
```

## Non-Goals

- Do not send email.
- Do not post to social media.
- Do not publish.
- Do not create a new dashboard app.
- Do not change Go policy.
- Do not promote Chetana atoms automatically.
- Do not make Polsia/Cofounder connectors.

## Done Definition

The implementation is done because:

- tests in `tests/test_darshan_external_reader_gate.py` pass;
- existing Darshan and Go bridge tests still pass;
- Go remains evidence-only;
- Python gate owns the decision;
- control surface can show contact gate state;
- docs mention the new validator and row;
- no external action is performed during tests.

## Suggested Verification Commands

```bash
pytest -q tests/test_darshan_external_reader_gate.py
pytest -q tests/test_darshan_operator_log.py tests/test_go_evidence_ingestor_bridge.py tests/test_go_world_signal_bridge.py
pytest -q tests/test_control_surface.py -k "GoReceiptRows or external_reader"
```

If Go toolchain is unavailable, Go-dependent tests may skip. The pure Python gate tests should not skip.
