# Control Surface Manifest Health Snapshot

**Generated:** 2026-05-20 12:13 UTC
**Manifest version:** 2
**Last updated:** 2026-05-13

## Summary

| Metric | Count |
|--------|-------|
| Total entities | **41** |
| Live | **22** |
| Degraded | **5** |
| Broken | **4** |
| Stub | **8** |
| Unknown | **2** |

## Dashboard Surfaces

| ID | Label | Declared | Observed | Gap | Priority |
|----|-------|----------|----------|-----|----------|
| control_surface | Control Surface | live | live | — | p0 |
| overview | System Overview | live | live | — | p0 |
| command_post | Command Post | live | live | — | p0 |
| qwen_surgeon | Qwen Surgeon | live | live | — | p1 |
| observatory | Observatory | stub | stub | — | p2 |
| runtime | Runtime | degraded | live | next: Connect runtime view to OperatorBridge live state | p1 |
| agents | Agents | live | live | — | p0 |
| tasks | Tasks | live | live | — | p0 |
| evolution | Evolution | degraded | live | next: Wire DarwinEngine to apply diffs in sandbox | p1 |
| gates | Telos Gates | stub | stub | — | p2 |
| ontology | Ontology | degraded | degraded | — | p0 |
| lineage | Lineage | degraded | live | next: Wire lineage graph to live provenance data | p2 |
| stigmergy | Stigmergy | live | live | — | p1 |
| eval_harness | Eval Harness | degraded | live | next: Wire eval harness to gauntlet results | p2 |
| audit | System Audit | degraded | live | next: Wire audit view to witness log entries | p2 |
| telemetry | Telemetry | degraded | live | next: Wire telemetry panels to live operator brief data | p1 |
| ecosystem | Ecosystem Map | stub | stub | — | p2 |
| synthesizer | Synthesizer | stub | stub | — | p2 |
| workflows | Workflows | stub | stub | — | p2 |
| blocks | Blocks | stub | stub | — | p2 |

## Agents & Subsystems

| ID | Label | Declared | Observed | Gap | Priority |
|----|-------|----------|----------|-----|----------|
| darwin_engine | Darwin Engine | degraded | live | next: Wire evolution diffs through OntologyRegistry and apply in sandbox | p1 |
| swarm_manager | Swarm Manager | live | live | — | p0 |
| telos_gatekeeper | Telos Gatekeeper | degraded | live | next: Wire inline gate checks to live task execution | p1 |
| stigmergy_store | Stigmergy Store | live | live | — | p1 |
| strange_loop | Strange Loop | stub | stub | — | p2 |
| ontology_registry | Ontology Registry | degraded | degraded | — | p0 |
| agent_runner | Agent Runner | live | live | — | p0 |
| dharma_kernel | Dharma Kernel | live | live | — | p0 |
| recursive_discovery_shadow | Recursive Discovery Shadow | shadow | degraded | unknown check_id: recursive_discovery_module_exists; next: Keep shadow-only: record receipts and recommend PRs without autonomous apply | p0 |

## Integrations

| ID | Label | Declared | Observed | Gap | Priority |
|----|-------|----------|----------|-----|----------|
| anthropic_api | Anthropic API | live | unknown | declared=live, observed=unknown |  |
| openrouter_api | OpenRouter API | live | unknown | declared=live, observed=unknown |  |
| runtime_db | Runtime SQLite | live | live | — |  |
| ontology_db | Ontology SQLite | live | broken | missing: /home/ubuntu/.dharma/ontology.db |  |
| go_world_signal_receipts | Go World Signal Receipts | incubating | broken | unknown check_id: go_world_receipts_present |  |
| recursive_discovery_receipts | Recursive Discovery Receipts | shadow | broken | unknown check_id: recursive_discovery_module_exists |  |

## Feedback Loops

| ID | Label | Declared | Observed | Gap | Priority |
|----|-------|----------|----------|-----|----------|
| strange_loop_cycle | Strange Loop | stub | stub | — | p2 |
| darwin_evolution_cycle | Darwin Evolution | degraded | live | next: Apply diffs to running code in sandbox and benchmark | p1 |
| recursive_discovery_shadow | Recursive Discovery Shadow | shadow | degraded | unknown check_id: recursive_discovery_module_exists; next: Wire receipts through EventLog and Control Surface before any autonomous apply | p0 |
| shakti_perception | Shakti Perception | stub | broken | missing: dharma_swarm/shakti_loop.py; next: Wire shakti observations to evolution pipeline | p2 |
| world_radar_receipt_projection | World Radar Receipt Projection | degraded | degraded | — | p1 |
| stigmergy_coordination | Stigmergy Coordination | live | live | — | p1 |
