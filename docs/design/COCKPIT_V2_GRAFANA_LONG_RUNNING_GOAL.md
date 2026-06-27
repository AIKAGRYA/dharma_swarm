# Cockpit V2 Grafana Board Mode — Long-Running Goal

**Started:** 2026-06-23 JST  
**Status:** ACTIVE — first implementation slice in progress  
**Front door:** `/dashboard/cockpit`  
**Data authority:** `/api/operator-coherence/report` and generated `reports/governance/operator_coherence_cockpit.*`  
**Design source manifest:** `docs/design/COCKPIT_V2_DESKTOP_SOURCE_MANIFEST.md` + `.json`

## Mission

Build a world-class **Grafana-style Board Mode** for the Operator Coherence Cockpit: a dense, calm, clickable mission-control instrument that shows DharmaSwarm's real operating state without becoming a new truth source.

This is deliberately **not** the full 3D mandala / recursive organism yet. This slice upgrades Linear/Grafana mode first, so the operator can click in and out of real evidence, understand what is safe/dirty/live/blocked/rogue, and hand off scoped work to future agents.

## Long-Running Loop Contract

Loop type: **verification loop**.

- **Run:** cockpit API, Next dashboard, operator-coherence report generator.
- **Use:** open `/dashboard/cockpit`, filter/search cards, click panels/cards, inspect drawer evidence.
- **Prove:** lint/build/test exit codes, API response shape, regenerated JSON/Markdown receipts, browser screenshot/DOM evidence when possible.
- **Record:** this goal doc, `COCKPIT_V2_DESKTOP_SOURCE_MANIFEST.*`, and `reports/governance/cockpit_v2_grafana_execution_receipt.md`.
- **Iterate:** each slice improves the board but preserves source authority and evidence links.

## Desktop Sources Used

Primary sources read or inventoried:

- `Desktop/DharmaSwarm FrontEnd/MANDALA_MISSION_CONTROL_CANON.md`
- `Desktop/DharmaSwarm FrontEnd/LIVING_ONTOLOGY_v1_DESIGN_2026-06-15.md`
- `Desktop/DharmaSwarm FrontEnd/ART_DIRECTION_v2_2026-06-15_RUG_TO_INSTRUMENT.md`
- `Desktop/DharmaSwarm FrontEnd/FRONTEND_DESIGN_PACKET_INDEX.md`
- `Desktop/LIVE_OPS_COCKPIT_V2_GOAL_SPEC.md`
- `Desktop/LIVE_OPS_COCKPIT_V2_PR_SEQUENCE_PACKET.md`
- `Desktop/DharmaSwarm FrontEnd/02_Codex Prototypes/CODEX_PROTOTYPES_2026-06-14/CODEX_PROTOTYPE_CRITIQUE.md`
- `Desktop/DharmaSwarm FrontEnd/03_Claude Prototypes/Claude opus 4.8 Protoypes/ROUND_1_RESULTS.md`
- `Desktop/DharmaSwarm FrontEnd/03_Claude Prototypes/POSTMORTEM_proto_v14_waste.md`
- Representative visual references:
  - `.../new cockpit fusion ideas/grafana new.jpeg`
  - `.../screenshots/proto_1_atlas_board.png`
  - `.../proto_v2b_command_synthesis.png`
  - Hokusai depth study folder
  - abstract circuits / thangka / Nierika / fal generations folders

Complete discovered inventory is in `docs/design/COCKPIT_V2_DESKTOP_SOURCE_MANIFEST.md`.

## Product Thesis

Use the Desktop design packet as follows:

- **Grafana inspiration:** compact panel wall, stat panels, bar gauges, status breakdowns, inspectable metrics.
- **Atlas Board prototype:** clear cockpit shell, object focus, evidence/relationships/handoff drawer.
- **Command Synthesis prototype:** dense operational rails, Needs Action, Ten Organs grid, telemetry strip.
- **Mandala canon:** matte indigo-sumi, pigment palette, no decorative glow, evidence-first, Linear mode now / Recursive later.
- **Art Direction v2:** “rug → instrument”; no generated painting as hero; build the cockpit from real components bound to real data.
- **Live Ops V2 spec:** observe → classify → rank → propose → require operator authority → record receipt; do not execute.

## Non-Negotiables

- Do not create a second source of truth.
- Do not mutate process/GitHub/runtime state from the dashboard.
- Do not build the full 3D mandala in this slice.
- Do not hide uncertainty.
- Do not use decorative neon/glow; luminous only for real state.
- Every clickable card/panel must carry evidence or an explicit unavailable reason.
- Raw codes are allowed in drawers, but the primary UI must use human labels.
- Preserve `/dashboard/cockpit` as the front door.

## Slice Plan

### Slice 1 — Grafana Board Shell (this run)

Build:

- Reusable V2 panel primitives.
- Top cockpit header with score, freshness, source uncertainty, refresh.
- Mode/filter/search bar: Overview, Triage, Git, Runtime, Tracks, Preservation, Evidence, Design Sources.
- Stat panels for readiness, source control, runtime liveness, needs decision, preservation, receipt ledger.
- Incident / next-action queue.
- Click-to-open inspector drawer with evidence, next action, facets, raw JSON, copy handoff.
- Design Sources panel referencing the Desktop canon/prototypes/inspiration files.

Acceptance:

- A human can see the system's condition above the fold.
- Search/filter works locally over normalized cockpit cards.
- Any panel/card can be inspected and traced to evidence.
- The design visibly follows Grafana board density + Atlas/Command prototype structure, not a long report scroll.

### Slice 2 — Git Deep Dive

Add `/dashboard/cockpit/git` or an in-board Git mode:

- Branch grouping by prefix.
- Local-only / unpushed / orphaned tables.
- Dirty worktree table.
- Stash triage.
- Copy handoff per branch/worktree/stash.

### Slice 3 — Runtime Deep Dive

Add Runtime mode:

- Live ops status grid.
- Desired-live-but-stopped.
- Stale live claims.
- Runtime DBs and receipts.
- launchd/tmux/process owner map.

### Slice 4 — Track Portfolio Deep Dive

Add Tracks mode:

- 11 active tracks table.
- TTL/evidence/readiness.
- Shippable lifecycle review queue.
- Owned surfaces and dirty/branch correlation.

### Slice 5 — Recursive Lens Scaffold

Only after Board Mode is useful:

- Same object model.
- Stub Linear ⇄ Recursive toggle.
- 2D organism/mandala preview, not 3D.
- Context-preserving selected object.

## Current Implementation Targets

Existing files to reuse:

- `dharma_swarm/operator_core/operator_coherence_cockpit.py`
- `api/routers/operator_coherence.py`
- `dashboard/src/lib/operatorCoherence.ts`
- `dashboard/src/hooks/useOperatorCoherence.ts`
- `dashboard/src/app/dashboard/cockpit/page.tsx`
- Current `dashboard/src/components/operator-coherence/*`

New V2 files should live under:

- `dashboard/src/components/operator-coherence/v2/`

## Definition of Done for Slice 1

- `make onboard` run and saved in terminal output.
- Desktop source manifest written and references all discovered source files.
- `/dashboard/cockpit` renders V2 board mode.
- Filters/search/drawer work without backend mutation.
- Evidence and uncertainty remain first-class.
- `uv run pytest -q tests/test_operator_coherence_cockpit.py` passes.
- Dashboard focused lint/build passes.
- Receipt written to `reports/governance/cockpit_v2_grafana_execution_receipt.md`.

## Known Uncertainties

- Taste requires operator judgment; automated build/lint cannot prove world-class taste.
- The current checkout is already dirty with many unrelated changes. This run must avoid resets/cleanup and only report its own file surfaces.
- `gh auth` is unavailable, so live PR/CI remains an uncertainty in the cockpit.
- tmux socket may be unavailable; this should remain explicit uncertainty, not a hidden failure.

---

# 2026-06-23 Fugu Fold-In: Authority, Lane Admission, and Forge Path

## Governing correction

The Cockpit V2 Grafana board work is now explicitly subordinate to the reconciliation/admission seam:

```text
Operator Coherence Cockpit
→ Agent Lane Admission Packet
→ Production Readiness / Candidate Promotion
→ Orchestration Arena v1
→ Forge/DGM shadow loop
```

This means the board is not merely a nicer dashboard. It must become the read-model candidate that makes parallel work visible, preserved, classified, receipted, and promotable.

## Canonical versus candidate truth

The plan must always distinguish:

- canonical `origin/main` at `839fd25f43c76375f49e45012fe8f20a324aa74c`;
- canonical portfolio: `7 active / max 10`;
- dirty candidate checkout: `/Users/dhyana/dharma_swarm` on `telos-ai-seed-v0-from-sandbox`;
- dirty local cockpit projection: may show `11 active / max 11` and must not be displayed as canonical truth.

Cockpit status until extracted:

```text
CANDIDATE_HIGH_PRIORITY_NOT_CANONICAL
```

## Branch/extraction gate before more canonical work

Before any PR/canonical admission, extract the cockpit into:

```text
governance/operator-coherence-cockpit-20260623
```

from canonical baseline, copying only known cockpit surfaces. Do not raw-merge the dirty checkout.

## Track-position decision

The cockpit should be a **successor/control-tower track**, not merely a runtime-truth extension.

Recommended track identity if admitted:

```text
operator-coherence-control-tower-2026-06
```

Reason: it spans git/worktrees/stashes/PRs/lane admission/prod readiness/preservation/live ops/Forge admission. Runtime truth is one input, not the whole scope.

## Track lifecycle correction

The UI/report must not equate checker-SHIPPABLE with production-close-ready.

Folded verdicts:

- `runtime-truth-reconciliation-2026-06`: `CLOSE_READY_WITH_FOLLOWUP`
- `runtime-truth-nats-2026-06`: `KEEP_ACTIVE_PROD_HARDENING`
- `truth-graph-platform-2026-06`: `KEEP_ACTIVE_PROD_HARDENING`
- `composer-holon-spine-longrun-2026-06`: `SPLIT_BEFORE_CLOSE`
- `provider-routing-consolidation-2026-06`: `CLOSE_READY_WITH_FOLLOWUP`

## Dependency honesty follow-up

Do not treat system-`python3` render-check failure as stale governance. The settled issue is interpreter dependency:

- system `python3` without PyYAML: false failure via fallback parser whitespace-only diff;
- repo `.venv/bin/python`: pass.

Plan follow-up: governance entrypoints use repo venv or fail loud with remediation.

## Lane admission schema

Draft schema now lives at:

```text
docs/governance/schemas/agent_lane_admission_packet.schema.json
```

Minimum fields include lane id, agent/provider, branch, worktree, base ref, intended/actual surfaces, dirty/untracked count, verification, receipts, status, candidate track, dependencies, conflicts, promotion recommendation, canonicality, and preservation status.

## New durable admission artifacts

- `reports/governance/lane_admission/OPERATOR_COHERENCE_COCKPIT_ADMISSION_REVIEW_2026-06-23.md`
- `reports/governance/lane_admission/OPERATOR_COHERENCE_COCKPIT_ADMISSION_REVIEW_2026-06-23.json`

## Operator approval gate

No branch extraction, PR creation, `ACTIVE_TRACK.yaml` edit, cleanup, merge, close, deletion, reset, clean, stash drop, worktree prune, or Forge/DGM autonomous mutation is authorized by this plan alone.
