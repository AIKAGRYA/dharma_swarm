# PR Janitor Session Report

- **Date:** 2026-06-02T16:01Z
- **Session:** devin-83a2dd8b2e464958827192986ab27ed6
- **Agent:** Devin (PR Janitor)
- **Authority:** `external_worker_evidence_only` — no merge authority

---

## Queue Summary

| Metric | Value |
|--------|-------|
| Total open PRs | 39 |
| MERGEABLE (before) | 38 |
| CONFLICTING (before) | 1 (#388) |
| MERGEABLE (after rebase) | 39 |
| CONFLICTING (after rebase) | 0 |
| CI all-green | 12 |
| CI failing (DocOps gate) | 24 |
| CI failing (other) | 2 (#391 dashboard, #323 CodeQL) |
| CI pending/minimal | 1 (#388 — just rebased) |
| Draft PRs | 3 (#412, #394, #325) |

---

## Actions Taken

1. **Rebased PR #388** (`devin/2026-05-30-receipt-disambiguation`) onto its base branch `devin/2026-05-30-manifest-check`. Clean rebase, no conflicts. Force-pushed.
2. **NATS heartbeat** — announced session on `dharma.a2a.fleet`. JetStream durable subscription not available (stream not configured); 0 inbound messages drained.
3. **Full CI audit** — checked all 39 PRs.

---

## CI Failure Analysis

### DocOps integrity gate (24 PRs)

The dominant failure mode is `canonical_guard`: new docs files contain authority terms but are not registered in `docs/governance/CANONICAL_DOC_STACK.md`. This is a **pre-existing main-branch issue** — the guard was tightened but the registration step was not applied to research/grounding docs.

**Affected PRs:** #384, #431, #442, #434, #432, #426, #425, #424, #423, #422, #421, #420, #417, #415, #414, #413, #410, #405, #402, #390, #389, #370, #344, #325

**Note:** PR #453 (`fix(docops): widen canonical_guard ignore`) was opened in a prior session to address this. If merged, it would unblock most of these PRs.

### Other failures

- **#391** (PR-H5 scaffold): `dashboard` CI check fails — likely a Next.js codegen or type issue from the OpenAPI pipeline addition.
- **#323** (fix providers): `CodeQL` fails — likely a pre-existing static analysis finding.

---

## PR Review Notes

### Wave 1 — Docs-only (lowest risk, merge first)

#### PR #373: docs: Wedge re-survey — 30-day time-to-first-dollar
- **Author:** AmitabhainArunachala
- **Category:** docs-only
- **Files:** 4 (docs reports)
- **Risk:** LOW
- **CI:** only detect-br-collision ran (1/1 pass) — limited CI coverage
- **Dependencies:** none
- **Recommendation:** MERGE (wave 1) — needs full CI re-trigger first

#### PR #414: research(layer-2): vocabulary inhabitation census
- **Author:** AmitabhainArunachala
- **Category:** docs-only (research)
- **Files:** 22 (docs)
- **Risk:** LOW
- **CI:** DocOps FAIL (canonical_guard)
- **Dependencies:** none
- **Recommendation:** MERGE (wave 1) after #453 lands

### Wave 1 — Research grounding companions (docs-only, merge with parents)

| PR | Title | Parent PR | CI | Recommendation |
|----|-------|-----------|-----|----------------|
| #442 | auto-grounding PR #436 | #436 (not open) | DocOps FAIL | MERGE wave 1 after #453 |
| #439 | auto-grounding PR #435 | #435 (not open) | GREEN | MERGE wave 1 |
| #434 | auto-grounding PR #433 | #433 (not open) | DocOps FAIL | MERGE wave 1 after #453 |
| #432 | auto-grounding PR #431 | #431 (open) | DocOps FAIL | MERGE wave 1 after #431 |
| #424 | auto-grounding PR #388 | #388 (open) | DocOps FAIL | MERGE wave 1 after #388 |
| #423 | auto-grounding PR #408 | #408 (not open) | DocOps FAIL | MERGE wave 1 after #453 |
| #422 | clean-main-audit v0.0.3.3 | N/A | DocOps FAIL | MERGE wave 1 after #453 |
| #421 | auto-grounding PR #409 | #409 (not open) | DocOps FAIL | MERGE wave 1 after #453 |
| #420 | auto-grounding PR #418 | #418 (not open) | DocOps FAIL | MERGE wave 1 after #453 |
| #419 | auto-grounding PR #409 | #409 (not open) | GREEN | MERGE wave 1 |
| #417 | auto-grounding PR #406 | #406 (not open) | DocOps FAIL | MERGE wave 1 after #453 |
| #415 | auto-grounding PR #406 | #406 (not open) | DocOps FAIL | MERGE wave 1 after #453 |
| #413 | auto-grounding PR #409 | #409 (not open) | DocOps FAIL | MERGE wave 1 after #453 |
| #410 | PhD-grade grounding #408/#409 | #408/#409 (not open) | DocOps FAIL | MERGE wave 1 after #453 |
| #405 | PhD-grade foundations grounding | N/A | DocOps FAIL | MERGE wave 1 after #453 |

### Wave 1 — Seam/research docs

| PR | Title | CI | Recommendation |
|----|-------|----|----------------|
| #426 | seam(spine-adoption) deliverables | DocOps FAIL | MERGE wave 1 after #453 |
| #425 | research(spine-adoption) master spec | DocOps FAIL | MERGE wave 1 after #453 |

### Wave 2 — Bug fixes (operational value)

#### PR #383: fix(guardian): recognize @dataclass __init__
- **Author:** AmitabhainArunachala
- **Category:** code-fix
- **Files:** 4 (dharma_swarm/guardian, tests)
- **Risk:** MEDIUM
- **CI:** GREEN (22/22)
- **Dependencies:** none — blocks #392 (dedup fix)
- **Recommendation:** MERGE (wave 2)

#### PR #392: fix(guardian): bulletproof dedup
- **Author:** AmitabhainArunachala
- **Category:** code-fix
- **Files:** 5 (dharma_swarm/guardian)
- **Risk:** MEDIUM
- **CI:** GREEN (22/22)
- **Dependencies:** depends on #383
- **Recommendation:** MERGE (wave 2, after #383)

#### PR #453: fix(docops): widen canonical_guard ignore
- **Author:** Devin (prior session)
- **Category:** governance-fix
- **Files:** 5
- **Risk:** MEDIUM (unblocks 24 PRs)
- **CI:** GREEN (22/22)
- **Dependencies:** none
- **Recommendation:** MERGE (wave 2, high priority — unblocks 24 DocOps-failing PRs)

### Wave 3 — Spine-track scaffolds (H-number order)

| PR | Title | CI | Risk | Recommendation |
|----|-------|----|------|----------------|
| #384 | PR-H2: manifest_check | DocOps FAIL | MEDIUM | MERGE wave 3 after #453 |
| #388 | PR-H1: disambiguate ClosureEvidenceReceipt | pending (just rebased) | MEDIUM | MERGE wave 3 (stacked on #384) |
| #389 | PR-H3: provider_registry contract | DocOps FAIL | MEDIUM | MERGE wave 3 after #453 |
| #390 | PR-H4: storage_schema_registry | DocOps FAIL | MEDIUM | MERGE wave 3 after #389 |
| #391 | PR-H5: openapi-typescript codegen | dashboard FAIL | MEDIUM | HOLD — dashboard CI needs investigation |

### Wave 4 — Governance / design

#### PR #394: feat(governance): PR quality gates (DRAFT)
- **Author:** AmitabhainArunachala
- **Category:** governance
- **Files:** 7
- **Risk:** MEDIUM
- **CI:** GREEN (22/22)
- **Dependencies:** none
- **Recommendation:** HOLD (draft) — operator review needed

#### PR #402: design(perplexity-computer): autonomous-loop addendum
- **Author:** AmitabhainArunachala
- **Category:** design/docs
- **Files:** 5
- **Risk:** LOW
- **CI:** DocOps FAIL
- **Dependencies:** none
- **Recommendation:** MERGE (wave 4) after #453

#### PR #412: ADR-008: ontology api_name grammar (DRAFT)
- **Author:** AmitabhainArunachala
- **Category:** governance (ADR)
- **Files:** 2
- **Risk:** LOW
- **CI:** GREEN (22/22)
- **Dependencies:** none
- **Recommendation:** HOLD (draft) — operator review needed

### Wave 5 — Feature code

#### PR #431: feat(kaizen): bind reviews to runtime truth refs
- **Author:** AmitabhainArunachala
- **Category:** code (feature)
- **Files:** 9
- **Risk:** MEDIUM
- **CI:** DocOps FAIL
- **Dependencies:** companion #432 (research grounding)
- **Recommendation:** MERGE (wave 5) after #453

#### PR #450: test: expand coverage — contracts/runtime, revenue/spine
- **Author:** Devin (prior session)
- **Category:** code (tests)
- **Files:** 11
- **Risk:** LOW (additive tests only)
- **CI:** GREEN (22/22)
- **Dependencies:** none
- **Recommendation:** MERGE (wave 5)

### Wave 6 — Legacy / large PRs (operator assessment needed)

#### PR #323: fix(providers): dkeys env alias normalization
- **Author:** AmitabhainArunachala
- **Category:** code-fix
- **Files:** 8
- **Risk:** HIGH (touches providers hot path)
- **CI:** CodeQL FAIL
- **Dependencies:** none
- **Recommendation:** HOLD — CodeQL failure needs investigation

#### PR #332: feat(ops): staging promote loop + Hermes heartbeat
- **Author:** AmitabhainArunachala
- **Category:** code (feature)
- **Files:** 14
- **Risk:** HIGH (large change, ops wiring)
- **CI:** GREEN (22/22)
- **Dependencies:** none
- **Recommendation:** MERGE (wave 6) — operator review recommended

#### PR #344: [codex] Default runtime context through Memory Kernel
- **Author:** AmitabhainArunachala
- **Category:** code (feature)
- **Files:** 11
- **Risk:** HIGH (modifies memory kernel)
- **CI:** DocOps FAIL
- **Dependencies:** none
- **Recommendation:** HOLD (wave 6) — needs operator review + DocOps fix

#### PR #325: [codex] publish Codex toolbelt onboarding (DRAFT)
- **Author:** AmitabhainArunachala
- **Category:** code (scaffold)
- **Files:** 8
- **Risk:** MEDIUM
- **CI:** DocOps FAIL
- **Dependencies:** none
- **Recommendation:** HOLD (draft)

#### PR #370: docs(reports): autonomous activation architect
- **Author:** AmitabhainArunachala
- **Category:** docs-only
- **Files:** 14
- **Risk:** LOW
- **CI:** DocOps FAIL
- **Dependencies:** none
- **Recommendation:** MERGE (wave 1) after #453

---

## Superseded PR Candidates (recommend closing)

| PR | Reason |
|----|--------|
| #454 | Prior janitor session report — superseded by this session |
| #452 | Prior janitor session report — superseded by this session |
| #451 | Prior janitor session report — superseded by this session |

**Operator decision needed:** These prior janitor PRs (#451, #452, #454) contain only outbound reports from earlier today. This session's report supersedes them. Recommend closing.

---

## Merge Sequence Recommendation

### Priority: Merge #453 first (unblocks 24 PRs)

1. **Wave 2a:** #453 (DocOps fix) → unblocks 24 PRs
2. **Wave 1:** #439, #419, #373, then remaining research/docs PRs (after #453)
3. **Wave 2b:** #383 → #392 (guardian fix chain)
4. **Wave 3:** #384 → #388 → #389 → #390 (spine H-series, in order)
5. **Wave 5:** #450 (test coverage), #431 (kaizen)
6. **Wave 6:** #332, #344, #323 (operator review needed)

---

## Blockers & Operator Decisions Needed

1. **#453 merge** — highest priority, unblocks 24 DocOps-failing PRs
2. **#391 dashboard CI** — needs investigation (OpenAPI codegen pipeline)
3. **#323 CodeQL** — needs investigation
4. **Draft PRs (#412, #394, #325)** — need operator intent confirmation
5. **Prior janitor PRs (#451, #452, #454)** — recommend closing as superseded
6. **NATS JetStream** — `dharma.a2a.devin` stream not configured on server; plain pub/sub works but durable delivery is unavailable

---

## NATS Coordination

- **Announced:** session start on `dharma.a2a.fleet`
- **Drained:** 0 inbound messages from `dharma.a2a.devin`
- **JetStream:** permissions violation for stream operations — devin user lacks JetStream admin. Plain pub/sub works.
- **Report sent to:** `dharma.a2a.merge_master_mike` and `dharma.a2a.fleet` (final status)
