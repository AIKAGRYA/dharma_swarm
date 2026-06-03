# Ops Run Report — 2026-06-03T12:00Z

**Agent:** Dharma Swarm ops agent (Oz)
**Run ID:** 019e8d5a-dc2a-7898-9db1-2a1f70a728dc
**Audit SHA:** 3e46109b216be688a8c0ffb9776fff5ec9462a45

---

## Mission 1: Spine Adoption Tracking

### Result
| Metric | Value |
|--------|-------|
| adoption_pct | **75.0%** |
| target | 95.0% |
| gap | −20 pp (need 4 more surfaces joined) |
| joined | 8 / 16 |
| adapter-ready | 4 / 16 |
| legacy | 2 / 16 |
| quarantine | 1 / 16 |
| missing | 1 / 16 |

### Status Movements
None — identical to previous committed metric.

### Actions Taken
- `reports/governance/spine_adoption_metric.json` updated and pushed to branch `chore/spine-adoption-metric-refresh-20260603`
- Draft PR **#463** opened for operator review
- Adoption status comment posted on PR **#462** (most recent open spine PR)

### Top Saturation Targets (fastest path to 95%)
1. `ontology_action_tollbooth` (adapter-ready) — 1 missing pattern: `RuntimeStateStore` write in `dharma_swarm/ontology.py`
2. `tool_registry_dispatch` (adapter-ready) — 1 missing pattern: idempotency gate in `dharma_swarm/tool_registry.py`
3. `self_modification_loop` (adapter-ready) — 1 missing pattern: idempotency gate on apply path in `dharma_swarm/diff_applier.py`
4. `mcp_tool_access` (adapter-ready) — 3 missing patterns: identity, ledger write, receipts in `dharma_swarm/mcp_server.py` / `dharma_swarm/dharma_context_mcp.py`
5. `workflow_checkpoint_replay` (legacy) — 3 missing patterns: identity, ledger write, receipt; currently using filesystem checkpoints and EventLog replay

---

## Mission 2: PR Lifecycle

### Summary
| Metric | Value |
|--------|-------|
| Total open PRs (before) | 48 |
| CONFLICTING (auto-close eligible) | 0 |
| Auto-closed | 0 |
| Total open PRs (after) | 49 (new spine metric PR #463 added) |
| Green and MERGEABLE | 49 / 49 |
| Duplicate auto-grounding flags | 3 PRs flagged |

### Auto-Closures
None — no PRs met the CONFLICTING + >7 days criteria.

### Duplicate Auto-Grounding Flags
| Target PR | Older Duplicate | Keep | Action |
|-----------|----------------|------|--------|
| #409 | **#419** | #421 | Comment posted suggesting close |
| #409 | **#413** | #421 | Comment posted suggesting close |
| #406 | **#415** | #417 | Comment posted suggesting close |

All 3 flagged PRs received comments with the superseding PR number and branch-preservation notice.

### Green-and-Ready PRs (MERGEABLE, no conflicts)
All 49 open PRs report `MERGEABLE`. Operator holds sole merge authority.

### Recommended Actions
1. Review and merge **#463** (spine metric refresh) when CI passes.
2. Close or archive **#419**, **#413**, **#415** (duplicate auto-groundings — operator discretion).
3. Priority merge candidate: **#453** ("fix(docops): widen canonical_guard ignore — unblocks 24 CI-failing PRs") — this is a blocker for multiple downstream PRs.
4. Continue spine saturation work targeting `ontology_action_tollbooth` and `tool_registry_dispatch` for the cheapest +2 joined surfaces.

---

_This report is type: `report`. It makes no authority claims. Evidence-only; operator holds sole merge authority._
