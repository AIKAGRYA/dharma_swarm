# PR Lifecycle + Spine Adoption Ops Report
**Generated:** 2026-06-17T12:00Z | **Automated Run**

---

## Mission 1: Spine Adoption Metric

| Metric | Value |
|---|---|
| adoption_pct | **93.8%** |
| Target | 95.0% |
| Gap | 1.2 pp (1 surface needed) |
| joined_count | 12 / 16 |
| adapter_ready_count | 3 |
| legacy_count | 1 |
| missing_count | 0 |
| quarantine_count | 0 |
| Total surfaces | 16 |

**No change from committed snapshot** — adoption_pct held at 93.8%, no surfaces changed status.

### Top Saturation Targets (adapter-ready → joined requires single pattern each)

1. **tool_registry_dispatch** (`dharma_swarm/tool_registry.py`)
   - Blocking: add `try_begin_idempotent_side_effect` gate on tool side effects
2. **self_modification_loop** (`dharma_swarm/diff_applier.py`, `evolution.py`, `self_improve.py`)
   - Blocking: add `try_begin_idempotent_side_effect` gate on the apply path
3. **mcp_tool_access** (`dharma_swarm/mcp_server.py`, `dharma_swarm/dharma_context_mcp.py`)
   - Blocking: ExecutionIdentity import, RuntimeStateStore write, record_side_effect receipts (3 patterns)

**Commented** on most recent open spine PR: #622

---

## Mission 2: PR Lifecycle

### Totals
| Metric | Count |
|---|---|
| Open PRs before this run | 17 |
| Auto-closed (CONFLICTING >7d) | **0** |
| Open PRs after this run | **17** |

### Auto-Close Assessment (CONFLICTING PRs)
All 4 conflicting PRs are < 7 days old — no auto-close triggered.

| PR | Title | Created | Age | Action |
|---|---|---|---|---|
| #614 | report(governance): ops report 2026-06-15T12:00Z | 2026-06-15 | ~2d | No auto-close (also flagged as duplicate) |
| #613 | report(governance): ops report 2026-06-15 06:00Z | 2026-06-15 | ~2d | No auto-close (also flagged as duplicate) |
| #602 | test(complexity): replay metamorphic relations | 2026-06-14 | ~3d | No auto-close — monitor |
| #592 | Bug Corral: signal-graded provenance manifest v2 | 2026-06-13 | ~4d | No auto-close — monitor |

### Duplicate Auto-Grounding PRs Flagged
Two automated workflow series accumulated duplicate open PRs. Commented on older PRs suggesting close. Operator to close.

**Series 1: chore(governance): refresh spine adoption metric**
| PR | Status | Action |
|---|---|---|
| #622 (2026-06-17T00:00Z) | MERGEABLE | ✅ Keep — newest |
| #621 (2026-06-16T18:00Z) | MERGEABLE | ⚠️ Flagged — suggest close |
| #615 (2026-06-16) | MERGEABLE | ⚠️ Flagged — suggest close |
| #612 (2026-06-15) | MERGEABLE | ⚠️ Flagged — suggest close |

**Series 2: report(governance): PR lifecycle + spine adoption ops report**
| PR | Status | Action |
|---|---|---|
| #624 (2026-06-17T06:05Z) | MERGEABLE | ✅ Keep — newest |
| #618 (2026-06-16T12:12Z) | MERGEABLE | ⚠️ Flagged — suggest close |
| #614 (2026-06-15T12:04Z) | CONFLICTING | ⚠️ Flagged — suggest close + conflict |
| #613 (2026-06-15T06:04Z) | CONFLICTING | ⚠️ Flagged — suggest close + conflict |

### Green-and-Ready PRs (MERGEABLE, not duplicates)
| PR | Title |
|---|---|
| #625 | feat(orientation): graph-shaped queries + time-to-orientation measurement |
| #624 | report(governance): PR lifecycle + spine adoption ops report 2026-06-17T0600Z *(newest ops report)* |
| #623 | Add Devin A2A agent daemon for persistent fleet presence |
| #622 | chore(governance): refresh spine adoption metric [automated] 2026-06-17T00:00Z *(newest metric)* |
| #620 | palantir-pilot: deep public-doc corpus + retrieval tuning + domain submaps |
| #619 | ci(governance): wire anti-slop enforcement gates |
| #609 | refresh(docs+state): onboard-doc stack reconciliation 2026-06-15 |
| #607 | ci(tests): pipefail so pytest failures actually fail the gate |
| #599 | docs(state): refresh LIVE_OPS_DASHBOARD to 2026-06-14 |

### Recommended Operator Actions
1. Close duplicate spine metric PRs: #621, #615, #612 (superseded by #622)
2. Close duplicate ops report PRs: #618, #614, #613 (superseded by #624)
3. Rebase or close conflicting non-duplicate PRs #602, #592 before they age past 7 days
4. Advance `mcp_tool_access` to joined — highest-effort saturation target (3 missing patterns)
5. Add `try_begin_idempotent_side_effect` to `tool_registry_dispatch` and `self_modification_loop` to close gap to 95%

---

> Operator holds sole merge authority. Agent reports evidence only.
