# PR Lifecycle + Spine Adoption Ops Report — 2026-06-14T00:00:17Z

**Run type:** automated governance ops  
**Repo:** AmitabhainArunachala/dharma_swarm  
**Operator holds sole merge authority. Agent performed evidence/comment actions only.**

---

## Mission 1: Spine Adoption Tracking

### Result
| Metric | Value |
|--------|-------|
| adoption_pct | **93.8%** |
| target | 95.0% |
| gap | 1.2pp (requires 16/16 surfaces at current scale) |
| joined_count | 12 (75.0%) |
| adapter_ready_count | 3 (18.8%) |
| legacy_count | 1 (6.2%) |
| quarantine_count | 0 |
| missing_count | 0 |
| total_surfaces | 16 |
| audit_sha | 9c76b2106d95ff3706ed0fa81f732240dfa01183 |
| source_status | clean (was: dirty) |

### Status Change vs. Committed
- adoption_pct: **unchanged** (93.8% → 93.8%) — JSON **not re-committed**
- audit_sha rotated; source_status transitioned dirty → clean (uncommitted changes were cleared)
- No surface reclassifications

### Remaining Gap to 95%
With 16 total surfaces, ≥95% requires **all 16** surfaces to be joined or adapter-ready (ceil(0.95 × 16) = 16).

**Single blocking surface:**
- `legacy_no_identity_escape_hatch` (priority 10, legacy) — intentional escape hatch in `runtime_state.py` with invariant test coverage. Operator decision required to advance.

**Alternative path:** grow tracked surfaces to ≥20; 19/20 = 95% would permit one non-joined gap.

### Top Saturation Targets (adapter-ready → joined)
Note: these 3 upgrades improve correctness/auditability but do NOT increase adoption_pct while the legacy surface persists.

1. `tool_registry_dispatch` (priority 5) — needs `try_begin_idempotent_side_effect` in `dharma_swarm/tool_registry.py`
2. `self_modification_loop` (priority 6) — needs `try_begin_idempotent_side_effect` in `dharma_swarm/diff_applier.py`
3. `mcp_tool_access` (priority 7) — needs `ExecutionIdentity` import + `RuntimeStateStore` wiring + `record_side_effect` receipts in `dharma_swarm/mcp_server.py` / `dharma_swarm/dharma_context_mcp.py`

### Action Taken
- Comment posted on most recent open spine PR **#594**: adoption_pct vs target, surface movement (none), gap analysis, saturation targets
  - URL: https://github.com/AmitabhainArunachala/dharma_swarm/pull/594#issuecomment-4700166721

---

## Mission 2: PR Lifecycle

### Open PRs Before This Run: 14

### Auto-Close Candidates (CONFLICTING + older than 7 days)
**None.** All CONFLICTING PRs are younger than 7 days. Closest to threshold:

| PR | Title | Age (days) | Days to Threshold |
|----|-------|-----------|------------------|
| #546 | chore(hygiene): move 17MB semantic-graph evidence to release artifacts | ~6.5 | ~0.5 |
| #558 | telos: enforce gate on REVIEW-decision self-mods | ~4.4 | ~2.6 |
| #564 | fleet: add Devin honest-spine handoff packet | ~4.0 | ~3.0 |
| #562 | fix(evolution): honest archive status, real gates_passed, lineage parent_id | ~3.4 | ~3.6 |
| #578 | governance(trust-gate): NORTH_STAR §8 scoreboard | ~2.3 | ~4.7 |
| #586 | feat(governance): add truth graph platform projection | ~1.8 | ~5.2 |
| #588 | fix(security): close post-574 review blockers | ~1.8 | ~5.2 |

> ⚠️ **#546 will cross the 7-day auto-close threshold in ~12 hours** if it remains CONFLICTING. Operator should assess: rebase or intentionally preserve.

### PRs Closed This Run
**0** — no auto-closes executed.

### Open PRs After This Run: 14 (unchanged)

### Duplicate Auto-Grounding PRs Flagged
| Older PR | Newer PR | Action |
|----------|----------|--------|
| **#591** "chore(governance): refresh spine adoption metric [automated]" (2026-06-13T06:01) | **#594** "chore(governance): refresh spine adoption metric [automated] 2026-06-13" (2026-06-13T18:03) | Comment posted on #591 suggesting close; keep #594 |

Comment URL: https://github.com/AmitabhainArunachala/dharma_swarm/pull/591#issuecomment-4700167033

### Green-and-Ready PRs (MERGEABLE, not flagged)
| PR | Title | Additions | Deletions |
|----|-------|-----------|-----------|
| #594 | chore(governance): refresh spine adoption metric [automated] 2026-06-13 | 7 | 204 |
| #593 | report(governance): PR lifecycle + spine adoption snapshot 2026-06-13 [automated] | 107 | 2 |
| #592 | Bug Corral: signal-graded provenance manifest v2 (gated, no deletions yet) | 998 | 5 |
| #591 | chore(governance): refresh spine adoption metric [automated] *(duplicate — flagged)* | 7 | 204 |
| #590 | [WIP draft] loop-closure campaign — Loop 1 + cascade wired E2E | 451 | 13 |
| #589 | feat(quality): seed one-way quality ratchet + assurance boundary V0 | 4481 | 117 |
| #576 | chore(docops): re-verify assertions, renew TTL 2026-06-12 | 1 | 1 |

### Recommended Actions for Operator
1. **Rebase or close #546** (CONFLICTING hygiene PR, ~6.5 days old — crosses auto-close threshold ~2026-06-14T11:16Z)
2. **Close #591** (duplicate spine adoption metric PR; #594 is the canonical copy)
3. **Assess #558, #564, #562** (CONFLICTING, 3–4.5 days old; should be rebased before they hit threshold)
4. **Review WIP #590** — marked "not ready" in title; verify whether loop-closure work is complete enough to graduate
5. **Idempotency hardening** — consider targeting `tool_registry_dispatch` and `self_modification_loop` to close their idempotency gate gaps (no merge blockers, just trust improvements)

---

*Generated by Dharma Swarm ops agent — evidence-only, no merges or source code changes.*
