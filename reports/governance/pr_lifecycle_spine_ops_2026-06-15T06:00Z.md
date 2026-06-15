# PR Lifecycle + Spine Adoption Ops Report
**Run timestamp:** 2026-06-15T06:00:17Z  
**Report type:** report (dated descriptive output)  
**Authority:** subordinate to `docs/governance/CANONICAL_DOC_STACK.md`

---

## Mission 1: Spine Adoption Tracking

### Metric Summary
| Field | Value |
|---|---|
| adoption_pct | **93.8%** |
| Target | 95.0% |
| Gap remaining | **1.2 pp** — 1 surface upgrade needed |
| joined | 12 / 16 |
| adapter-ready | 3 / 16 |
| legacy | 1 / 16 |
| missing | 0 |
| quarantine | 0 |
| total_surfaces | 16 |
| audit_sha | 9c76b2106d95ff3706ed0fa81f732240dfa01183 |

### Surface Status Changes vs Previous Run
No surfaces changed classification status. Adoption remains at 93.8% — metric JSON was refreshed with updated evidence and audit_sha.

### Remaining Gaps to 95% Target
Promoting **any single** adapter-ready surface to joined clears the 95% bar:

1. **`tool_registry_dispatch`** — `dharma_swarm/tool_registry.py`  
   Missing: `try_begin_idempotent_side_effect` gate before tool side-effects fire.  
   **Easiest win (1 file, 1 missing pattern).**

2. **`self_modification_loop`** — `diff_applier.py`, `evolution.py`, `self_improve.py`  
   Missing: `try_begin_idempotent_side_effect` gate on the apply path.

3. **`mcp_tool_access`** — `mcp_server.py`, `dharma_context_mcp.py`  
   Missing all three joined patterns: `ExecutionIdentity` import, `RuntimeStateStore` write, `record_side_effect` receipts.

### Actions Taken
- Refreshed `reports/governance/spine_adoption_metric.json` (branch: `chore/spine-adoption-metric-refresh`, PR: #612)
- Posted adoption status comment on PR #612 (most recent open spine PR)

---

## Mission 2: PR Lifecycle

### PR Counts
| State | Count |
|---|---|
| Open PRs before run | 29 |
| New PRs opened this run | 1 (PR #612 — spine metric refresh) |
| Open PRs after run | 30 |
| Auto-closed (CONFLICTING > 7 days) | **0** |
| MERGEABLE | 24 |
| CONFLICTING | 5 |

### CONFLICTING PRs — Status & Risk
All conflicting PRs are under the 7-day auto-close threshold:

| PR | Title | Age | Threshold |
|---|---|---|---|
| #588 | fix(security): close post-574 review blockers | ~3 days | Safe |
| #586 | feat(governance): add truth graph platform projection | ~3 days | Safe |
| #578 | governance(trust-gate): NORTH_STAR §8 scoreboard | ~4 days | Safe |
| #564 | fleet: add Devin honest-spine handoff packet | ~5 days | Safe |
| #558 | telos: enforce gate on REVIEW-decision self-mods | **~5.6 days** | ⚠️ Crosses threshold ~2026-06-16T15:03Z |

**Next auto-close risk:** PR #558 will cross 7 days at approximately 2026-06-16T15:03Z. Operator should rebase or close proactively.

### Green-and-Ready PRs (MERGEABLE, not WIP)
PRs ready for operator review and merge: #610, #609, #608, #607, #603, #602, #601, #600, #599, #598, #597, #592, #589, #576, #562, #546.  
(Excludes accumulated automated report duplicates and WIP draft #590.)

### Duplicate Auto-Grounding PRs Flagged
Older automated PRs that are superseded by newer equivalents — comments posted suggesting close:

**Spine adoption metric** (superseded by PR #612):
- PR #596 — `chore(governance): refresh spine adoption metric [automated] 2026-06-14`
- PR #594 — `chore(governance): refresh spine adoption metric [automated] 2026-06-13`

**Ops reports** (superseded by PR #606 — 2026-06-15T00:00Z):
- PR #605 — `report(governance): PR lifecycle + spine adoption ops report 2026-06-14 18:00Z`
- PR #604 — `report(governance): PR lifecycle + spine adoption ops report 2026-06-14 12:00Z`
- PR #595 — `report(governance): PR lifecycle + spine adoption ops report 2026-06-14`
- PR #593 — `report(governance): PR lifecycle + spine adoption snapshot 2026-06-13`

### Recommended Actions for Operator
1. **Merge spine metric refresh** (PR #612) — evidence-only governance update, no source changes.
2. **Close accumulated duplicate PRs**: #596, #594, #605, #604, #595, #593 — 6 stale automated PRs cluttering the queue.
3. **Rebase or close PR #558** before 2026-06-16T15:03Z to avoid auto-close.
4. **Review CONFLICTING PRs #586, #578, #564, #588** — rebase when ready.
5. **Prioritize `tool_registry_dispatch` idempotency gate** to clear the 95% spine adoption target.

---

> Evidence-only report. Operator holds sole merge authority. No source code modified.
