# Ops Run Report — 2026-06-05T12:00Z

**Agent:** Dharma Swarm ops agent (Oz)
**Run ID:** 019e97a7-9424-773e-9747-64ddae6ff794
**Audit SHA:** 10a40cd0e7974b2e764c8d5cc07ff559e1d2e5ed

---

## Mission 1: Spine Adoption Tracking

### Result
| Metric | Value |
|--------|-------|
| adoption_pct | **75.0%** |
| target | 95.0% |
| gap | −20 pp (need ≥ 3 more surfaces promoted) |
| joined | 8 / 16 |
| adapter-ready | 4 / 16 |
| legacy | 2 / 16 |
| quarantine | 1 / 16 |
| missing | 1 / 16 |

### Status Movements
None — all 16 surfaces identical to previous committed metric (75.0% → 75.0%).

### Actions Taken
- Spine adoption metric re-computed; `reports/governance/spine_adoption_metric.json` not recommitted (adoption_pct unchanged at 75.0%).
- Adoption status comment posted on PR **#485** (most recent open spine PR).

### Top Saturation Targets (fastest path to 95%)

**Adapter-ready → joined (already counted in adoption_pct, upgrade quality only):**
1. `tool_registry_dispatch` (adapter-ready) — 1 missing pattern: idempotency gate (`try_begin_idempotent_side_effect`) in `dharma_swarm/tool_registry.py`
2. `ontology_action_tollbooth` (adapter-ready) — 1 missing pattern: `RuntimeStateStore` write in `dharma_swarm/ontology.py`
3. `self_modification_loop` (adapter-ready) — 1 missing pattern: idempotency gate on apply path in `dharma_swarm/diff_applier.py`
4. `mcp_tool_access` (adapter-ready) — 3 missing patterns: identity import, `RuntimeStateStore` write, `record_side_effect` receipts in `dharma_swarm/mcp_server.py` / `dharma_swarm/dharma_context_mcp.py`

**Legacy/missing/quarantine → adopted (moves adoption_pct needle):**
5. `opportunity_refill_research_backend` (quarantine) — 1 missing joined pattern: `ExecutionIdentity` import in `dharma_swarm/opportunity_refill.py` → promotes to adapter-ready (+6.25 pp)
6. `workflow_checkpoint_replay` (legacy) — 3 missing patterns: identity import, `RuntimeStateStore` write, ledger-reconstructable receipt in workflow/checkpoint/replay files (+6.25 pp)
7. `nats_jetstream_transport` (missing) — no implementation files yet; requires NATS/JetStream client + identity + idempotency gate + ack/nack contract (+6.25 pp)
8. `legacy_no_identity_escape_hatch` (legacy) — intentional bypass, has test coverage; removal/promotion requires explicit governance decision

**Path to 95%:** With 16 surfaces, 95% requires ≥ 15.2 (≈ 16) surfaces adopted. Realistically: promote items 5, 6, 7 above → 15/16 = 93.75%. All 4 non-adopted surfaces must move to reach ≥ 95%.

---

## Mission 2: PR Lifecycle

### Summary
| Metric | Value |
|--------|-------|
| Total open PRs (before scan) | 30 |
| CONFLICTING | 2 (#489, #476) |
| Auto-close eligible (CONFLICTING + >7 days) | 0 |
| Auto-closed | 0 |
| Total open PRs (after) | 30 |
| MERGEABLE | 28 / 30 |
| Duplicate auto-grounding pairs flagged | 1 |

### CONFLICTING PRs (not eligible for auto-close — under 7 days old)
| PR | Title | Created | Age |
|----|-------|---------|-----|
| #489 | [codex] Add CI truth gate for Mike | 2026-06-05T08:38Z | ~3.4 h |
| #476 | Document PR portfolio cleanup wave | 2026-06-04T12:16Z | ~24 h |

Neither PR meets the CONFLICTING + >7 days auto-close threshold. Both branches preserved; operator may rebase or close at discretion.

### Auto-Closures
None.

### Duplicate Auto-Grounding Flags
**1 duplicate pair found** — both PRs target auto-grounding for **PR #409**:

| PR | Title | Created | Action |
|----|-------|---------|--------|
| **#421** (newer — keep) | research(palantir-ontology): auto-grounding for PR #409 | 2026-06-01T09:05Z | Retain |
| **#419** (older — flagged) | research(palantir-ontology): auto-grounding for PR#409 | 2026-06-01T08:07Z | Suggest close |

Duplicate comment posted on **#419**. Operator holds sole close authority.

All other auto-grounding PRs target distinct base PRs:

| Auto-grounding PR | Target PR |
|-------------------|-----------|
| #442 | #436 |
| #439 | #435 |
| #434 | #433 |
| #432 | #431 |
| #424 | #388 |
| #423 | #408 |
| #421 | #409 |
| #420 | #418 |
| #417 | #406 |

### Green-and-Ready PRs (MERGEABLE, no conflicts)
28 of 30 open PRs are `MERGEABLE`. Notable PRs awaiting operator review:

- **#490** `ci(docops): self-healing count auto-refresh feeder [impact-checked]` — 103 additions, 1 file (newest)
- **#474** `feat(go-ingest): wire idea spark ingest spine` — 3,639 additions / 132 deletions, 24 files (largest feature)
- **#465** `feat(ops): add read-only live ops cockpit` — 2,708 additions, 23 files
- **#461** `Seed: The Self-Reference Attractor — keystone synthesis (SRA_001)` — 303 additions, 6 files
- **#450** `test: expand coverage — contracts/runtime, revenue/spine, cascade_domains/skill` — 1,447 additions / 469 deletions, 9 files
- **#431** `feat(kaizen): bind reviews to runtime truth refs` — 358 additions / 8 deletions, 9 files

### Stale Governance Artifact Backlog (open, MERGEABLE, automated)
Multiple automated metric/report PRs remain open and unmerged:

| PRs | Type | Note |
|-----|------|------|
| #475, #467, #466, #463, #462 | spine adoption metric refresh | Superseded by later runs; #475 is most recent |
| #485, #483, #464, #460 | ops run reports | Prior ops cycles; this report supersedes |

### Recommended Actions
1. **Rebase or close** CONFLICTING PR **#489** (`[codex] Add CI truth gate for Mike`) — conflicts block CI; straightforward rebase candidate given its focused scope (1 file, 103 additions).
2. **Review** CONFLICTING PR **#476** (`Document PR portfolio cleanup wave`) — 6 files changed; may need operator-guided conflict resolution.
3. **Consider closing** duplicate auto-grounding PR **#419** in favour of **#421**.
4. **Merge** **#474** `feat(go-ingest): wire idea spark ingest spine` — largest open feature, directly advances spine saturation.
5. **Batch-close** stale spine-metric refresh PRs **#462, #463, #466, #467** once **#475** merges — all target the same governance file and are superseded.
6. **Prioritise** `opportunity_refill_research_backend` spine adoption: adding a single `ExecutionIdentity` import unblocks +6.25 pp adoption and promotes it from quarantine.

---

_This report is type: `report`. It makes no authority claims. Evidence-only; operator holds sole merge authority._
