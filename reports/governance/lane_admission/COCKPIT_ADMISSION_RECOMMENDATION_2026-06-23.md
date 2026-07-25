# Cockpit Admission Recommendation — 2026-06-23

## Question

Should the Operator Coherence Cockpit be admitted as:
- a runtime-truth extension,
- a successor active track,
- a control-tower prerequisite to Arena v1,
- or remain candidate only?

## Verified current state

- Cockpit exists only in dirty checkout `/Users/dhyana/dharma_swarm` (branch `telos-ai-seed-v0-from-sandbox`); NOT on origin/main (confirmed: `git ls-tree origin/main` shows only `dashboard/src/app/dashboard/cockpit/page.tsx`).
- Full verification reran PASS: compileall, `pytest tests/test_operator_coherence_cockpit.py` (1 passed), report regen, `json.tool`, dashboard `npm run lint`, `npm run build`.
- canonicality: `DIRTY_LOCAL_CANDIDATE`; preservation_status: local_only.
- cap room exists: canonical 7/10, admission would be 8/10.

## Recommendation

`KEEP_CANDIDATE` now -> extract to a dedicated branch -> then `ADMIT_AS_ACTIVE_TRACK` as a **successor control-tower track**, depending on `runtime-truth-reconciliation-2026-06`, not folded inside it.

Rationale: the cockpit is broader than runtime truth. It spans source-control coherence, dirty-lane radar, preservation ledger, PR/CI uncertainty, live-ops liveness, production-readiness, and the future Forge/Arena input surface. Hiding it inside runtime-truth would understate its role as the swarm control tower.

## Proposed track (DRAFT — do not write to ACTIVE_TRACK.yaml without operator approval)

```
id: operator-coherence-control-tower-2026-06
serves: substrate-nativeness
depends_on: [runtime-truth-reconciliation-2026-06]
owned_surfaces:
  - dharma_swarm/operator_core/operator_coherence_cockpit.py
  - scripts/runtime/operator_coherence_cockpit.py
  - api/routers/operator_coherence.py
  - dashboard/src/app/dashboard/cockpit/**
  - dashboard/src/components/operator-coherence/**
  - dashboard/src/lib/operatorCoherence.ts
  - dashboard/src/hooks/useOperatorCoherence.ts
  - reports/governance/lane_admission/**
moves_vital_signs: [quality_gates, memory_persistence]
```

## Extraction plan (operator-gated, non-destructive)

1. Preserve dirty checkout / off-machine first (still local-only — needs gh auth or Agni).
2. Create `governance/operator-coherence-cockpit-20260623` from clean origin/main.
3. Copy ONLY cockpit + backplane surfaces (no Telos/A2A/Holon dirty drag-in).
4. Re-run full verification on the branch.
5. Add backplane contracts as evidence.
6. Open reviewable PR; do NOT raw-merge dirty checkout.

## Operator decisions needed

1. Approve cockpit as the main control-tower candidate? (recommend: yes)
2. Approve dedicated-branch extraction? (recommend: yes)
3. Provide gh auth / off-machine preservation before any cleanup? (required before destructive ops)
4. Successor track vs runtime-truth extension? (recommend: successor control-tower track)
