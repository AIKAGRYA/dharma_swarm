---
title: Trace Attractor Ledger Master Spec
path: docs/plans/TRACE_ATTRACTOR_LEDGER_MASTER_SPEC.md
slug: trace-attractor-ledger-master-spec
doc_type: master_spec
status: shadow_implemented_not_runtime_authority
summary: A bounded next-seam spec and shadow implementation for turning partial trace propagation, SignalBus fanout, telic provenance, runtime artifacts, economic telemetry, and value events into one rebuildable operator-visible read model.
source:
  provenance: repo_local_plus_external_standards
  kind: execution_spec
  origin_signals:
    - docs/plans/NEXT_10_SUBSTRATE_TODO.md
    - docs/plans/ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md
    - docs/governance/FOURFOLD_ACTION_WARRANT.md
    - docs/interface_mismatches.yaml
    - ACTIVE_SURFACE_MANIFEST.yaml
    - dharma_swarm/correlation_context.py
    - dharma_swarm/signal_bus.py
    - dharma_swarm/telic_seam.py
    - dharma_swarm/runtime_state.py
    - dharma_swarm/telemetry_plane.py
    - dharma_swarm/operator_brief/value_events.py
  cited_urls:
    - https://www.w3.org/TR/prov-o/
    - https://www.w3.org/TR/json-ld11/
    - https://github.com/cloudevents/spec/blob/main/cloudevents/spec.md
    - https://www.w3.org/TR/trace-context/
    - https://opentelemetry.io/docs/specs/semconv/
  generated_hint: codex_authored_repo_doc
disciplines:
  - software_architecture
  - semantic_ontology
  - provenance
  - runtime_state
  - observability
  - value_accounting
  - governance
inspiration:
  - ontology_native_operator_brief
  - fourfold_action_warrant
  - correlation_context
  - signal_bus_fanout
  - value_event_loop
connected_relevant_files:
  - docs/plans/NEXT_10_SUBSTRATE_TODO.md
  - docs/plans/ONTOLOGY_NATIVE_OPERATOR_BRIEF_MASTER_SPEC.md
  - docs/governance/FOURFOLD_ACTION_WARRANT.md
  - docs/interface_mismatches.yaml
  - INTERFACE_MISMATCH_MAP.md
  - ACTIVE_SURFACE_MANIFEST.yaml
  - dharma_swarm/correlation_context.py
  - dharma_swarm/signal_bus.py
  - dharma_swarm/telic_seam.py
  - dharma_swarm/runtime_state.py
  - dharma_swarm/telemetry_plane.py
  - dharma_swarm/operator_brief/value_events.py
stigmergy:
  meaning: Defines the next bounded seam after the operator brief and value-event loop: a rebuildable trace-level projection that makes the existing substrates legible as one causal packet.
  state: shadow_implemented
  semantic_weight: 0.93
  coordination_comment: Use this before implementing Dharma Radar, Hypernode evidence routing, or any cross-store trace consolidation.
  trace_role: next_seam_contract
---

# Trace Attractor Ledger Master Spec

Status: shadow implemented, not runtime authority.

Current code truth: `dharma_swarm/trace_attractor/` now contains typed packet
models, a pure projector, read-only store readers, and regression tests. The
implementation remains a shadow read model. It must not become a mutable source
of truth, dashboard trigger, autonomy trigger, or merge excuse for unrelated
work.

## One Sentence

The Trace Attractor Ledger is a rebuildable read model that turns a `trace_id`
into one operator-visible `AttractorPacket`: proposal, gates, artifacts, task
claims, delegation runs, outcomes, value events, contributions, signal events,
economic telemetry, and fourfold warrant evidence, without becoming a new source
of truth.

## Why This Seam

Current `main` has the pieces, but not the whole:

- `CorrelationContext` carries `trace_id`, `proposal_id`, and `session_id`.
- `TelicSeam` records `Outcome` and `ValueEvent` objects and emits
  `SIGNAL_OUTCOME_RECORDED` and `SIGNAL_VALUE_EVENT_RECORDED`.
- `RuntimeStateStore` owns task claims, delegation runs, workspace leases, and
  artifact records.
- `TelemetryPlane` records economic events and trace-tagged critical telemetry.
- `dgc value-events` makes operator-brief value visible by agent.
- `docs/interface_mismatches.yaml` still marks common trace propagation
  (`NEW-07`) and SignalBus fanout subscription (`NEW-08`) as `PARTIAL`.

The problem is not a lack of ambition. The problem is that causality is still
scattered. Operators can see pieces, but cannot ask:

> Show me everything that happened because of this trace, what value it created,
> who or what was responsible, what artifacts were produced, and whether the
> governance warrant held.

This seam answers that question.

## Readiness Boundary

This spec and the shadow read model may merge as coordination artifacts.

Runtime/dashboard/autonomy wiring must wait until one of these is true:

- The `dgc value-events` read has been used on real operator data for at least
  seven calendar days after the value-loop merge.
- An explicit Fourfold Action Warrant override is attached to the implementation
  PR and names why waiting would be worse than proceeding.

Do not implement Dharma Radar v0 as part of this seam. The ledger is the
evidence substrate that makes Dharma Radar worth opening later.

## Non-Goals

- Do not create a new mutable system of record.
- Do not replace `TelicSeam`, `RuntimeStateStore`, `TelemetryPlane`, or the
  ontology registry.
- Do not build a dashboard first.
- Do not auto-trigger agents from ledger findings.
- Do not consolidate all 54 trace-lacking stores in one PR.
- Do not mutate historic records during projection.

## External Standards Alignment

The seam should borrow the small, proven parts of external standards, not import
their full complexity.

- W3C PROV-O: use the basic provenance shape of `Entity`, `Activity`, `Agent`,
  `wasGeneratedBy`, `wasDerivedFrom`, `wasAttributedTo`, `used`, and
  `wasAssociatedWith` for JSON-LD export.
- JSON-LD 1.1: export packets as ordinary JSON that can also be interpreted as
  linked data through `@context`, `@id`, and `@type`.
- CloudEvents: use a disciplined event envelope with `id`, `source`,
  `specversion`, `type`, `time`, `subject`, and `data` for projected signal
  events.
- W3C Trace Context: treat `trace_id` as the durable causal identity and keep a
  path open for `traceparent`/`tracestate` interop at API boundaries.
- OpenTelemetry semantic conventions: prefer stable attribute names for events,
  traces, logs, and resource/service identity so telemetry is correlatable
  across tools.

## Core Abstraction

### AttractorPacket

An `AttractorPacket` is a read-model object assembled from existing stores.

Required fields:

```json
{
  "schema_version": 1,
  "trace_id": "trc_...",
  "generated_at": "2026-05-05T00:00:00Z",
  "session_ids": [],
  "proposal_ids": [],
  "gate_decision_ids": [],
  "task_ids": [],
  "claim_ids": [],
  "delegation_run_ids": [],
  "artifact_ids": [],
  "outcome_ids": [],
  "value_event_ids": [],
  "contribution_ids": [],
  "economic_event_ids": [],
  "signal_event_ids": [],
  "witness_log_ids": [],
  "lineage_edge_ids": [],
  "fourfold_warrant": {
    "status": "pass|hold|block|unknown",
    "maheshwari": "pass|hold|block|unknown",
    "mahakali": "pass|hold|block|unknown",
    "mahalakshmi": "pass|hold|block|unknown",
    "mahasaraswati": "pass|hold|block|unknown",
    "evidence_refs": []
  },
  "value_summary": {
    "composite_value": 0.0,
    "economic_amount": 0.0,
    "currency": "USD",
    "agent_count": 0,
    "artifact_count": 0,
    "task_count": 0
  },
  "lifecycle_findings": [],
  "provenance_graph": {
    "nodes": [],
    "edges": []
  }
}
```

### AttractorEvent

An `AttractorEvent` is the normalized event row used inside the projection.

Required fields:

- `event_id`
- `trace_id`
- `proposal_id`
- `session_id`
- `source_store`
- `source_table_or_type`
- `source_object_id`
- `event_type`
- `subject`
- `occurred_at`
- `attributes`

CloudEvents mapping:

- `id` maps to `event_id`.
- `source` maps to `dharma://{source_store}/{source_table_or_type}`.
- `specversion` is `1.0`.
- `type` maps to `dev.dharma.{event_type}`.
- `subject` maps to the primary source object id.
- `time` maps to `occurred_at`.
- `data` maps to `attributes`.

PROV-O mapping:

- `KnowledgeArtifact`, `ValueEvent`, `Outcome`, `Contribution`, and runtime
  artifacts are `prov:Entity`.
- Dispatch, gating, execution, artifact materialization, and value scoring are
  `prov:Activity`.
- Operators, agents, workers, and external tools are `prov:Agent`.
- `Outcome` is `prov:wasGeneratedBy` task execution.
- `ValueEvent` is `prov:wasDerivedFrom` `Outcome`.
- `Contribution` is `prov:wasAttributedTo` `Agent`.
- `ArtifactRecord` is `prov:wasGeneratedBy` materialization and may be
  `prov:wasDerivedFrom` prior artifacts.

## Store Integration Contract

The first implementation series must touch the smallest useful surface:

1. Add `dharma_swarm/trace_attractor/` with pure read/projection code.
2. Read ontology objects through existing `OntologyRegistry` APIs.
3. Read runtime rows from existing `RuntimeStateStore` tables.
4. Read economic rows from existing `TelemetryPlane` tables.
5. Read `SignalBus` fanout through subscribers only when explicitly enabled.
6. Emit deterministic JSON from a CLI before any API or dashboard route.

No store becomes subordinate to the ledger. The ledger can always be deleted and
rebuilt from the existing ontology, runtime, telemetry, and signal capture data.

## Feature Flag

All runtime signal capture must be disabled by default until tests and the CLI
are stable.

Required flag:

```bash
DHARMA_TRACE_ATTRACTOR_LEDGER_ENABLED=1
```

When the flag is unset:

- projection-from-stores still works;
- SignalBus subscribers are not installed;
- no new runtime rows are written;
- existing `TelicSeam` behavior is unchanged.

## CLI Surface

Add one read-only command first:

```bash
dgc trace-attractor --trace-id trc_abc --json
```

Then add a list command:

```bash
dgc trace-attractors --since 2026-05-05 --min-value 0.5 --json
```

Human output must be compact:

```text
Trace trc_abc
  proposals: 1  gates: 4  tasks: 6  artifacts: 2
  outcomes: 1   value_events: 1  contributions: 2
  economic: USD 1200.00  warrant: pass
  findings: 0 blocker, 1 degraded
```

JSON output is the acceptance surface. Tests must compare normalized JSON.

## API and Dashboard Later

Only after the CLI is green and used on real data:

- `GET /api/trace-attractors/{trace_id}`
- `GET /api/trace-attractors?since=...&min_value=...`
- dashboard read-only panel under `DEEP` or `COMMAND`, not a new top-level
  product surface.

This keeps the seam from becoming a premature dashboard project.

## Fourfold Warrant Semantics

Every packet must be able to answer the Fourfold Action Warrant dimensions:

- Maheshwari: Does the trace serve the named telos or larger pattern?
- Mahakali: Did the trace act at the right force level and stop at the right
  boundary?
- Mahalakshmi: Did the trace reduce fragmentation or introduce parallel state?
- Mahasaraswati: Are the evidence refs, tests, artifacts, and timestamps
  precise enough to audit?

The ledger does not compute moral certainty. It computes evidence sufficiency.
Unknown is valid and must not be silently upgraded to pass.

## Lifecycle Findings

The packet must include findings, not just happy-path summaries.

Finding severities:

- `INFO`
- `DEGRADED`
- `BLOCKER`

Minimum findings:

- `missing_trace_id`: a source row in the primary path lacks trace identity.
- `orphan_outcome`: `Outcome` lacks a proposal link.
- `orphan_value_event`: `ValueEvent` lacks an outcome link.
- `open_claim_completed_task`: task lifecycle mismatch from `NEW-05`.
- `artifact_without_manifest`: runtime artifact lacks manifest/payload evidence.
- `economic_without_value_event`: economic event cannot be tied to value record.
- `signal_not_projected`: SignalBus event was observed but not captured.
- `warrant_unknown`: no warrant evidence can be derived.

## Trace Identity Rules

`trace_id` is load-bearing.

- New primary-path records must either carry `trace_id` directly or carry it in
  metadata until their table gains a first-class column.
- The projection may read `trace_id` from metadata for legacy tables.
- A missing `trace_id` on new primary-path records is `DEGRADED`.
- Missing `trace_id` on an economic or value-bearing record is `BLOCKER` once
  this seam is enabled.
- API boundaries may later expose W3C `traceparent`, but internal records keep
  the existing `trc_...` format unless a separate migration warrant is accepted.

## SignalBus Fanout Rules

The first subscriber must be narrow:

- subscribe only to `SIGNAL_OUTCOME_RECORDED`;
- subscribe only to `SIGNAL_VALUE_EVENT_RECORDED`;
- normalize each signal into `AttractorEvent`;
- write only when the feature flag is enabled;
- never let subscriber failures propagate to emitters.

This directly closes the current `NEW-08` partial state without forcing the
other independent `record_outcome()` implementations to change in the same PR.

## JSON-LD Export

The JSON-LD export is optional in the first implementation PR, but the data
model must not block it.

Shape:

```json
{
  "@context": {
    "prov": "http://www.w3.org/ns/prov#",
    "dharma": "https://dharma.local/ns#",
    "trace_id": "dharma:traceId",
    "value_summary": "dharma:valueSummary"
  },
  "@id": "dharma:trace/trc_abc",
  "@type": "dharma:AttractorPacket"
}
```

## Test Gauntlet

Minimum first implementation tests:

- `tests/test_trace_attractor_projection.py`
  - builds a synthetic trace across ontology, runtime, and telemetry;
  - asserts stable `AttractorPacket` JSON;
  - asserts the projection can be rebuilt after deleting generated rows.
- `tests/test_trace_attractor_signal_fanout.py`
  - enables the feature flag;
  - emits outcome and value-event signals;
  - asserts subscribers normalize signals;
  - asserts subscriber failure cannot break the emitter.
- `tests/test_trace_attractor_lifecycle_findings.py`
  - creates orphan outcome/value/economic/artifact cases;
  - asserts severity mapping.
- `tests/test_dgc_trace_attractor_cli.py`
  - verifies `--trace-id --json`;
  - verifies empty trace output;
  - verifies deterministic sort order.

Targeted commands:

```bash
pytest -q tests/test_trace_attractor_projection.py
pytest -q tests/test_trace_attractor_signal_fanout.py
pytest -q tests/test_trace_attractor_lifecycle_findings.py
pytest -q tests/test_dgc_trace_attractor_cli.py
```

Full confidence command:

```bash
pytest -q tests/test_authority_revenue_loop.py tests/test_value_events_cli.py tests/test_signal_bus.py tests/test_artifact_manifest.py
```

## Implementation PR Sequence

### PR 1: Spec Only

This document.

### PR 2: Pure Projection Types

Add:

- `dharma_swarm/trace_attractor/__init__.py`
- `dharma_swarm/trace_attractor/models.py`
- `dharma_swarm/trace_attractor/projector.py`
- `tests/test_trace_attractor_projection.py`

No CLI. No subscribers. No writes.

### PR 3: Store Readers

Add store readers for:

- ontology objects by type and trace metadata;
- runtime task claims and delegation runs by `trace_id`;
- runtime artifacts by direct or metadata trace;
- telemetry economic events by `trace_id`.

### PR 4: Signal Capture

Add feature-flagged subscriber installation for outcome and value-event signals.

### PR 5: CLI

Add `dgc trace-attractor --trace-id ... --json`.

### PR 6: Value-Loop Join

Extend `dgc value-events` with optional trace correlation:

```bash
dgc value-events --since 2026-05-05 --trace-id trc_abc --json
```

### PR 7: Operator Witness

Run one real operator-brief trace and one opportunity/revenue trace through the
ledger. Produce a witness report under:

```text
reports/witness/<date>-trace-attractor-first-packet.md
```

### PR 8: Dharma Radar Warrant

Only after the readiness boundary is satisfied, write the Dharma Radar v0 spec
against this ledger instead of directly against raw stores.

## Acceptance Criteria

The seam is accepted when:

- one operator-brief trace produces a complete `AttractorPacket`;
- one opportunity/revenue trace produces a complete `AttractorPacket`;
- value events can be grouped by agent and filtered by trace;
- economic events can be correlated to value events or explicitly flagged;
- artifact records are visible in the packet;
- missing links produce deterministic findings;
- packet JSON is stable across repeated runs;
- disabling the feature flag removes subscribers but does not break projection;
- no new source of truth is introduced.

## What This Unlocks

- Dharma Radar v0 can become a view over verified packets, not a second
  dashboard reading half the system.
- Hypernode and revenue cells can consume evidence packets instead of scraping
  unrelated stores.
- Devin/Codex/human work can be reviewed by trace rather than by scattered
  commits, logs, and ontology rows.
- The mismatch map gets a concrete closure path for `NEW-07` and `NEW-08`.
- The Fourfold Action Warrant becomes inspectable after the fact, not just a
  pre-action prose artifact.

## Core Risk

The dangerous version of this project is a giant state unification refactor.

The correct version is smaller and stricter:

- projection first;
- read-only first;
- CLI first;
- JSON first;
- feature flag before subscribers;
- dashboard last.
