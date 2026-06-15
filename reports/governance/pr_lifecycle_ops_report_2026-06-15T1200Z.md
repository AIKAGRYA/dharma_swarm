# PR Lifecycle + Spine Adoption Ops Report
**Run:** 2026-06-15T12:00Z  |  **Operator:** automated ops agent

---

## Mission 1: Spine Adoption

| Metric | Value |
|---|---|
| adoption_pct | **93.8%** |
| Target | 95% |
| joined | 12 (75.0%) |
| adapter-ready | 3 |
| missing | 0 |
| quarantine | 0 |
| legacy | 1 |
| total surfaces | 16 |
| audit_sha | 9c76b2106d95ff3706ed0fa81f732240dfa01183 |
| source_status | clean |

### Status vs. previous run
- adoption_pct: **unchanged** at 93.8% (all counters stable)
- JSON not recommitted (adoption_pct unchanged per governance rule)
- Spine status comment posted to PR #613

### Gap to 95%
The single blocking surface is the intentional legacy escape hatch:

| Surface | Status | Blocker |
|---|---|---|
| `legacy_no_identity_escape_hatch` | **legacy** | Must be retired (not just bypassed) — migrate off `legacy_no_identity_allowed=True` |

**Promotion path (adapter-ready → joined; won't raise % but deepens integrity):**

| Surface | Missing pattern |
|---|---|
| `tool_registry_dispatch` | `try_begin_idempotent_side_effect` in `tool_registry.py` |
| `self_modification_loop` | `try_begin_idempotent_side_effect` on apply path in `diff_applier.py` |
| `mcp_tool_access` | ExecutionIdentity import + RuntimeStateStore + `record_side_effect` in `mcp_server.py` / `dharma_context_mcp.py` |

---

## Mission 2: PR Lifecycle

### Counts

| | Count |
|---|---|
| Total open PRs (before) | 24 |
| Auto-closed this run | **0** |
| Total open PRs (after) | 24 |
| MERGEABLE (green) | 23 |
| CONFLICTING | 1 |
| WIP/draft (of MERGEABLE) | 1 |
| **Truly green-and-ready** | **22** |

### Conflicting PRs

| PR | Title | Created | Age | Action |
|---|---|---|---|---|
| #588 | fix(security): close post-574 review blockers | 2026-06-12T05:43Z | ~3 days | Monitor — auto-close threshold is 7 days (triggers 2026-06-19) |

### WIP / Not-ready PRs

| PR | Title | Note |
|---|---|---|
| #590 | [WIP draft] loop-closure campaign — Loop 1 + cascade wired E2E | Explicitly draft — not ready per title |

### Duplicate auto-grounding PRs
None detected. No PRs with auto-grounding patterns found targeting the same PR number.

### Green-and-ready PRs (MERGEABLE, not WIP) — 22 total

| # | Title | +/- |
|---|---|---|
| 613 | report(governance): PR lifecycle + spine adoption ops report 2026-06-15 06:00Z [automated] | +107/−207 |
| 612 | chore(governance): refresh spine adoption metric [automated] 2026-06-15 | +7/−204 |
| 610 | fix(stage0): make main honestly green under pipefail CI (safe/unowned subset) | +143/−22 |
| 609 | refresh(docs+state): onboard-doc stack reconciliation 2026-06-15 | +665/−1022 |
| 608 | fix(assurance): claude_code provider accepts its anthropic model family | +9/−1 |
| 607 | ci(tests): pipefail so pytest failures actually fail the gate | +11/−1 |
| 603 | test(smoke): orchestrate_live constructor smoke suite | +241/−4 |
| 602 | test(complexity): replay metamorphic relations (honest L2 layer) | +274/−4 |
| 601 | test(hygiene): 5 high-leverage testing improvements | +748/−5 |
| 600 | feat(governance): hygiene delta-ratchet wired into quality membrane | +551/−5 |
| 599 | docs(state): refresh LIVE_OPS_DASHBOARD to 2026-06-14 | +310/−98 |
| 598 | feat(governance): corral re-verifier | +443/−5 |
| 597 | docs(readme): replace fake make targets with real ones (AS-06) | +17/−11 |
| 592 | Bug Corral: signal-graded provenance manifest v2 | +998/−5 |
| 589 | feat(quality): seed one-way quality ratchet + assurance boundary V0 | +4481/−117 |
| 586 | feat(governance): add truth graph platform projection | +2191/−174 |
| 578 | governance(trust-gate): NORTH_STAR §8 scoreboard | +717/−4 |
| 576 | chore(docops): re-verify assertions, renew TTL 2026-06-12 | +1/−1 |
| 564 | fleet: add Devin honest-spine handoff packet | +86/−4 |
| 562 | fix(evolution): honest archive status, real gates_passed, lineage parent_id | +104/−19 |
| 558 | telos: enforce gate on REVIEW-decision self-mods (WS4a — partial) | +507/−12 |
| 546 | chore(hygiene): move 17MB semantic-graph evidence to release artifacts | +98/−575235 |

### Recommended Actions

1. **PR #588** — CONFLICTING: Rebase and re-open before 2026-06-19 or it will be auto-closed on next run.
2. **PR #546** — 575k deletions: Very large hygiene PR — review carefully before merge.
3. **PR #589** — 4.5k additions: Large ratchet/assurance PR — deserves deliberate review.
4. **PR #590** — Explicit WIP: Do not merge until marked ready.
5. **Queue depth:** 22 green PRs is a large backlog. Operator should consider prioritized merge cadence.

---

_This report is a witness artifact. Operator holds sole merge authority. No PRs were merged or approved by this run._
