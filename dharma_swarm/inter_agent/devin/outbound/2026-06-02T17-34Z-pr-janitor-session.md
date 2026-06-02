# PR Janitor Session Report

- **Date**: 2026-06-02T17:34Z
- **Session**: devin-janitor-20260602T173416Z
- **Agent**: devin (PR Janitor)
- **Authority**: external_worker_evidence_only (no merge)

---

## Queue Summary

| Metric | Value |
|---|---|
| Total open PRs | 43 |
| MERGEABLE (before) | 42 |
| CONFLICTING (before) | 1 (#388) |
| MERGEABLE (after rebase) | 43 |
| CONFLICTING (after rebase) | 0 |
| CI GREEN (all checks pass) | 18 |
| CI FAILING (DocOps) | 21 |
| CI FAILING (dashboard) | 1 (#391) |
| CI FAILING (CodeQL, non-required) | 1 (#323) |
| CI partial (only 1 check ran) | 1 (#373) |
| Draft PRs | 3 (#394, #412, #325) |

## PRs Rebased This Session

| PR | Branch | Conflict | Resolution |
|---|---|---|---|
| #388 | devin/2026-05-30-receipt-disambiguation | DocOps counts (AUTO_INVENTORY.md, SOVEREIGN_MANIFEST.md) | Kept main's version per playbook |

## PR Review Notes

### Wave 1 — Docs-only (LOW risk, clear the queue)

#### PR #373: docs: Wedge re-survey — 30-day time-to-first-dollar
- **Author**: AmitabhainArunachala
- **Category**: docs-only
- **Files**: 3
- **Risk**: LOW
- **CI**: PARTIAL (only detect-br-collision ran; needs full CI trigger)
- **Dependencies**: supersedes #372
- **Recommendation**: HOLD (needs CI re-trigger)

#### PR #370: docs(reports): autonomous activation architect — 3 deliverables
- **Author**: AmitabhainArunachala
- **Category**: docs-only
- **Files**: 3
- **Risk**: LOW
- **CI**: FAILING (DocOps doc-registry gate)
- **Dependencies**: none
- **Recommendation**: HOLD (DocOps fix needed)

### Wave 2 — Bug Fixes (MEDIUM risk, operational value)

#### PR #383: fix(guardian): recognize @dataclass-synthesized __init__
- **Author**: devin-ai-integration
- **Category**: code-fix
- **Files**: 3
- **Risk**: MEDIUM
- **CI**: GREEN (22/22)
- **Dependencies**: none; #392 depends on this
- **Recommendation**: MERGE (Wave 2) — pr-packet generated, needs agent reviews

#### PR #392: fix(guardian): bulletproof dedup
- **Author**: devin-ai-integration
- **Category**: code-fix
- **Files**: 3
- **Risk**: MEDIUM
- **CI**: GREEN (22/22)
- **Dependencies**: depends on #383
- **Recommendation**: MERGE (Wave 2, after #383) — pr-packet generated

#### PR #323: fix(providers): dkeys <-> dharma_swarm env alias normalization
- **Author**: devin-ai-integration
- **Category**: code-fix
- **Files**: 3
- **Risk**: MEDIUM
- **CI**: FAILING (CodeQL non-required; all required checks pass)
- **Dependencies**: none
- **Recommendation**: MERGE (Wave 2) — CodeQL failure is non-required

### Wave 3 — Spine Track Scaffolds (in H-number order)

#### PR #384: PR-H2: manifest_check enforces ACTIVE_SURFACE_MANIFEST
- **Author**: devin-ai-integration
- **Category**: scaffold/governance
- **Files**: 11
- **Risk**: HIGH
- **CI**: FAILING (DocOps doc-registry gate)
- **Dependencies**: #388 stacked on this
- **Recommendation**: HOLD (DocOps fix needed before merge)

#### PR #388: PR-H1: disambiguate ClosureEvidenceReceipt from spine EvidenceReceipt
- **Author**: AmitabhainArunachala
- **Category**: code-fix
- **Files**: 5
- **Risk**: HIGH (touches receipt identity boundary)
- **CI**: GREEN (1/1 — rebased this session, full CI pending)
- **Dependencies**: stacked on #384; operator hold per comment
- **Recommendation**: HOLD (operator directive: restack onto main, not merge as-is)

#### PR #389: PR-H3: provider_registry contract
- **Author**: devin-ai-integration
- **Category**: scaffold
- **Files**: 7
- **Risk**: MEDIUM
- **CI**: FAILING (DocOps doc-registry gate)
- **Dependencies**: should follow H1, H2
- **Recommendation**: HOLD (DocOps fix needed)

#### PR #390: PR-H4: storage_schema_registry contract
- **Author**: devin-ai-integration
- **Category**: scaffold
- **Files**: 5
- **Risk**: MEDIUM
- **CI**: FAILING (DocOps doc-registry gate)
- **Dependencies**: should follow H3
- **Recommendation**: HOLD (DocOps fix needed)

#### PR #391: PR-H5: openapi-typescript codegen pipeline
- **Author**: devin-ai-integration
- **Category**: scaffold
- **Files**: 7
- **Risk**: MEDIUM
- **CI**: FAILING (dashboard — npm lockfile mismatch)
- **Dependencies**: should follow H4
- **Recommendation**: HOLD (dashboard CI fix needed)

### Wave 4 — Governance / Design

#### PR #394: feat(governance): PR quality gates [DRAFT]
- **Author**: devin-ai-integration
- **Category**: governance
- **Files**: 9
- **Risk**: HIGH (modifies PR gates)
- **CI**: GREEN (22/22)
- **Dependencies**: none
- **Recommendation**: HOLD (DRAFT — needs operator review)

#### PR #412: ADR-008: ontology api_name grammar [DRAFT]
- **Author**: AmitabhainArunachala
- **Category**: governance
- **Files**: 4
- **Risk**: LOW
- **CI**: GREEN (22/22)
- **Dependencies**: none
- **Recommendation**: HOLD (DRAFT — needs operator review)

#### PR #414: research(layer-2): vocabulary inhabitation census
- **Author**: AmitabhainArunachala
- **Category**: docs-only/research
- **Files**: 3
- **Risk**: LOW
- **CI**: FAILING (DocOps)
- **Dependencies**: none
- **Recommendation**: HOLD (DocOps fix needed)

### Wave 5 — Feature Code

#### PR #450: test: expand coverage — contracts/runtime, revenue/spine
- **Author**: devin-ai-integration
- **Category**: code (tests)
- **Files**: 11
- **Risk**: MEDIUM
- **CI**: GREEN (22/22)
- **Dependencies**: none
- **Recommendation**: MERGE (Wave 5) — pr-packet generated

#### PR #431: feat(kaizen): bind reviews to runtime truth refs
- **Author**: AmitabhainArunachala
- **Category**: code
- **Files**: 11
- **Risk**: HIGH
- **CI**: GREEN (22/22)
- **Dependencies**: #432 is research companion
- **Recommendation**: MERGE (Wave 5) — pr-packet generated, needs agent reviews

#### PR #344: [codex] Default runtime context through Memory Kernel
- **Author**: devin-ai-integration
- **Category**: code
- **Files**: 6
- **Risk**: HIGH
- **CI**: GREEN (22/22)
- **Dependencies**: none
- **Recommendation**: MERGE (Wave 5) — pr-packet generated, needs agent reviews

#### PR #332: feat(ops): staging promote loop + Hermes heartbeat
- **Author**: devin-ai-integration
- **Category**: code
- **Files**: 9
- **Risk**: HIGH
- **CI**: GREEN (22/22)
- **Dependencies**: none
- **Recommendation**: MERGE (Wave 5) — pr-packet generated, needs agent reviews

### Wave 6 — Research / Companion PRs

The following research(palantir-ontology) PRs are auto-grounding companions:
- #442 (companion to #436) — DocOps FAIL
- #439 (companion to #435) — GREEN
- #434 (companion to #433) — DocOps FAIL
- #432 (companion to #431) — DocOps FAIL
- #424 (companion to #388) — DocOps FAIL
- #423 (companion to #408) — DocOps FAIL
- #422 (clean-main-audit) — DocOps FAIL
- #421 (companion to #409) — DocOps FAIL
- #420 (companion to #418) — DocOps FAIL
- #419 (companion to #409) — GREEN
- #417 (companion to #406) — DocOps FAIL
- #415 (companion to #406) — DocOps FAIL
- #413 (companion to #409) — DocOps FAIL
- #410 (PhD-grade trio) — DocOps FAIL
- #405 (PhD-grade foundations) — DocOps FAIL

#### PR #426: seam(spine-adoption): consolidate deliverables
- **Author**: AmitabhainArunachala
- **Category**: docs/scaffold
- **Files**: 7
- **Risk**: MEDIUM
- **CI**: FAILING (DocOps)
- **Recommendation**: HOLD (DocOps fix)

#### PR #425: research(spine-adoption): master spec
- **Author**: AmitabhainArunachala
- **Category**: docs/research
- **Files**: 4
- **Risk**: LOW
- **CI**: FAILING (DocOps)
- **Recommendation**: HOLD (DocOps fix)

#### PR #402: design(perplexity-computer): autonomous-loop addendum
- **Author**: AmitabhainArunachala
- **Category**: docs/design
- **Files**: 4
- **Risk**: LOW
- **CI**: FAILING (DocOps)
- **Recommendation**: HOLD (DocOps fix)

### Wave 7 — Previous Janitor Session PRs (superseded)

PRs #451–#457 are outbound reports from previous janitor sessions. Only the latest should be kept:
- **#457**: Latest janitor session report — GREEN
- **#451–#456**: Superseded by #457
- **Recommendation**: CLOSE #451–#456 (superseded by #457)

#### PR #325: [codex] publish Codex toolbelt onboarding [DRAFT]
- **Author**: devin-ai-integration
- **Category**: docs
- **Files**: 3
- **Risk**: LOW
- **CI**: FAILING (DocOps)
- **Recommendation**: HOLD (DRAFT + DocOps fix needed)

---

## Merge Sequence Recommendation

### Immediate (operator approval needed)
1. **#383** → fix(guardian) @dataclass __init__ — GREEN, MEDIUM risk
2. **#392** → fix(guardian) dedup — GREEN, MEDIUM risk (after #383)
3. **#323** → fix(providers) env alias — GREEN (CodeQL non-required)

### After agent reviews
4. **#450** → test: expand coverage — GREEN, MEDIUM risk
5. **#431** → feat(kaizen): bind reviews — GREEN, HIGH risk
6. **#344** → [codex] Memory Kernel — GREEN, HIGH risk
7. **#332** → feat(ops): staging promote — GREEN, HIGH risk

### Blocked on DocOps
21 PRs blocked on DocOps doc-registry gate failures (files contain gov-scoped terms but aren't registered in the doc stack). This is the #1 blocker for queue health.

### Blocked on operator decisions
- **#388**: Operator hold — needs restack per comment
- **#384**: DocOps fail (base for #388 stack)
- **#394, #412, #325**: DRAFT PRs

### Recommended closures
- **#451–#456**: Superseded janitor session reports (keep #457)
- **#415, #419**: Duplicate research companions for same parent PR #406/#409

---

## Blockers & Operator Decisions Needed

1. **DocOps doc-registry gate** is blocking 21 PRs. Files with gov-scoped terms need registration in the doc stack, or the guard needs widening. This is the top priority for queue health.
2. **PR #388** has operator hold (restack directive from AmitabhainArunachala).
3. **PR #391** (H5) has dashboard CI failure (npm lockfile mismatch).
4. **PR #373** has incomplete CI (only 1 check ran).

## Session Actions

- [x] NATS presence announced on dharma.a2a.fleet
- [x] Inbound drained: 0 messages (no JetStream permissions, no wildcard messages)
- [x] PR #388 rebased (DocOps conflict resolved, pushed)
- [x] pr-packet generated for #383, #392, #344, #332, #450, #431
- [x] Full CI survey completed for all 43 PRs
- [x] Merge sequence produced (7 waves)
- [x] Report filed to dharma.a2a.merge_master_mike
- [x] Final status sent to dharma.a2a.fleet
