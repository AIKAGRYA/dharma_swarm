# Trace Attractor First Packet Witness

Date: 2026-05-20
Track: trace-attractor-causal-spine-2026-05
Trace ID: operator_brief::legacy-first-packet
Trace ID source: synthetic_legacy_alias

## Verdict

Trace Attractor is now a public operator read model, not only an internal
projector. The first packet is intentionally marked as a legacy/synthetic
operator-brief trace because current historical operator-brief records were
created before explicit trace propagation was added.

This is forward movement, not a duplicate surface: the packet makes one causal
thread queryable across ontology, runtime artifacts, telemetry, BoardStore
events, and Sakshi provenance while preserving the finding that upstream
trace_id propagation still needs to become native.

## Command Shape

```bash
dgc trace-attractor --trace-id operator_brief::legacy-first-packet --json
```

Optional store paths:

```bash
dgc trace-attractor \
  --trace-id operator_brief::legacy-first-packet \
  --registry-path ~/.dharma/ontology.db \
  --runtime-db ~/.dharma/state/runtime.db \
  --telemetry-db ~/.dharma/state/runtime.db \
  --board-db ~/.dharma/board/event_log.sqlite3 \
  --sakshi-log ~/.dharma/sakshi/provenance_log.jsonl \
  --json
```

## Packet Contract

The packet must expose:

- `trace_id`
- `trace_id_source`
- `proposal_ids`
- `gate_decision_ids`
- `artifact_ids`
- `outcome_ids`
- `value_event_ids`
- `economic_event_ids`
- `witness_log_ids`
- `lineage_edge_ids`
- `fourfold_warrant`
- `value_summary`
- `lifecycle_findings`
- `provenance_graph`

Expected finding for this first packet class:

```json
{
  "code": "legacy_trace_alias",
  "severity": "DEGRADED",
  "message": "Projected trace uses a legacy or synthetic trace alias; upstream trace propagation is still required."
}
```

Observed projector excerpt from the synthetic legacy operator-brief packet:

```json
{
  "trace_id": "operator_brief::legacy-first-packet",
  "trace_id_source": "synthetic_legacy_alias",
  "artifact_ids": ["artifact-legacy-first-packet"],
  "gate_decision_ids": ["gate-consent", "gate-steelman"],
  "witness_log_ids": ["witness-first-packet"],
  "lifecycle_findings": [
    {"code": "legacy_trace_alias", "severity": "DEGRADED"},
    {"code": "warrant_unknown", "severity": "INFO"}
  ]
}
```

## Boundaries

This witness does not open autonomous apply, mutate MemoryKernel, complete the
BoardStore adapter cutover, or register a dashboard/API surface. It only makes
trace causality visible through a CLI read model and adds optional trace
metadata to records that were previously blind to trace identity.
