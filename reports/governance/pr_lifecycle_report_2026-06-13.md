# PR Lifecycle & Spine Adoption Report
**Run timestamp:** 2026-06-13T12:00:33Z
**Operator:** automated governance agent
**Repo:** AmitabhainArunachala/dharma_swarm

---

## Mission 1 — Spine Adoption Metric

**audit_sha:** `9c76b2106d95ff3706ed0fa81f732240dfa01183`

| Metric | Value | Target |
|---|---|---|
| Adoption % (joined + adapter-ready) | **93.8%** | 95.0% |
| Joined (full) | 12 / 16 | — |
| Adapter-ready | 3 / 16 | — |
| Missing | 0 | — |
| Quarantine | 0 | — |
| Legacy | 1 | — |

**Status vs. committed baseline:** No change. adoption_pct held steady at 93.8% — JSON not re-committed.

### Surfaces That Moved Status
None this run.

### Non-Joined Surfaces (gap to 95%)

1. **`tool_registry_dispatch`** — `adapter-ready` (priority 5)
   - File: `dharma_swarm/tool_registry.py`
   - Missing join pattern: `try_begin_idempotent_side_effect` (tool side-effects not idempotency-gated)

2. **`self_modification_loop`** — `adapter-ready` (priority 6)
   - Files: `dharma_swarm/diff_applier.py`, `evolution.py`, `self_improve.py`
   - Missing join pattern: `try_begin_idempotent_side_effect` (apply path not idempotency-gated)

3. **`mcp_tool_access`** — `adapter-ready` (priority 7) — **highest-impact gap**
   - Files: `dharma_swarm/mcp_server.py`, `dharma_context_mcp.py`
   - Missing join patterns (3): `ExecutionIdentity` import, `RuntimeStateStore` write, `record_side_effect` receipt

4. **`legacy_no_identity_escape_hatch`** — `legacy` (priority 10) — acknowledged, invariant-covered, no join required

**Path to 95%:** Promote `mcp_tool_access` to `joined` (3 patterns → highest leverage). Alternatively promote both `tool_registry_dispatch` and `self_modification_loop` (1 pattern each). Neither changes the blended 93.8% until they fully join — the metric uses joined + adapter-ready as numerator, so promoting adapter-ready surfaces to joined improves signal integrity but not the headline percentage. The headline will exceed 95% only if a currently non-tracked surface is added and joins, or if the metric definition narrows to joined-only (currently 75%).

**Comment posted:** https://github.com/AmitabhainArunachala/dharma_swarm/pull/592#issuecomment-4698460730

---

## Mission 2 — PR Lifecycle

### Summary

| Metric | Count |
|---|---|
| Total open (before) | 12 |
| Auto-closed this run | 0 |
| Total open (after) | 12 |
| CONFLICTING (need rebase) | 7 |
| MERGEABLE (green-and-ready) | 5 |
| Duplicate auto-grounding detected | 0 |

### Auto-Close Assessment

**Cutoff:** PRs that are `CONFLICTING` AND created before `2026-06-06T12:00:33Z`

No PRs qualify. Oldest conflicting PR is #546 at **6.0 days old** — threshold is 7 days. Check again in ~24 hours.

### MERGEABLE — Green and Ready

| PR | Title | Age | Notes |
|---|---|---|---|
| #592 | Bug Corral: signal-graded provenance manifest v2 | 0.1d | Most recent; 5 files, +680/-5 |
| #591 | chore(governance): refresh spine adoption metric [automated] | 0.2d | Automated governance; 1 file, +7/-204 |
| #590 | [WIP draft] loop-closure campaign — Loop 1 + cascade E2E | 0.3d | Marked WIP — not ready per title |
| #589 | feat(quality): seed one-way quality ratchet + assurance boundary V0 | 0.9d | Large change: 36 files, +4481/-117 |
| #576 | chore(docops): re-verify assertions, renew TTL 2026-06-12 | 1.8d | Tiny: 1 file, +1/-1 |

### CONFLICTING — Needs Rebase

| PR | Title | Age | Risk |
|---|---|---|---|
| #588 | fix(security): close post-574 review blockers | 1.3d | Security fix — rebase priority high |
| #586 | feat(governance): add truth graph platform projection | 1.3d | 29 files, +2194/-177 — complex rebase |
| #578 | governance(trust-gate): NORTH_STAR §8 scoreboard | 1.8d | 6 files, governance impact |
| #564 | fleet: add Devin honest-spine handoff packet | 2.5d | 3 files, fleet doc |
| #562 | fix(evolution): honest archive status, real gates_passed | 2.9d | 5 files, evolution fix |
| #558 | telos: enforce gate on REVIEW-decision self-mods | 3.9d | 6 files, telos gate |
| #546 | chore(hygiene): move 17MB semantic-graph evidence | 6.0d | ⚠️ Approaching 7-day auto-close threshold tomorrow |

### Duplicate Auto-Grounding PRs

No duplicates detected. Each automated PR targets a unique subject:
- #591: spine adoption metric refresh (only instance)
- #576: docops assertions TTL (only instance)

### Recommended Actions (operator review required)

1. **#546 — WATCH:** 6.0 days old, CONFLICTING. Will qualify for auto-close in ~24 hours if not rebased. Operator should rebase or accept upcoming auto-close.
2. **#588 — PRIORITY REBASE:** Security fix, conflicting. Rebase promptly to avoid staleness.
3. **#590 — WIP:** Marked `[WIP draft]` — not operator-ready despite MERGEABLE status. Do not merge until WIP tag removed.
4. **#591 — STALE AUTOMATION:** Spine adoption metric automated PR. Since this run detected no change in adoption_pct (93.8%), this PR's content is still valid but the operator may wish to merge or close it to reduce queue noise.
5. **Spine gap:** `mcp_tool_access` is the highest-leverage surface (3 missing patterns). A targeted PR wiring `ExecutionIdentity`, `RuntimeStateStore`, and `record_side_effect` into `mcp_server.py` / `dharma_context_mcp.py` would advance spine adoption toward 95%.

---

_This report is evidence-only. Operator holds sole merge authority. No PRs were merged, approved, or source code modified._
