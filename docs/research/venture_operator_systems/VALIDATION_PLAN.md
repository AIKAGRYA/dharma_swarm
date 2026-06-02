# Validation Plan

Date: 2026-06-02
Status: validation contract plus first-brick verification receipt

## Packet Validation

This architecture packet is valid only if the following files exist:

- `MASTER_CONSOLIDATION_SPEC.md`
- `DARSHAN_GO_EXTERNAL_READER_GATE_SPEC.md`
- `MEMORY_KERNEL_WIKI_AUDIT.md`
- `OPERATOR_OS_MERGE_MAP.md`
- `FIRST_BUILD_PACKET.md`
- `VALIDATION_PLAN.md`

Each file must reference the first brick:

`Darshan external-reader/contact gate requires accepted Go evidence receipt.`

## Architecture Invariants

1. Go emits receipts only.
2. Python/Dharma governance decides.
3. Draft bundle validation remains separate from DONE advancement.
4. External contact/outreach/publishing require human approval.
5. Private reader data is redacted or hashed.
6. Chetana ingest is staged, not auto-trusted.
7. Control surface is read-only projection.
8. Polsia/Cofounder are sources of patterns, not authority.

## Implementation Verification

Current first-brick verification on 2026-06-02:

```bash
pytest -q tests/test_darshan_external_reader_gate.py
pytest -q tests/test_darshan_operator_log.py tests/test_go_evidence_ingestor_bridge.py tests/test_go_world_signal_bridge.py
pytest -q tests/test_control_surface.py -k "GoReceiptRows or external_reader"
```

Observed:

```text
10 passed
9 passed
1 passed, 74 deselected
```

Implementation files:

- `dharma_swarm/venture_cell/darshan/schema.py`
- `dharma_swarm/venture_cell/darshan/external_reader_gate.py`
- `dharma_swarm/venture_cell/darshan/bundle.py`
- `dharma_swarm/operator_core/control_surface_go.py`
- `dharma_swarm/chetana/provenance.py`
- `tests/test_darshan_external_reader_gate.py`

Future regression runs should keep running:

```bash
pytest -q tests/test_darshan_external_reader_gate.py
pytest -q tests/test_darshan_operator_log.py
pytest -q tests/test_go_evidence_ingestor_bridge.py
pytest -q tests/test_go_world_signal_bridge.py
pytest -q tests/test_control_surface.py -k "GoReceiptRows or external_reader"
```

Required passing cases:

- no reader event blocks DONE;
- URL-only evidence blocks DONE;
- missing receipt blocks DONE;
- rejected receipt blocks DONE;
- wrong source blocks DONE;
- artifact mismatch blocks DONE;
- `contact_attempt` does not satisfy DONE;
- accepted countable Go receipt passes;
- control surface reports gate state;
- Chetana stages accepted event with receipt refs.

## Memory Validation

After ingesting this packet into Chetana, these queries should return non-zero useful results:

- `Polsia Cofounder VentureCell Operator OS`
- `Darshan external reader gate Go evidence receipt`
- `Go evidence receipt source_url event_uid accepted`
- `Cofounder Canvas Library Plan Execute publishing`
- `Chetana wiki memory kernel staged trusted quarantine`
- `VentureCell autonomy ladder external action approval`

Current status on 2026-06-02 before ingest:

```text
wiki: 0
catalytic: 0
gitnexus: 0
memory: 0
contextplus: 0
```

The memory work is not complete until these queries retrieve packet context with provenance.

## Control Surface Validation

Expected rows after implementation:

- `go.evidence_bridge`
- `go.receipt_sdk`
- `go.world_signal_receipts`
- `darshan.external_reader_go_receipts`

Expected Darshan row states:

- no events: `declared_only`
- events but missing/bad receipts: `partial`
- accepted countable receipt: `bound`

## Human Review Gates

Human approval is required before:

- sending outreach;
- publishing a Darshan artifact;
- spending money;
- exposing any reader identity;
- promoting private feedback into trusted/public memory.

## Completion Standard

The first brick is complete when an agent can create a fixture Darshan bundle, attach an accepted Go receipt, run the validator, see the gate pass, see a control-surface row, and observe a staged Chetana atom.

That standard is now met for local fixture evidence. The next standard is wiring it into the broader VentureCell Operator OS orchestration loop.
