# PR Lifecycle + Spine Adoption Ops Report
**Run:** 2026-06-14 18:00Z  
**Agent:** Oz automated ops agent

---

## Mission 1: Spine Adoption

| Metric | Value |
|--------|-------|
| adoption_pct | **93.8%** |
| target | 95% |
| gap | 1.2 pp |
| joined | 12 / 16 |
| adapter-ready | 3 |
| legacy | 1 |
| missing | 0 |
| quarantine | 0 |

**Status change from prior run:** None. 93.8% → 93.8%. All 16 surface classifications stable.

### Top Saturation Targets (adapter-ready → joined)

1. **tool_registry_dispatch** (`dharma_swarm/tool_registry.py`)
   - Missing: `try_begin_idempotent_side_effect` gate before tool side-effects
   - Priority 5 · category: tool

2. **self_modification_loop** (`dharma_swarm/diff_applier.py`)
   - Missing: `try_begin_idempotent_side_effect` gate on apply path
   - Priority 6 · category: self-modification

3. **mcp_tool_access** (`dharma_swarm/mcp_server.py`, `dharma_swarm/dharma_context_mcp.py`)
   - Missing: `ExecutionIdentity` import, `RuntimeStateStore` wiring, `record_side_effect` receipts (3 patterns)
   - Priority 7 · category: tool

**Quick-win path to 95%:** Wire idempotency gate in `dharma_swarm/tool_registry.py` (single file, 1 pattern).

Metric JSON updated and PR [#605](https://github.com/AmitabhainArunachala/dharma_swarm/pull/605) opened.
Adoption comment posted to [PR #604](https://github.com/AmitabhainArunachala/dharma_swarm/pull/604#issuecomment-4702584340).

---

## Mission 2: PR Lifecycle

### Inventory

| State | Count |
|-------|-------|
| Open (before this run) | 23 |
| Auto-closed this run | 0 |
| Open (after this run) | 23 |

### CONFLICTING PRs (not yet eligible for auto-close, < 7 days)

| PR | Title | Age | Days to Auto-Close Eligibility |
|----|-------|-----|-------------------------------|
| #588 | fix(security): close post-574 review blockers | ~2.5 d | 4.5 d |
| #586 | feat(governance): add truth graph platform projection | ~2.5 d | 4.5 d |
| #578 | governance(trust-gate): NORTH_STAR §8 scoreboard | ~3.1 d | 3.9 d |
| #564 | fleet: add Devin honest-spine handoff packet | ~3.8 d | 3.2 d |
| #558 | telos: enforce gate on REVIEW-decision self-mods | ~5.1 d | **1.9 d** |

> **Watch:** PR #558 reaches auto-close eligibility in ~1.9 days (approx. 2026-06-16T15:00Z).

### Auto-Closed This Run
None.

### Duplicate Auto-Grounding PRs Flagged

| Older (flagged) | Newer (keep) | Reason |
|----------------|-------------|--------|
| [#595](https://github.com/AmitabhainArunachala/dharma_swarm/pull/595) — "PR lifecycle + spine adoption ops report 2026-06-14 [automated]" | [#604](https://github.com/AmitabhainArunachala/dharma_swarm/pull/604) — "…2026-06-14 12:00Z" | Same-day automated report duplication |

Comment posted on PR #595 recommending close.

### Green-and-Ready (MERGEABLE) PRs

| PR | Title | +/- |
|----|-------|-----|
| #604 | report(governance): PR lifecycle + spine adoption ops report 2026-06-14 12:00Z [automated] | +159/−2 |
| #603 | test(smoke): orchestrate_live constructor smoke suite | +225/−2 |
| #602 | test(complexity): replay metamorphic invariance v1 | +182/−4 |
| #601 | test(hygiene): 5 high-leverage testing improvements | +746/−3 |
| #600 | feat(governance): hygiene delta-ratchet wired into quality membrane | +549/−3 |
| #599 | docs(state): refresh LIVE_OPS_DASHBOARD to 2026-06-14 | +308/−96 |
| #598 | feat(governance): corral re-verifier — gate against importing stale findings | +441/−3 |
| #597 | docs(readme): replace fake make targets with real ones (AS-06) | +16/−10 |
| #596 | chore(governance): refresh spine adoption metric [automated] 2026-06-14 | +7/−204 |
| #595 | report(governance): PR lifecycle + spine adoption ops report 2026-06-14 [automated] | +106/−3 |
| #594 | chore(governance): refresh spine adoption metric [automated] 2026-06-13 | +7/−204 |
| #593 | report(governance): PR lifecycle + spine adoption snapshot 2026-06-13 [automated] | +107/−2 |
| #592 | Bug Corral: signal-graded provenance manifest v2 | +998/−5 |
| #590 | [WIP draft] loop-closure campaign — Loop 1 + cascade wired E2E | +451/−13 |
| #589 | feat(quality): seed one-way quality ratchet + assurance boundary V0 | +4481/−117 |
| #576 | chore(docops): re-verify assertions, renew TTL 2026-06-12 | +1/−1 |
| #562 | fix(evolution): honest archive status, real gates_passed, lineage parent_id | +104/−19 |
| #546 | chore(hygiene): move 17MB semantic-graph evidence to release artifacts | +96/−575233 |

### Recommended Actions for Operator

1. **Close PR #595** — duplicate of #604 (same-day governance report). Comment already posted.
2. **Watch PR #558** — CONFLICTING, reaches 7-day threshold ~2026-06-16T15:00Z. Rebase or close before then.
3. **Rebase PRs #588, #586, #578, #564** — all CONFLICTING; none yet eligible for auto-close but accumulating merge debt.
4. **Review #590 [WIP]** — large draft (451 additions); labeled as not ready. Confirm scope before merge window.
5. **Consider merging chore/governance cluster** — PRs #596, #594, #593, #604, #595 are all small governance-report PRs. Batch-merging or closing superseded ones would reduce open PR count by ~5.

---

_Evidence-only report. Operator holds sole merge authority. No source code modified._
