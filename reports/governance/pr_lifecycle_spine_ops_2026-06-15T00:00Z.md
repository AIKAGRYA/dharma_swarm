# PR Lifecycle + Spine Adoption Ops Report
**Run timestamp:** 2026-06-15T00:00:30Z  
**Agent:** Dharma Swarm ops agent (automated)  
**Report type:** `report` — dated descriptive output, not doctrine.

---

## Mission 1: Spine Adoption

| Metric | Value |
|--------|-------|
| **adoption_pct** | **93.8%** (target: 95%) |
| joined | 12 / 16 (75.0%) |
| adapter-ready | 3 / 16 |
| legacy | 1 / 16 |
| missing | 0 |
| quarantine | 0 |
| total surfaces | 16 |

**Status vs last commit:** adoption_pct unchanged at 93.8%. No JSON commit triggered (condition: pct must change).

**Gap to 95% target:** 1.2 pp — 1 additional surface must graduate from adapter-ready → joined.

### Top saturation targets

| Priority | Surface ID | Status | Missing pattern |
|----------|-----------|--------|-----------------|
| 5 | `tool_registry_dispatch` | adapter-ready | `try_begin_idempotent_side_effect` in `tool_registry.py` |
| 6 | `self_modification_loop` | adapter-ready | `try_begin_idempotent_side_effect` on apply path (`diff_applier.py`) |
| 7 | `mcp_tool_access` | adapter-ready | `ExecutionIdentity` import, `RuntimeStateStore` write, `record_side_effect` receipt — all 3 absent in `mcp_server.py` / `dharma_context_mcp.py` |
| 10 | `legacy_no_identity_escape_hatch` | legacy | Explicit and test-covered — no action required |

**Surfaces that moved status:** None.

**Celebration threshold:** Not yet reached (93.8% < 95%). Nearest win: wire `try_begin_idempotent_side_effect` into `tool_registry.py` (single-pattern delta).

**Spine adoption comment posted on:** PR #596 (`chore(governance): refresh spine adoption metric [automated] 2026-06-14`)

---

## Mission 2: PR Lifecycle

### Summary

| Stat | Count |
|------|-------|
| Total open PRs before run | 24 |
| Auto-closed (CONFLICTING > 7 days) | 0 |
| Duplicate ops reports flagged | 2 |
| Total open PRs after run | 24 |

### CONFLICTING PRs — age check

No CONFLICTING PRs older than 7 days found. All conflicting PRs are 2–6 days old as of 2026-06-15T00:00Z.

| PR | Title | Age | Action |
|----|-------|-----|--------|
| #588 | fix(security): close post-574 review blockers | ~2.8 days | Monitor |
| #586 | feat(governance): add truth graph platform projection | ~2.8 days | Monitor |
| #578 | governance(trust-gate): NORTH_STAR §8 scoreboard | ~3.3 days | Monitor |
| #564 | fleet: add Devin honest-spine handoff packet | ~4.0 days | Monitor |
| #558 | telos: enforce gate on REVIEW-decision self-mods | ~5.4 days | Monitor |

**Next check window for auto-close:** PRs #558 and #564 will cross the 7-day threshold on 2026-06-16 if unresolved.

### Duplicate auto-grounding PRs flagged

Three same-day ops report PRs exist for 2026-06-14:

| PR | Created | Action |
|----|---------|--------|
| #605 | 2026-06-14T18:01Z | **KEEP** (newest) |
| #604 | 2026-06-14T12:04Z | Flagged for close — comment posted |
| #595 | 2026-06-14T00:04Z | Flagged for close — comment posted |

### Green-and-ready PRs (MERGEABLE, no blocking status)

PRs that are mergeable and have no flags — operator may review at will:

- #605 report(governance): PR lifecycle + spine adoption ops report 2026-06-14 18:00Z
- #603 test(smoke): orchestrate_live constructor smoke suite
- #602 test(complexity): replay metamorphic invariance v1
- #601 test(hygiene): 5 high-leverage testing improvements
- #600 feat(governance): hygiene delta-ratchet wired into quality membrane
- #599 docs(state): refresh LIVE_OPS_DASHBOARD to 2026-06-14
- #598 feat(governance): corral re-verifier — gate against importing stale findings
- #597 docs(readme): replace fake make targets with real ones
- #596 chore(governance): refresh spine adoption metric [automated] 2026-06-14
- #595 report(governance): PR lifecycle + spine adoption ops report 2026-06-14 (duplicate flagged)
- #594 chore(governance): refresh spine adoption metric [automated] 2026-06-13
- #593 report(governance): PR lifecycle + spine adoption snapshot 2026-06-13
- #592 Bug Corral: signal-graded provenance manifest v2
- #590 [WIP draft] loop-closure campaign (self-declared not ready)
- #589 feat(quality): seed one-way quality ratchet
- #576 chore(docops): re-verify assertions, renew TTL
- #562 fix(evolution): honest archive status, real gates_passed
- #546 chore(hygiene): move 17MB semantic-graph evidence to release artifacts

### Recommended actions for operator

1. **Rebase or close** #558, #564, #578, #586, #588 — all are CONFLICTING; #558 will hit the 7-day auto-close threshold 2026-06-16T15:03Z.
2. **Close** #604 and #595 (duplicate same-day ops reports; superseded by #605).
3. **Review** `tool_registry_dispatch` idempotency gap — single-line change to reach 95% spine adoption.
4. **Review** `mcp_tool_access` — 3 missing joined patterns; highest-effort target.

---

> Evidence-only report. Operator holds sole merge authority. No source code was modified.
