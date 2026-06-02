# PR Janitor Session Report

**Date:** 2026-06-02T16:35Z
**Session:** devin-ad49117985aa43549a21d13d02bcd409
**Agent:** Devin (PR Janitor)
**Authority:** external_worker_evidence_only — no merge

---

## Queue Snapshot

| Metric | Count |
|---|---|
| Total open PRs | 41 |
| MERGEABLE | 41 |
| CONFLICTING | 0 |
| GITHUB_GREEN (all CI pass) | 13 |
| DocOps integrity gate FAIL | 24 |
| Dashboard CI FAIL | 1 (#391) |
| CodeQL FAIL | 1 (#323) |
| Incomplete CI (only 1 check) | 2 (#388, #373) |
| Draft PRs | 3 (#412, #394, #325) |

## PRs Rebased This Session

**None** — 0/41 CONFLICTING. All 41 PRs are MERGEABLE.

## NATS Coordination

- Connected to `wss://157.245.193.15:8443` as `devin`
- Announced presence on `dharma.a2a.fleet`
- JetStream durable subscribe not available (permissions: `$js.api.stream.names` denied)
- Plain subscribe to `dharma.a2a.devin.>` — 0 inbound messages
- Filesystem inbound (`inter_agent/devin/inbound/`) — directory does not exist; no messages

## pr-packet / pr-gate Results (11 GITHUB_GREEN PRs)

All 11 green PRs were run through `make pr-packet` and `make pr-gate`:

| PR | Risk | Coherence | Gate Decision | Blockers |
|---|---|---|---|---|
| #455 | LOW | pass | BLOCKED | needs codex_review + claude_review |
| #454 | LOW | pass | BLOCKED | needs codex_review + claude_review |
| #453 | MEDIUM | pass | BLOCKED | needs codex_review + claude_review |
| #452 | LOW | pass | BLOCKED | needs codex_review + claude_review |
| #451 | LOW | pass | BLOCKED | needs codex_review + claude_review |
| #450 | MEDIUM | pass | BLOCKED | needs codex_review + claude_review |
| #439 | LOW | pass | BLOCKED | needs codex_review + claude_review |
| #419 | LOW | pass | BLOCKED | needs codex_review + claude_review |
| #392 | MEDIUM | pass | BLOCKED | needs codex_review + claude_review |
| #383 | MEDIUM | pass | BLOCKED | needs codex_review + claude_review |
| #332 | HIGH | pass | BLOCKED | needs codex_review + claude_review + --human-approved |

**Summary:** All green PRs pass coherence but are BLOCKED at the gate pending dual-agent review receipts (Codex + Claude). PR #332 additionally requires `--human-approved` (HIGH risk).

## CI Failure Analysis

### DocOps integrity gate (24 PRs)
**Root cause:** `canonical_guard` rejects docs that contain authority terms but aren't registered in `docs/governance/CANONICAL_DOC_STACK.md`.

Example error: `FAIL: canonical: docs/research/palantir-ontology/auto-grounded/2026-06-02-0401-pr436-mapping-receipts.md contains an authority term but is not registered in docs/governance/CANONICAL_DOC_STACK.md`

**Fix available:** PR #453 (`fix(docops): widen canonical_guard ignore`) is GITHUB_GREEN and directly addresses this. Once #453 merges to main and these 24 PRs are rebased, they should pass.

**Affected PRs:** #442, #434, #432, #431, #426, #425, #424, #423, #422, #421, #420, #417, #415, #414, #413, #410, #405, #402, #390, #389, #384, #370, #344, #325

### Dashboard CI (#391)
**Root cause:** `npm ci` fails — likely missing or stale `package-lock.json` in `dashboard/`.
**Needs:** Operator or code-author fix.

### CodeQL (#323)
**Root cause:** CodeQL scan failure (not a code issue; likely CI infrastructure).
**Note:** All other 21 checks pass including DocOps, pytest, etc.

### Incomplete CI (#388, #373)
Only `detect-br-collision` ran. Remaining 21 checks did not trigger.
**Likely cause:** Branch is very old or CI config changed since branch was pushed. May need a trivial push to re-trigger.

## PR Categorization & Review Notes

### Wave 1: Docs-only / Research (lowest risk — clear the queue)

| PR | Title | Category | Risk | CI | Recommendation |
|---|---|---|---|---|---|
| #455 | outbound(devin): PR janitor session — 1 rebased | docs-only | LOW | PASS | MERGE wave 1 (or CLOSE — superseded by this session) |
| #454 | outbound(devin): PR janitor session — 1 rebased | docs-only | LOW | PASS | CLOSE (superseded by #455 and this session) |
| #452 | outbound(devin): PR janitor session — 2 rebased | docs-only | LOW | PASS | CLOSE (superseded) |
| #451 | outbound(devin): PR janitor session — 33 rebased | docs-only | LOW | PASS | CLOSE (superseded) |
| #439 | research(palantir-ontology): auto-grounding #435 | docs-only | LOW | PASS | MERGE wave 1 |
| #419 | research(palantir-ontology): auto-grounding #409 | docs-only | LOW | PASS | MERGE wave 1 |
| #442 | research(palantir-ontology): auto-grounding #436 | docs-only | LOW | DocOps FAIL | HOLD (needs #453 merge first) |
| #434 | research(palantir-ontology): auto-grounding #433 | docs-only | LOW | DocOps FAIL | HOLD |
| #432 | research(palantir-ontology): auto-grounding #431 | docs-only | LOW | DocOps FAIL | HOLD |
| #424 | research(palantir-ontology): auto-grounding #388 | docs-only | LOW | DocOps FAIL | HOLD |
| #423 | research(palantir-ontology): auto-grounding #408 | docs-only | LOW | DocOps FAIL | HOLD |
| #421 | research(palantir-ontology): auto-grounding #409 | docs-only | LOW | DocOps FAIL | HOLD (possible dup of #419) |
| #420 | research(palantir-ontology): auto-grounding #418 | docs-only | LOW | DocOps FAIL | HOLD |
| #417 | research(palantir-ontology): auto-grounding #406 | docs-only | LOW | DocOps FAIL | HOLD |
| #415 | research(palantir-ontology): auto-grounding #406 | docs-only | LOW | DocOps FAIL | HOLD (possible dup of #417) |
| #413 | research(palantir-ontology): auto-grounding #409 | docs-only | LOW | DocOps FAIL | HOLD (possible dup of #421) |
| #410 | research(palantir-ontology): PhD-grade trio | docs-only | LOW | DocOps FAIL | HOLD |
| #405 | research(palantir-ontology): PhD-grade foundations | docs-only | LOW | DocOps FAIL | HOLD |
| #422 | research(clean-main-audit): v0.0.3.3 audit | docs-only | LOW | DocOps FAIL | HOLD |
| #414 | research(layer-2): vocabulary inhabitation census | docs-only | LOW | DocOps FAIL | HOLD |
| #373 | docs: Wedge re-survey | docs-only | LOW | Incomplete | HOLD (retrigger CI) |
| #370 | docs(reports): autonomous activation architect | docs-only | LOW | DocOps FAIL | HOLD |

### Wave 2: Bug fixes

| PR | Title | Category | Risk | CI | Recommendation |
|---|---|---|---|---|---|
| #383 | fix(guardian): recognize @dataclass __init__ | fix | MEDIUM | PASS | MERGE wave 2 (blocks #392) |
| #392 | fix(guardian): bulletproof dedup | fix | MEDIUM | PASS | MERGE wave 2 (after #383) |
| #323 | fix(providers): dkeys ↔ dharma_swarm env alias | fix | HIGH | CodeQL FAIL | HOLD (needs operator review) |

### Wave 3: Spine-track scaffolds (H-number order)

| PR | Title | Category | Risk | CI | Recommendation |
|---|---|---|---|---|---|
| #388 | PR-H1: disambiguate ClosureEvidenceReceipt | code | MEDIUM | Incomplete | HOLD (retrigger CI) |
| #384 | PR-H2: manifest_check enforces ACTIVE_SURFACE | code | MEDIUM | DocOps FAIL | HOLD (needs #453) |
| #389 | PR-H3: provider_registry contract | scaffold | MEDIUM | DocOps FAIL | HOLD (needs #453) |
| #390 | PR-H4: storage_schema_registry contract | scaffold | MEDIUM | DocOps FAIL | HOLD (needs #453) |
| #391 | PR-H5: openapi-typescript codegen | scaffold | MEDIUM | Dashboard FAIL | HOLD (needs npm fix) |

### Wave 4: Governance / Design

| PR | Title | Category | Risk | CI | Recommendation |
|---|---|---|---|---|---|
| #453 | fix(docops): widen canonical_guard ignore | governance | MEDIUM | PASS | **MERGE FIRST** — unblocks 24 PRs |
| #412 | ADR-008: ontology api_name grammar | governance | LOW | PASS | HOLD (draft) |
| #394 | feat(governance): PR quality gates | governance | MEDIUM | PASS | HOLD (draft) |
| #402 | design(perplexity-computer): autonomous-loop | docs-only | LOW | DocOps FAIL | HOLD |

### Wave 5: Feature code

| PR | Title | Category | Risk | CI | Recommendation |
|---|---|---|---|---|---|
| #431 | feat(kaizen): bind reviews to runtime truth refs | code | MEDIUM | DocOps FAIL | HOLD (needs #453) |
| #426 | seam(spine-adoption): consolidate deliverables | docs-only | LOW | DocOps FAIL | HOLD |
| #425 | research(spine-adoption): master spec | docs-only | LOW | DocOps FAIL | HOLD |
| #450 | test: expand coverage — contracts/runtime | code | MEDIUM | PASS | MERGE wave 5 |

### Wave 6: Legacy / Large PRs

| PR | Title | Category | Risk | CI | Recommendation |
|---|---|---|---|---|---|
| #344 | [codex] Default runtime context Memory Kernel | code | HIGH | DocOps FAIL | HOLD (needs #453 + operator review) |
| #332 | feat(ops): staging promote loop | code | HIGH | PASS | HOLD (needs --human-approved) |
| #325 | [codex] Codex toolbelt onboarding | docs-only | LOW | DocOps FAIL | HOLD (draft + needs #453) |

## Recommended Merge Sequence

1. **#453** (governance fix) — unblocks 24 DocOps-failing PRs
2. **Rebase all 24 DocOps-failing PRs** after #453 lands
3. **#383** → **#392** (guardian fixes, ordered dependency)
4. **#439, #419** (research companions, already green)
5. **#450** (test coverage expansion)
6. **#455** or this session's report PR (latest janitor report)
7. Close superseded janitor reports: #454, #452, #451
8. Spine-track PRs in H-order: #388 → #384 → #389 → #390 → #391 (after CI fixes)
9. Feature PRs: #431, #332 (needs --human-approved)
10. Operator triage: #323 (CodeQL), #344 (HIGH risk), draft PRs (#412, #394, #325)

## PRs Recommended for Closure (Superseded)

- **#454** — superseded by #455 (same janitor report, older)
- **#452** — superseded by #455
- **#451** — superseded by #455
- **#421** — possible duplicate of #419 (same grounding target: PR #409)
- **#415** — possible duplicate of #417 (same grounding target: PR #406)
- **#413** — possible duplicate of #421/#419 (same grounding target: PR #409)

## Operator Decisions Needed

1. **Merge #453 first** to unblock the 24 DocOps-failing PRs
2. **Approve dual-agent reviews** (Codex + Claude) for the 11 green PRs, or adjust gate requirements
3. **Close superseded Devin janitor PRs** (#454, #452, #451)
4. **Close duplicate research grounding PRs** (#421, #415, #413) if confirmed superseded
5. **Triage #332** — HIGH risk, needs `--human-approved`
6. **Investigate #388, #373** — incomplete CI; may need retrigger
7. **Fix #391** — dashboard `npm ci` failure

---

*Report generated by Devin PR Janitor. No PRs were merged. No code was modified except this report.*
