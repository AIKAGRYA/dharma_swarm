# ADR: Control Surface Projector — Declared Intent vs Observed Reality

**Status:** Accepted  
**Date:** 2026-05-20  
**Track:** `cockpit-control-surface-2026-05`  
**PRs:** #244, #254, #275, #296, #307

---

## Context

The dharma_swarm operator needs a single view of system coherence: what was
*declared* (in `ACTIVE_SURFACE_MANIFEST.yaml`) versus what is *observed*
(in code, runtime, evidence adapters). Before this work, declared intent and
observed reality lived in separate, unconnected documents. The operator had no
reconciliation engine and no structured way to detect drift.

## Decision

Implement a **Control Surface Projector** that:

1. Reads declared intent from `ACTIVE_SURFACE_MANIFEST.yaml` (schema v2).
2. Probes observed reality via code imports, file existence, Go receipt
   ingestor output, recursive discovery receipts, and broken register state.
3. Produces typed `ControlSurfaceRow` records with coherence state
   (`bound`, `partial`, `drifted`, `declared_only`, `unknown`).
4. Wraps all API responses in a `ControlSurfaceEnvelope` with schema version,
   request ID, generation timestamp, and source errors.
5. Computes `DisplayHints` for frontend rendering (severity rank, tone, icon,
   group, freshness state, available actions).
6. Generates scoped `AgentHandoffPrompt` records from rows requiring action.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Operator Cockpit (Dashboard)                │
│  Human front door: /dashboard/cockpit                            │
│  Implementation: dashboard/src/app/dashboard/control-surface/page.tsx │
└─────────────────────┬───────────────────────────────────────────┘
                      │ GET /api/control-surface/{summary,rows,stream}
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│                  API Router (api/routers/control_surface.py)     │
│  Wraps projection in ControlSurfaceEnvelope                     │
│  Exposes SSE stream for live updates                            │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│            Control Surface Projector (operator_core/)            │
│                                                                 │
│  control_surface.py         — projection engine (reconcile)     │
│  control_surface_models.py  — Pydantic models + row contract    │
│  control_surface_go.py      — Go receipt adapter                │
│  control_surface_handoff.py — agent handoff prompt generation   │
└───────┬──────────────┬──────────────┬───────────────────────────┘
        │              │              │
        ▼              ▼              ▼
  ┌──────────┐  ┌────────────┐  ┌─────────────────┐
  │ Manifest │  │ Code/Files │  │ Evidence Sources │
  │ (YAML)   │  │ (imports)  │  │ (Go receipts,   │
  │          │  │            │  │  broken register,│
  │          │  │            │  │  recursive disc.)│
  └──────────┘  └────────────┘  └─────────────────┘
```

## Key Models

| Model | Role |
|---|---|
| `ControlSurfaceEnvelope` | Typed response wrapper with schema version, errors, freshness |
| `ControlSurfaceRow` | One row in the cockpit grid — declared vs observed with evidence |
| `DisplayHints` | Frontend rendering: severity, tone, icon, group, freshness, actions |
| `EvidenceItem` | Structured evidence with provenance chain |
| `SourceRef` | Reference to a source file/route/config |
| `HumanDecisionContext` | Why a row requires operator intervention |
| `VerificationEvent` | Timeline entry for observe→drift→fix→verify lifecycle |
| `AgentHandoffPrompt` | Scoped prompt generated for an agent to act on a row |

## Coherence States

- **bound** — declared intent matches observed reality
- **partial** — some evidence matches, some gaps remain
- **drifted** — declared and observed have diverged
- **declared_only** — intent declared but no observation possible
- **unknown** — insufficient evidence to determine

## Row Kinds

API routers, dashboard pages, runtime stores, state writers, organs, fleets,
memory surfaces, broken register items, Go receipts, recursive discoveries,
doc surfaces, integrations, feedback loops, agent subsystems, cron jobs.

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/api/control-surface/summary` | Coherence summary with counts by state |
| GET | `/api/control-surface/rows` | Full row list in envelope |
| GET | `/api/control-surface/rows/{id}` | Single row by ID |
| POST | `/api/control-surface/rows/{id}/handoff-prompt` | Generate agent handoff prompt |
| GET | `/api/control-surface/stream` | SSE stream of updated rows |

## Consequences

- The manifest is explicitly **not** the single source of truth — it is the
  declared-intent layer. Truth comes from reconciliation.
- `ControlSurfaceEnvelope` is the contract boundary between the projector and
  all consumers (dashboard, CLI, agents). Breaking changes require a schema
  version bump.
- DEGRADED zones are surfaced via `DisplayHints.tone = "warning"` or
  `"critical"` — enabling the ledger watcher to act on envelope data.
- The dashboard renders one read-only view; mutation flows through the API
  (handoff prompts) or direct code changes.

## Non-Goals

- The control surface does **not** mutate runtime state. It observes and reports.
- It does not replace the broken register — it surfaces broken register items
  as `ControlSurfaceRow` records with `kind = "broken_register"`.
- It does not implement the training flywheel or identity unification seams
  (those are future track candidates).

## References

- `dharma_swarm/operator_core/control_surface.py` — projection engine
- `dharma_swarm/operator_core/control_surface_models.py` — models + row contract
- `api/routers/control_surface.py` — API router
- `dashboard/src/app/dashboard/cockpit/page.tsx` — human front-door route
- `dashboard/src/app/dashboard/control-surface/page.tsx` — cockpit UI implementation
- `ACTIVE_SURFACE_MANIFEST.yaml` — declared intent
- `tests/test_control_surface.py` — contract tests
