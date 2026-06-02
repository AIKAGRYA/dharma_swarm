# PR Janitor Session Report

- **Date**: 2026-06-02T15:38Z
- **Session**: devin-6cc11707fd8543728cba0482ab0c5475
- **Role**: PR Janitor (no merge authority)

## Queue Summary

| Metric | Before | After |
|--------|--------|-------|
| Total open PRs | 39 | 39 |
| MERGEABLE | 38 | 39 |
| CONFLICTING | 1 | 0 |
| GITHUB_GREEN | 12 | 12 |
| DocOps gate failing | 24 | 24 |
| Drafts | 3 | 3 |

## Actions Taken

1. **Rebased PR #388** (PR-H1: disambiguate ClosureEvidenceReceipt)
   - Was CONFLICTING due to stale DocOps counts
   - Fixed AUTO_INVENTORY.md + SOVEREIGN_MANIFEST.md counts
   - Force-pushed; now MERGEABLE

2. **Generated pr-packets** for 9 GITHUB_GREEN PRs:
   - #332 (risk=HIGH), #373 (LOW), #383 (MEDIUM), #392 (MEDIUM)
   - #439 (LOW), #450 (MEDIUM), #451 (LOW), #452 (LOW), #453 (MEDIUM)

3. **Ran merge gates** — all BLOCKED pending dual-agent review receipts

4. **NATS coordination**:
   - Connected and announced presence on `dharma.a2a.fleet`
   - Drained `dharma.a2a.devin` — 0 pending messages
   - Published full report to `dharma.a2a.merge_master_mike`

## CI Failure Analysis

- **24 PRs**: DocOps integrity gate (stale counts) — will resolve when PR #453 merges
- **1 PR** (#323): CodeQL failure
- **1 PR** (#391): Dashboard build failure

## Recommended Merge Sequence

### Wave 1 — Priority Unblock
- **#453** fix(docops): widen canonical_guard ignore (unblocks 24 CI-failing PRs)

### Wave 2 — Bug Fixes
- **#383** fix(guardian): recognize @dataclass __init__ (closes 29 dupe issues)
- **#392** fix(guardian): bulletproof dedup

### Wave 3 — Spine Track (H-number order)
- **#388** PR-H1: disambiguate ClosureEvidenceReceipt
- **#384** PR-H2: manifest_check enforces ACTIVE_SURFACE_MANIFEST
- **#389** PR-H3: provider_registry contract
- **#390** PR-H4: storage_schema_registry contract
- **#391** PR-H5: openapi-typescript codegen (dashboard CI failing)

### Wave 4 — Docs/Research (low risk, clears queue)
- #373, #370, #405, #410, #413–#434, #439, #442 (research/grounding PRs)
- #414, #419–#426 (research companions)

### Wave 5 — Features
- **#332** feat(ops): staging promote loop (HIGH risk, needs --human-approved)
- **#431** feat(kaizen): bind reviews to runtime truth refs
- **#450** test: expand coverage

### Wave 6 — Legacy/Devin Janitor
- #451, #452 (previous janitor session reports — can be closed if redundant)
- #325, #344 (older codex PRs)

## Operator Decisions Needed

1. **Merge #453 first** — it unblocks 24 DocOps-failing PRs
2. **#332** is HIGH risk and requires `--human-approved` flag
3. **All green PRs** need codex + claude dual-agent review before gate passes
4. **#451, #452** — previous janitor reports; consider closing as superseded
5. **Inbound from 2026-05-25** (codex request to verify 11-step chain) — stale, may already be addressed

## NATS Bus Status

- JetStream: permissions restricted (no `$js.api.stream.names` access for `devin` user)
- Plain pub/sub: working (fleet + merge_master_mike subjects)
- Inbound drain: 0 messages pending
