# PR Janitor Session Report — 2026-06-02 14:35 UTC

**Agent:** devin (AGT-DEVIN)
**Session:** https://app.devin.ai/sessions/3e9721f21c274d05b6e70334e12a0ef2
**Authority:** external_worker_evidence_only (Stage 1)
**NATS:** Connected to `wss://157.245.193.15:8443` — announced on `dharma.a2a.fleet`

---

## Queue Snapshot

| Metric | Before | After |
|--------|--------|-------|
| Total open PRs | 37 | 37 |
| MERGEABLE | 35 | 37 |
| CONFLICTING | 2 (#388, #373) | 0 |
| CI fully green | 3 (#450, #439, #332) | 3+ (pending re-checks) |
| CI pending (rebased) | 0 | 4 (#388, #392, #383, #451) |
| DocOps-only failure | ~14 | ~14 (count drift from main) |
| Draft PRs | 3 (#412, #394, #325) | 3 |

## Actions Taken

### 1. Rebased CONFLICTING PRs → 0 CONFLICTING

| PR | Branch | Conflict Source | Resolution |
|---|---|---|---|
| #388 | `devin/2026-05-30-receipt-disambiguation` | Stale CONFLICTING status (merge actually clean) | Force-rebased to trigger GitHub re-evaluation |
| #373 | `devin/2026-05-29-wedge-resurvey` | DocOps counts vs base branch (#370) | Keep base version (`--ours`) for AUTO_INVENTORY.md + SOVEREIGN_MANIFEST.md |

### 2. NATS Coordination

- Connected to NATS bus at `wss://157.245.193.15:8443` as `devin`
- Announced session start on `dharma.a2a.fleet`
- JetStream unavailable (permissions: `$js.api.stream.names` denied) — using core NATS pub/sub only
- Drained inbound: 0 messages on `dharma.a2a.devin` / `dharma.a2a.devin.>`
- Reported to Mike on `dharma.a2a.merge_master_mike`
- Final status sent to `dharma.a2a.fleet`

### 3. CI Survey Findings

**Dominant failure pattern:** DocOps integrity gate (count drift). The `manifest-markdown-files` and `manifest-markdown-lines` assertions fail because main's counts have diverged since these branches were created. This resolves automatically after wave merges regenerate counts.

**Exception:** PR #323 fails CodeQL only (not DocOps). All other gates pass.

## Proposed Merge Sequence

### Wave 1 — Docs/Research (18 PRs, lowest risk)

All docs-only, zero code risk. Clear the queue first.

| PR | Title | Status |
|---|---|---|
| #442 | research: auto-grounding for PR #436 | MERGEABLE |
| #439 | research: auto-grounding for PR #435 | MERGEABLE, CI GREEN |
| #434 | research: auto-grounding for PR #433 | MERGEABLE, DocOps drift |
| #432 | research: auto-grounding for PR #431 | MERGEABLE, DocOps drift |
| #425 | research: spine-adoption master spec | MERGEABLE, DocOps drift |
| #424 | research: auto-grounding for PR #388 | MERGEABLE, DocOps drift |
| #423 | research: auto-grounding for PR #408 | MERGEABLE, DocOps drift |
| #422 | research: clean-main-audit v0.0.3.3 | MERGEABLE, DocOps drift |
| #421 | research: auto-grounding for PR #409 | MERGEABLE |
| #420 | research: auto-grounding for PR #418 | MERGEABLE, DocOps drift |
| #419 | research: auto-grounding for PR#409 | MERGEABLE |
| #414 | research: vocabulary inhabitation census | MERGEABLE |
| #410 | research: PhD-grade trio grounding #408/#409 | MERGEABLE |
| #405 | research: PhD-grade foundations grounding | MERGEABLE |
| #370 | docs: autonomous activation architect | MERGEABLE |

**⚠ Potential duplicates to review before merge:**
- **#415 & #417**: Both ground PR #406 — likely duplicates
- **#413, #419, #421**: All ground PR #409 — may overlap

### Wave 2 — Guardian Bug Fixes (2 PRs)

| PR | Title | Status | Notes |
|---|---|---|---|
| #383 | fix(guardian): recognize @dataclass __init__ | CI pending (just rebased) | Closes 29+ dupe issues |
| #392 | fix(guardian): bulletproof dedup | CI pending (just rebased) | Depends on #383 merging first |

**Sequence:** #383 → #392 (fix before dedup hardening)

### Wave 3 — Spine-Track Scaffolds (5 PRs, H-number order)

| PR | Title | Status | Notes |
|---|---|---|---|
| #388 | PR-H1: disambiguate ClosureEvidenceReceipt | CI pending (rebased) | 25 files, 4758+/19- |
| #384 | PR-H2: manifest_check enforces ACTIVE_SURFACE_MANIFEST | DocOps drift | 20 files |
| #389 | PR-H3: provider_registry contract | DocOps drift | 4 files, scaffold |
| #390 | PR-H4: storage_schema_registry contract | DocOps drift | 4 files, scaffold |
| #391 | PR-H5: openapi-typescript codegen pipeline | MERGEABLE | 6 files, scaffold |

**Sequence:** H1 → H2 → H3 → H4 → H5

### Wave 4 — Governance/Design (3 PRs)

| PR | Title | Status | Notes |
|---|---|---|---|
| #394 | feat(governance): PR quality gates + bot-pr-limit | DRAFT | Needs operator review |
| #402 | design: autonomous-loop + NATS endpoint | MERGEABLE | 5 files |
| #426 | seam(spine-adoption): consolidate into seams/ | DocOps drift | 6 files |

### Wave 5 — Feature Code (5 PRs)

| PR | Title | Status | Notes |
|---|---|---|---|
| #431 | feat(kaizen): bind reviews to runtime truth | DocOps drift | 9 files |
| #450 | test: expand coverage | CI GREEN (1 pending) | 5 files, Devin bot |
| #332 | feat(ops): staging promote + hermes wiring | CI GREEN | 14 files |
| #323 | fix(providers): dkeys env normalization | CodeQL fail | 8 files |
| #451 | outbound(devin): PR janitor session (prior) | CI pending | Previous janitor session |

### Wave 6 — Legacy/Stacked (3 PRs, need operator assessment)

| PR | Title | Status | Notes |
|---|---|---|---|
| #344 | [codex] Default runtime context Memory Kernel | DocOps drift | 11 files, module-budget pressure |
| #325 | [codex] Codex toolbelt onboarding | DRAFT | 8 files |
| #373 | docs: Wedge re-survey | Stacked on #370 | Merge #370 first |
| #412 | ADR-008: ontology api_name grammar | DRAFT | 3 files |

## Recommendations to Operator

1. **Merge Wave 1 first** — 18 docs PRs are zero-risk and will reduce queue by 50%. DocOps counts will auto-correct after first few merges.
2. **Close duplicates** — #415/#417 (both ground #406), #413/#419/#421 (all ground #409). Review which is most complete and close the rest.
3. **Wave 2 urgently** — #383 closes 29+ guardian dupe issues. #392 hardens dedup. Together they clean up a major recurring problem.
4. **Wave 3 in order** — H1→H5 are the active spine-track scaffolds. H1 (#388) is the largest and most important.
5. **#323 CodeQL** — investigate CodeQL failure; all other gates pass. May be a false positive or pre-existing.
6. **#344 module-budget** — Memory Kernel PR has module-budget pressure flagged in prior sessions. May need decomposition before merge.
7. **NATS JetStream** — `devin` user lacks `$js.api` publish permission. If JetStream durable subscriptions are needed, grant `$js.api.>` publish permission to the `devin` user in NATS config.

## Blockers

- **JetStream access**: Cannot use durable subscriptions for `dharma.a2a.devin`. Core NATS pub/sub works fine for coordination.
- **No inbound messages**: `dharma.a2a.devin` queue was empty; no filesystem inbound messages found.
- **DocOps count drift**: Systemic — every PR touching docs will fail DocOps gate until wave merges stabilize counts. Not fixable per-PR.
