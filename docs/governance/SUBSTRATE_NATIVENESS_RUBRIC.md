# Substrate Nativeness Rubric

Status: PR-S0' baseline measurement. This document defines the denominator and
the score; it does not change runtime writes.

## Denominator

A write surface is any durable path where Dharma state, lineage, decisions,
handoffs, marks, or action traces are written.

SQLite runtime surfaces:

- `runtime_state.py` stores `~/.dharma/state/runtime.db`:
  `dharma_swarm/runtime_state.py:28`.
- Tables: `sessions`, `task_claims`, `delegation_runs`, `workspace_leases`,
  `artifact_records`, `artifact_links`, `memory_facts`, `memory_edges`,
  `context_bundles`, `operator_actions`, `session_events`,
  `session_events_fts`: `dharma_swarm/runtime_state.py:30`,
  `dharma_swarm/runtime_state.py:42`, `dharma_swarm/runtime_state.py:58`,
  `dharma_swarm/runtime_state.py:76`, `dharma_swarm/runtime_state.py:89`,
  `dharma_swarm/runtime_state.py:105`, `dharma_swarm/runtime_state.py:115`,
  `dharma_swarm/runtime_state.py:134`, `dharma_swarm/runtime_state.py:146`,
  `dharma_swarm/runtime_state.py:161`, `dharma_swarm/runtime_state.py:174`,
  `dharma_swarm/runtime_state.py:189`.
- Runtime typed records exist as dataclasses:
  `dharma_swarm/runtime_state.py:327`, `dharma_swarm/runtime_state.py:339`,
  `dharma_swarm/runtime_state.py:355`, `dharma_swarm/runtime_state.py:373`,
  `dharma_swarm/runtime_state.py:386`, `dharma_swarm/runtime_state.py:402`,
  `dharma_swarm/runtime_state.py:421`, `dharma_swarm/runtime_state.py:433`,
  `dharma_swarm/runtime_state.py:448`, `dharma_swarm/runtime_state.py:461`.

Ontology surfaces:

- `OntologyHub` persists to `~/.dharma/ontology.db`:
  `dharma_swarm/ontology_hub.py:1`, `dharma_swarm/ontology_hub.py:31`.
- It owns `_meta`, `objects`, `links`, and `action_log` tables:
  `dharma_swarm/ontology_hub.py:76`, `dharma_swarm/ontology_hub.py:87`,
  `dharma_swarm/ontology_hub.py:104`, `dharma_swarm/ontology_hub.py:119`.
- `ActionDef` is the typed action contract:
  `dharma_swarm/ontology.py:129`.
- `OntologyRegistry.execute_action()` builds `ActionExecution` and may require
  telos gates before success: `dharma_swarm/ontology.py:594`,
  `dharma_swarm/ontology.py:606`, `dharma_swarm/ontology.py:623`.
- `TelicSeam` writes ontology lifecycle objects but is best-effort:
  `dharma_swarm/telic_seam.py:1`, `dharma_swarm/telic_seam.py:48`.

JSON/JSONL surfaces:

- Stigmergy appends marks under `~/.dharma/stigmergy`:
  `dharma_swarm/stigmergy.py:92`, `dharma_swarm/stigmergy.py:118`.
- Handoff appends typed handoffs to `~/.dharma/handoffs.jsonl`:
  `dharma_swarm/handoff.py:1`, `dharma_swarm/handoff.py:95`,
  `dharma_swarm/handoff.py:111`.
- Telos witness logging writes witness records:
  `dharma_swarm/telos_gates.py:522`.
- The latest Shakti executive upgrade emits governance bundles and history in
  the LF5 worktree; it is advisory and not direct dispatch control:
  `/Users/dhyana/dharma_swarm_lf5/specs/SHAKTI_ZEITGEIST_EXECUTIVE_SPEC.md:7`,
  `/Users/dhyana/dharma_swarm_lf5/dharma_swarm/shakti_zeitgeist_executive.py:1`,
  `/Users/dhyana/dharma_swarm_lf5/dharma_swarm/shakti_zeitgeist_executive.py:680`.

The measurement script also discovers Python source lines under `dharma_swarm/`
and `scripts/` that mention `.dharma` plus `.json`, `.jsonl`, or `.db`, so new
literal write paths enter the denominator without editing this rubric.

## Native Criteria

A surface is native when all four conditions are true:

1. Typed contract: dataclass, Pydantic model, `ActionDef`, or SQLite schema.
2. Authority metadata: actor, agent, session, operator, proposal, or execution
   identity is recorded.
3. Governance hook: telos, policy, gate, Shakti, or witness semantics are present.
4. Traceability: timestamp, lineage, provenance, audit log, index, or query path
   supports later reconstruction.

The script reports each criterion separately and marks `native=true` only when
all four pass.

## Formula

`substrate_nativeness = native_surfaces / total_write_surfaces`

The result is a single float in `[0.0, 1.0]`, written with a timestamp and
per-surface breakdown to:

`~/.dharma/baselines/substrate_nativeness_<YYYY-MM-DD>.json`

This turns estimates such as "10-15%" into one dated measurement.
