# PR Lifecycle + Spine Adoption Ops Report
Generated: 2026-06-14T12:00:15Z
Operator authority: sole merge/approval right retained by human operator.
No source code was modified. No PRs were merged or approved.

---

## Mission 1: Spine Adoption

### Summary

| Metric | Value | Target |
|---|---|---|
| adoption_pct (joined + adapter-ready) | **93.8%** | 95% |
| joined (fully wired) | 12 / 16 | — |
| adapter-ready (partial, not fully joined) | 3 / 16 | — |
| legacy | 1 / 16 | 0 |
| missing | 0 / 16 | 0 |
| quarantine | 0 / 16 | 0 |
| total tracked surfaces | 16 | — |

**adoption_pct unchanged from committed snapshot** (was 93.8%; audit_sha rotated;
source tree transitioned from `dirty` → `clean` between runs; no surface statuses changed).
No commit/push of spine_adoption_metric.json required (adoption_pct did not change).

### Surface status breakdown

| Surface | Status | Category | Priority |
|---|---|---|---|
| identity_contract | joined | identity | 1 |
| runtime_state_ledger | joined | ledger | 1 |
| runtime_lifecycle_adapter | joined | dispatch | 2 |
| task_board_ingress | joined | ingress | 2 |
| orchestrator_dispatch | joined | dispatch | 3 |
| message_bus_transport | joined | event | 3 |
| a2a_server_ingress | joined | external-agent | 4 |
| artifact_store | joined | artifact | 4 |
| ontology_action_tollbooth | joined | ontology | 5 |
| workflow_checkpoint_replay | joined | checkpoint-replay | 6 |
| nats_jetstream_transport | joined | event | 8 |
| opportunity_refill_research_backend | joined | quarantine | 9 |
| tool_registry_dispatch | **adapter-ready** | tool | 5 |
| self_modification_loop | **adapter-ready** | self-modification | 6 |
| mcp_tool_access | **adapter-ready** | tool | 7 |
| legacy_no_identity_escape_hatch | **legacy** | legacy | 10 |

### Top saturation targets (gap to 95%)

With 16 surfaces, adoption_pct = (joined + adapter_ready) / total = 15/16 = 93.75%.
Reaching 95% requires 16/16 surfaces (next discrete step = 100%). **Single blocker:**

**`legacy_no_identity_escape_hatch` (legacy)**
- Location: `dharma_swarm/runtime_state.py`, `tests/test_runtime_state_invariants.py`
- Evidence: `legacy_no_identity_allowed=True` flag + invariant coverage exists
- Path to adapter-ready: document explicit deprecation of the no-identity bypass with a
  concrete removal target date and replacement receipt path.

**Adapter-ready → joined gaps (idempotency):**
- `tool_registry_dispatch` (`dharma_swarm/tool_registry.py`):
  missing `try_begin_idempotent_side_effect` on tool side-effects
- `self_modification_loop` (`dharma_swarm/diff_applier.py`):
  missing `try_begin_idempotent_side_effect` on apply path
- `mcp_tool_access` (`dharma_swarm/mcp_server.py`, `dharma_swarm/dharma_context_mcp.py`):
  missing ExecutionIdentity import, RuntimeStateStore, and record_side_effect patterns (all 3)

### Comment posted

Spine adoption comment posted to most recent open spine PR:
- PR #601 "test(hygiene): 5 high-leverage testing improvements (mypy ratchet, spine integration…)"
- Comment URL: https://github.com/AmitabhainArunachala/dharma_swarm/pull/601#issuecomment-4701682953

---

## Mission 2: PR Lifecycle

### Open PR count (at run time)

**Total open PRs: 22**

### CONFLICTING PRs — auto-close eligibility (threshold: >7 days old)

Current time: 2026-06-14T12:00:15Z  
7-day cutoff: 2026-06-07T12:00:15Z

| PR | Title | Created | Age (days) | Eligible for auto-close |
|---|---|---|---|---|
| #588 | fix(security): close post-574 review blockers | 2026-06-12T05:43Z | 2.3 | No |
| #586 | feat(governance): add truth graph platform projection | 2026-06-12T05:02Z | 2.3 | No |
| #578 | governance(trust-gate): NORTH_STAR §8 scoreboard | 2026-06-11T16:22Z | 2.8 | No |
| #564 | fleet: add Devin honest-spine handoff packet | 2026-06-10T23:59Z | 3.5 | No |
| #558 | telos: enforce gate on REVIEW-decision self-mods | 2026-06-09T15:03Z | 4.9 | No |

**Result: No PRs auto-closed.** All CONFLICTING PRs are under 5 days old.

### Duplicate auto-grounding PR scan

Checked automated ops report PRs (#593, #594, #595, #596) for shared target PR references:
- #595 and #593 are sequential automated ops reports (different dates); no exact overlap of
  target PR numbers constituting a true duplicate-grounding pattern.
- #596 and #594 are sequential spine adoption metric refresh PRs (different dates).
- No duplicate auto-grounding PRs targeting the same PR number detected.

### Green-and-ready PRs (MERGEABLE, not WIP/draft)

| PR | Title | Created | +lines / -lines |
|---|---|---|---|
| #603 | test(smoke): orchestrate_live constructor smoke suite | 2026-06-14 | +225/-2 |
| #602 | test(complexity): replay metamorphic invariance v1 | 2026-06-14 | +182/-4 |
| #601 | test(hygiene): 5 high-leverage testing improvements | 2026-06-14 | +746/-3 |
| #600 | feat(governance): hygiene delta-ratchet wired into quality membrane | 2026-06-14 | +549/-3 |
| #599 | docs(state): refresh LIVE_OPS_DASHBOARD to 2026-06-14 | 2026-06-14 | +308/-96 |
| #598 | feat(governance): corral re-verifier — gate against importing stale findings | 2026-06-14 | +441/-3 |
| #597 | docs(readme): replace fake make targets with real ones (AS-06) | 2026-06-14 | +16/-10 |
| #596 | chore(governance): refresh spine adoption metric [automated] 2026-06-14 | 2026-06-14 | +7/-204 |
| #595 | report(governance): PR lifecycle + spine adoption ops report 2026-06-14 [automated] | 2026-06-14 | +106/-3 |
| #594 | chore(governance): refresh spine adoption metric [automated] 2026-06-13 | 2026-06-13 | +7/-204 |
| #593 | report(governance): PR lifecycle + spine adoption snapshot 2026-06-13 [automated] | 2026-06-13 | +107/-2 |
| #592 | Bug Corral: signal-graded provenance manifest v2 | 2026-06-13 | +998/-5 |
| #589 | feat(quality): seed one-way quality ratchet + assurance boundary V0 | 2026-06-12 | +4481/-117 |
| #590 | [WIP draft] loop-closure campaign | 2026-06-13 | +451/-13 |
| #576 | chore(docops): re-verify assertions, renew TTL 2026-06-12 | 2026-06-11 | +1/-1 |
| #562 | fix(evolution): honest archive status, real gates_passed, lineage parent_id | 2026-06-10 | +104/-19 |
| #546 | chore(hygiene): move 17MB semantic-graph evidence to release artifacts | 2026-06-07 | +87/-575233 |

### Recommended operator actions

1. **Rebase and reopen CONFLICTING PRs** (none auto-closed; monitor — all 5 will cross 7-day
   threshold between 2026-06-16 and 2026-06-19 if not rebased):
   - #558 hits 7 days: ~2026-06-16T15Z
   - #564 hits 7 days: ~2026-06-17T23Z
   - #578 hits 7 days: ~2026-06-18T16Z
   - #586 hits 7 days: ~2026-06-19T05Z
   - #588 hits 7 days: ~2026-06-19T05Z

2. **Stale automated PRs**: #594 and #596 (both "spine adoption metric") are superseded by
   each other — the newer run (#596) contains the fresher snapshot. Consider closing #594.
   Similarly, #593 is superseded by #595 for the ops report. Operator discretion.

3. **WIP PR #590** ("[WIP draft] loop-closure campaign") is MERGEABLE but explicitly marked
   as not ready. No action needed; flag for operator awareness.

4. **Large PR #589** (+4481/-117 across 36 files) is MERGEABLE. Recommend thorough review
   before merge given scope.

5. **Spine adoption path to 95%**: promote `legacy_no_identity_escape_hatch` from legacy
   status (document replacement/deprecation path). Single lever delivers 93.8% → 100%.

### Final counts

| Metric | Value |
|---|---|
| Total open PRs (before run) | 22 |
| Auto-closed this run | 0 |
| Total open PRs (after run) | 22 |
| CONFLICTING PRs | 5 |
| MERGEABLE PRs | 17 |
| Green-and-ready (MERGEABLE, not WIP) | 16 |
