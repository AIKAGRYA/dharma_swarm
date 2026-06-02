# Operator OS Merge Map

Date: 2026-06-02
Status: consolidation architecture map

## Merge Principle

Do not centralize everything into one new service. Consolidate by naming truth owners, bridge-only components, projections, and gates.

## Canonical Owners

| Concern | Canonical owner | Notes |
|---|---|---|
| VentureCell identity and policy | `docs/governance/VENTURE_CELL_DARSHAN.md`, future portfolio schema | Docs/policy own intent; runtime must prove observed state. |
| Darshan artifact transaction | `dharma_swarm/venture_cell/darshan/bundle.py` | Required files define artifact bundle shape. |
| Darshan advancement readiness | new `dharma_swarm/venture_cell/darshan/external_reader_gate.py` | Draft validation remains separate from DONE gate. |
| External operator sessions | `dharma_swarm/venture_cell/darshan/operator_log.py` | Cofounder/Polsia observations are evidence, not authority. |
| Go evidence receipt | `tools/go_sdk/receipt/receipt.go` | Deterministic evidence only. |
| Python Go bridge | `dharma_swarm/operator_core/go_evidence_bridge.py` | Reads accepted receipts and projects into Python proof paths. |
| World-radar Go receipts | `dharma_swarm/operator_core/world_radar/receipt_bridge.py` | Pattern to reuse, not Darshan source of truth. |
| Control surface | `dharma_swarm/operator_core/control_surface.py` plus focused row modules | Read-only projection over truth owners. |
| Task state | `dharma_swarm/task_board.py`, A2A lifecycle | Company OS work state should project from these. |
| Risk admission | `dharma_swarm/operator_core/governed_work_admission.py` | Shared deterministic allow/review/block decision shape. |
| Memory/wiki | `dharma_swarm/chetana/` | Canonical agent-native knowledge substrate. |
| Ontology | `dharma_swarm/ontology.py` and Darshan ontology adapter | Structured semantic materialization. |
| Decision trail | DecisionLog via Darshan `decision_adapter.py` | Final advancement decisions need durable refs. |
| Goodworks DGM | `dharma_swarm/goodworks_dgm/` | Goal/eval/optimization layer, not customer-facing company OS by itself. |

## Bridge-Only Components

These components must not own policy:

- Go receipt SDK
- Go ingestors
- `go_evidence_bridge.py`
- `world_radar/receipt_bridge.py`
- Cofounder/Polsia imports
- future email/social/payment connectors

They may read, normalize, hash, emit, load, summarize, or project. They may not decide, dispatch, publish, spend, contact, mutate ontology, mutate runtime DBs, or mark work DONE.

## Product Shell Mapping

| Cofounder shell | DS merge target |
|---|---|
| Company profile | VentureCell profile |
| Departments | agent rosters plus authority scopes |
| Canvas | projection over TaskBoard, A2A, claims, receipts, gates |
| Tasks | TaskBoard plus A2A leases |
| Library | Chetana plus artifact/source/receipt browser |
| Plan/Execute | governed work admission plus receipt-backed execution |
| Skills | Chetana atoms plus agent runbooks and scoped tool policies |
| Integrations/MCP | default-deny connectors with approval gates |
| Publishing | human-approved external action with PR/deploy receipts |

| Polsia ambition | DS merge target |
|---|---|
| AI runs company while operator sleeps | daily VentureCell delta with receipts |
| CEO/Engineer/Growth/Comms/Ops roles | departments with authority tiers |
| live activity stream | receipt stream, not theater |
| revenue/growth loop | gated external action and attribution receipts |
| bolder autonomy | progressive autonomy ladder and evals |

## First Brick Flow

```text
Darshan artifact bundle
-> human-approved external reader/contact event
-> Go emits go_evidence_receipt.v0
-> Python loads receipt through Go bridge
-> Darshan external-reader gate validates receipt and payload
-> gate_decisions.json records contact_gate result
-> decision_delta.json carries external_reader_events
-> Chetana stages privacy-redacted atom
-> control surface shows bound/partial/missing gate state
-> TaskBoard/A2A may advance only after gate pass
```

## Data Boundaries

Public evidence:

- source URL
- public page archive URL
- content hash
- published article URL
- public comment URL

Private evidence:

- raw email or DM body
- reader contact details
- payment or account data
- unpublished sensitive feedback

Private evidence must be represented by hashes, redacted summaries, and consent flags. Never put raw private material into Go receipts, Chetana atoms, public docs, or control-surface rows.

## Merge Order

1. Add Darshan external-reader gate spec and tests.
2. Add typed schema fields and validator.
3. Add control-surface row.
4. Add Chetana staged ingest for passing gate.
5. Add TaskBoard/A2A DONE gate integration.
6. Add Operator OS department/canvas projections.
7. Add external operator importers.
8. Add autonomy evals and promotion rules.

## Consolidation Risks

- Treating `validate_bundle()` as DONE readiness would collapse draft and advancement semantics.
- Letting Go receipt acceptance equal policy acceptance would violate DS boundaries.
- Adding a dashboard before the gate would create another declaration surface.
- Ingesting everything into Chetana without trust/freshness/evals would worsen recall.
- Building Polsia-like autonomy before contact-gate proof would scale narration, not operation.

