# PR Lifecycle + Spine Adoption Ops Report
**Generated:** 2026-06-18T00:00:23Z | **Operator:** Oz autonomous agent | **Type:** report

---

## Mission 1: Spine Adoption

| Metric | Value |
|---|---|
| **adoption_pct** | 93.8% |
| **Target** | 95% |
| **Gap** | 1.2 pp |
| joined | 12 (75.0%) |
| adapter-ready | 3 (18.8%) |
| legacy | 1 (6.3%) |
| missing | 0 |
| quarantine | 0 |
| total_surfaces | 16 |
| audit_sha | 2368f26c0c60ed162454f7d14fab40694f2c7880 |

### Status vs Committed Version
- `adoption_pct`: **unchanged** (93.8% → 93.8%) — no commit triggered
- `source_status`: **dirty → clean** (working tree is now clean)
- `audit_sha` rotated: `a511aa6` → `2368f26`

### Surface Status Map
| Surface ID | Category | Status |
|---|---|---|
| identity_contract | identity | ✅ joined |
| runtime_state_ledger | ledger | ✅ joined |
| runtime_lifecycle_adapter | dispatch | ✅ joined |
| task_board_ingress | ingress | ✅ joined |
| orchestrator_dispatch | dispatch | ✅ joined |
| message_bus_transport | event | ✅ joined |
| a2a_server_ingress | external-agent | ✅ joined |
| artifact_store | artifact | ✅ joined |
| ontology_action_tollbooth | ontology | ✅ joined |
| workflow_checkpoint_replay | checkpoint-replay | ✅ joined |
| nats_jetstream_transport | event | ✅ joined |
| opportunity_refill_research_backend | quarantine | ✅ joined |
| tool_registry_dispatch | tool | 🔶 adapter-ready |
| self_modification_loop | self-modification | 🔶 adapter-ready |
| mcp_tool_access | tool | 🔶 adapter-ready |
| legacy_no_identity_escape_hatch | legacy | 🕹 legacy |

### Top Saturation Targets (adapter-ready → joined)
1. **tool_registry_dispatch** — add `try_begin_idempotent_side_effect` gate in `dharma_swarm/tool_registry.py`
2. **self_modification_loop** — add idempotency gate on apply path in `dharma_swarm/diff_applier.py`
3. **mcp_tool_access** — wire ExecutionIdentity import, RuntimeStateStore write, and `record_side_effect` receipt in `dharma_swarm/mcp_server.py` + `dharma_context_mcp.py`

> Any single promotion to joined reaches 16/16 = 100% (far exceeding 95%). 93.8% represents the current integer floor.

### Commented On
- [PR #627](https://github.com/AmitabhainArunachala/dharma_swarm/pull/627) — spine adoption status, surface breakdown, saturation targets

---

## Mission 2: PR Lifecycle

### Open PRs Before This Run: 19

| # | Title | Mergeable | Age (days) | Action |
|---|---|---|---|---|
| #627 | chore(governance): refresh spine adoption metric [automated] 2026-06-17T1802Z | MERGEABLE | 0.25 | Keep (newest spine metric) |
| #626 | report(governance): PR lifecycle + spine adoption ops report 2026-06-17T1200Z [automated] | MERGEABLE | 0.5 | Keep (newest ops report) |
| #625 | feat(orientation): graph-shaped queries + time-to-orientation measurement | MERGEABLE | 0.7 | 🟢 Ready |
| #624 | report(governance): PR lifecycle + spine adoption ops report 2026-06-17T0600Z [automated] | MERGEABLE | 0.75 | 🚩 Duplicate ops report — flagged |
| #623 | Add Devin A2A agent daemon for persistent fleet presence | MERGEABLE | 0.8 | 🟢 Ready |
| #622 | chore(governance): refresh spine adoption metric [automated] 2026-06-17T00:00Z | MERGEABLE | 1.0 | 🚩 Duplicate spine metric — flagged |
| #621 | chore(governance): refresh spine adoption metric [automated] 2026-06-16T18:00Z | MERGEABLE | 1.25 | 🚩 Duplicate spine metric — flagged |
| #620 | palantir-pilot: deep public-doc corpus + retrieval tuning + domain submaps | MERGEABLE | 1.4 | 🟢 Ready |
| #619 | ci(governance): wire anti-slop enforcement gates | MERGEABLE | 1.4 | 🟢 Ready |
| #618 | report(governance): PR lifecycle + spine adoption ops report 2026-06-16T1200Z [automated] | MERGEABLE | 1.5 | 🚩 Duplicate ops report — flagged |
| #615 | chore(governance): refresh spine adoption metric [automated] 2026-06-16 | MERGEABLE | 2.0 | 🚩 Duplicate spine metric — flagged |
| #614 | report(governance): PR lifecycle + spine adoption ops report 2026-06-15T12:00Z [automated] | CONFLICTING | 2.5 | ⚠️ Conflict + duplicate ops report — flagged |
| #613 | report(governance): PR lifecycle + spine adoption ops report 2026-06-15 06:00Z [automated] | CONFLICTING | 2.75 | ⚠️ Conflict + duplicate ops report — flagged |
| #612 | chore(governance): refresh spine adoption metric [automated] 2026-06-15 | MERGEABLE | 3.0 | 🚩 Duplicate spine metric — flagged |
| #609 | refresh(docs+state): onboard-doc stack reconciliation 2026-06-15 | MERGEABLE | 3.4 | 🟢 Ready |
| #607 | ci(tests): pipefail so pytest failures actually fail the gate | MERGEABLE | 3.5 | 🟢 Ready |
| #602 | test(complexity): replay metamorphic relations (honest L2 layer) | CONFLICTING | 3.6 | ⚠️ Conflict — needs rebase |
| #599 | docs(state): refresh LIVE_OPS_DASHBOARD to 2026-06-14 | MERGEABLE | 3.75 | 🟢 Ready |
| #592 | Bug Corral: signal-graded provenance manifest v2 | CONFLICTING | 4.6 | ⚠️ Conflict — needs rebase |

### Auto-Close Actions (CONFLICTING + older than 7 days)
**None.** All 4 CONFLICTING PRs (#614, #613, #602, #592) are ≤ 4.6 days old (threshold: 7 days). No auto-close triggered.

### Duplicate Auto-Grounding PRs Flagged
**Spine adoption metric series** (keep #627):
- #622 — flagged, commented
- #621 — flagged, commented
- #615 — flagged, commented
- #612 — flagged, commented

**Ops report series** (keep #626):
- #624 — flagged, commented
- #618 — flagged, commented
- #614 — flagged, commented (also CONFLICTING)
- #613 — flagged, commented (also CONFLICTING)

### Open PRs After This Run: 19 (no closes executed — no CONFLICTING PRs > 7 days)

### Green-and-Ready PRs (MERGEABLE, substantive)
| # | Title |
|---|---|
| #625 | feat(orientation): graph-shaped queries + time-to-orientation measurement |
| #623 | Add Devin A2A agent daemon for persistent fleet presence |
| #620 | palantir-pilot: deep public-doc corpus + retrieval tuning + domain submaps |
| #619 | ci(governance): wire anti-slop enforcement gates |
| #609 | refresh(docs+state): onboard-doc stack reconciliation 2026-06-15 |
| #607 | ci(tests): pipefail so pytest failures actually fail the gate |
| #599 | docs(state): refresh LIVE_OPS_DASHBOARD to 2026-06-14 |

### Recommended Actions for Operator
1. **Merge or close duplicate automation PRs**: #612, #615, #618, #621, #622, #624 (spine metric and ops report duplicates — superseded by #627 and #626).
2. **Rebase CONFLICTING PRs**: #602, #592 approaching age threshold; #614 and #613 are also conflicting duplicates already flagged.
3. **Review green-and-ready**: #625 (orientation graph queries), #623 (Devin A2A daemon), #620 (palantir corpus), #619 (anti-slop CI gates), #609, #607, #599 are all MERGEABLE with no conflicts.
4. **Spine saturation**: Promote one adapter-ready surface (priority: `tool_registry_dispatch` — single-pattern gap) to cross the 95% threshold.

---

*Operator holds sole merge/approve authority. No source code modified. Report only.*
