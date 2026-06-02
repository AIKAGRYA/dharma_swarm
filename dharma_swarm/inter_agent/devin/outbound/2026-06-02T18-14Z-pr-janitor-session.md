# PR Janitor Session Report

- **Date**: 2026-06-02T18:14Z
- **Session**: https://app.devin.ai/sessions/68e7fc87ce884aeca9891183576c762a
- **Agent**: devin (PR Janitor)
- **Authority**: external_worker_evidence_only (no merge authority)

## Queue Summary

| Metric | Value |
|--------|-------|
| Total open PRs | 43 |
| MERGEABLE | 43/43 (100%) |
| CONFLICTING | 0 |
| CI GREEN (all checks pass) | 20 |
| CI FAILING — DocOps integrity gate | 22 |
| CI FAILING — dashboard | 1 (#391) |
| CI FAILING — CodeQL | 1 (#323, non-required) |
| Draft PRs | 3 (#412, #394, #325) |

## DocOps Failure Root Cause

All 22 DocOps failures share the same root cause: branches add research/report/inter_agent docs that contain authority terms (e.g., "canonical", "source of truth") but aren't registered in `CANONICAL_DOC_STACK.md`. These are descriptive uses, not authority claims.

**Blocker**: PR #453 (`fix(docops): widen canonical_guard ignore`) is GREEN and MERGEABLE. It adds ignore patterns for `docs/research/**`, `docs/reports/**`, `reports/**`, `seams/**`, `dharma_swarm/inter_agent/**`, `inter_agent/**`, `docs/ops/**`. Once #453 merges, all 22 PRs will pass DocOps after rebase.

**Recommendation**: Merge #453 as Wave 0 to unblock 22 PRs.

## NATS Coordination

- Connected to `wss://157.245.193.15:8443` as `devin`
- Announced presence on `dharma.a2a.fleet`
- JetStream subscribe failed (permissions violation for `$js.api.stream.names`) — devin user lacks JetStream admin. Core pub/sub works.
- No inbound messages drained (JetStream inaccessible)
- Status report sent to `dharma.a2a.merge_master_mike`

## Inbound Messages (filesystem)

- `inter_agent/devin/inbound/2026-05-25_codex_request_verify_11_step_chain.md` — already processed (response exists in outbound from 2026-05-25)

## CI Status by PR

### GREEN (20 PRs — ready for operator review)

| PR | Title | Category | Risk |
|----|-------|----------|------|
| #383 | fix(guardian): recognize @dataclass __init__ | code-fix | LOW |
| #388 | PR-H1: disambiguate ClosureEvidenceReceipt | code-scaffold | MEDIUM |
| #392 | fix(guardian): bulletproof dedup | code-fix | MEDIUM |
| #394 | feat(governance): PR quality gates (DRAFT) | governance | MEDIUM |
| #412 | ADR-008: ontology api_name grammar (DRAFT) | governance | LOW |
| #419 | research(palantir-ontology): grounding PR#409 | docs-only | LOW |
| #431 | feat(kaizen): bind reviews to runtime truth refs | code | MEDIUM |
| #439 | research(palantir-ontology): grounding PR #435 | docs-only | LOW |
| #332 | feat(ops): staging promote loop + Hermes | code | MEDIUM |
| #344 | [codex] Default runtime context through Memory Kernel | code | HIGH |
| #450 | test: expand coverage | code | MEDIUM |
| #451 | outbound(devin): PR janitor session — 33 rebased | docs-only | LOW |
| #452 | outbound(devin): PR janitor session — 2 rebased | docs-only | LOW |
| #453 | fix(docops): widen canonical_guard ignore | governance | LOW |
| #454 | outbound(devin): PR janitor session — 1 rebased | docs-only | LOW |
| #455 | outbound(devin): PR janitor session — 1 rebased | docs-only | LOW |
| #456 | outbound(devin): PR janitor session — 0 rebased | docs-only | LOW |
| #457 | outbound(devin): PR janitor session — 5 DocOps fixed | docs-only | LOW |
| #458 | outbound(devin): PR janitor session — 1 rebased | docs-only | LOW |
| #373 | docs: Wedge re-survey (partial CI) | docs-only | LOW |

### FAILING DocOps (22 PRs — blocked on #453 merge)

| PR | Title | Category |
|----|-------|----------|
| #384 | PR-H2: manifest_check enforces ACTIVE_SURFACE_MANIFEST | code-scaffold |
| #389 | PR-H3: provider_registry contract | code-scaffold |
| #390 | PR-H4: storage_schema_registry contract | code-scaffold |
| #391 | PR-H5: openapi-typescript codegen (also fails dashboard) | code-scaffold |
| #402 | design(perplexity-computer): autonomous-loop addendum | docs-only |
| #405 | research(palantir-ontology): PhD-grade foundations | docs-only |
| #410 | research(palantir-ontology): PhD-grade trio + exec brief | docs-only |
| #413 | research(palantir-ontology): grounding PR#409 | docs-only |
| #414 | research(layer-2): vocabulary inhabitation census | docs-only |
| #415 | research(palantir-ontology): grounding PR#406 | docs-only |
| #417 | research(palantir-ontology): grounding PR#406 | docs-only |
| #420 | research(palantir-ontology): grounding PR#418 andon | docs-only |
| #421 | research(palantir-ontology): grounding PR#409 | docs-only |
| #422 | research(clean-main-audit): v0.0.3.3 audit | docs-only |
| #423 | research(palantir-ontology): grounding PR#408 | docs-only |
| #424 | research(palantir-ontology): grounding PR#388 | docs-only |
| #425 | research(spine-adoption): master spec | docs-only |
| #426 | seam(spine-adoption): consolidate deliverables | docs-only |
| #432 | research(palantir-ontology): grounding PR#431 | docs-only |
| #434 | research(palantir-ontology): grounding PR#433 | docs-only |
| #442 | research(palantir-ontology): grounding PR#436 | docs-only |
| #325 | [codex] publish Codex toolbelt onboarding (DRAFT) | docs-only |
| #370 | docs(reports): autonomous activation architect | docs-only |

### Other CI Failures

- **#323** fix(providers): dkeys env alias — CodeQL failure (non-required check)
- **#391** PR-H5: openapi-typescript codegen — dashboard CI failure

## Merge Sequence Recommendation

### Wave 0 — Unblock (merge first)
- **#453** fix(docops): widen canonical_guard ignore ← unblocks 22 PRs

### Wave 1 — Docs-only (lowest risk, after #453)
- #373, #402, #405, #410, #413, #414, #415, #417, #419, #420, #421, #422, #423, #424, #425, #432, #434, #439, #442

### Wave 2 — Bug fixes
- **#383** fix(guardian): recognize @dataclass __init__
- **#392** fix(guardian): bulletproof dedup (depends on #383)

### Wave 3 — Spine-track scaffolds (H-number order)
- **#388** PR-H1: disambiguate ClosureEvidenceReceipt
- **#384** PR-H2: manifest_check (after #453 for DocOps)
- **#389** PR-H3: provider_registry (after #453)
- **#390** PR-H4: storage_schema_registry (after #453)
- **#391** PR-H5: openapi-typescript codegen (needs dashboard fix + #453)

### Wave 4 — Governance
- #394 feat(governance): PR quality gates (DRAFT)
- #412 ADR-008: ontology api_name grammar (DRAFT)
- #426 seam(spine-adoption) (after #453)

### Wave 5 — Feature code
- #431 feat(kaizen): bind reviews to runtime truth refs
- #332 feat(ops): staging promote loop
- #344 [codex] Default runtime context through Memory Kernel
- #450 test: expand coverage

### Wave 6 — Legacy/assessment needed
- #323 fix(providers): dkeys env alias (CodeQL failure)
- #325 [codex] Codex toolbelt onboarding (DRAFT, DocOps)
- #370 docs(reports): autonomous activation architect

### Superseded PR Candidates (recommend close)

Previous janitor session PRs that are superseded by newer runs:
- #451, #452, #454, #455, #456, #457, #458 — all outbound session reports from earlier today. The latest (#458) supersedes the rest. Consider closing #451-#457 to reduce queue noise.

## Rebases Performed

None needed — all 43 PRs are MERGEABLE (0 CONFLICTING).

## Operator Decisions Needed

1. **Merge #453** to unblock 22 DocOps-failing PRs
2. **Close superseded janitor PRs** (#451-#457) to reduce queue from 43 to 36
3. **Dashboard CI fix for #391** — needs investigation (openapi-typescript codegen)
4. **#323 CodeQL failure** — assess whether to fix or close
5. **Draft PRs** (#412, #394, #325) — operator review needed to determine readiness

## Session Actions Taken

1. `git pull origin main` — already up to date
2. `make onboard` — all completion criteria pass
3. NATS connected, presence announced on `dharma.a2a.fleet`
4. JetStream drain attempted — permissions restricted, no messages available
5. Filesystem inbound checked — 1 message (already processed)
6. Full CI survey of all 43 PRs completed
7. DocOps root cause identified: #453 merge unblocks 22 PRs
8. Merge sequence recommendation produced
9. Report sent to Mike on `dharma.a2a.merge_master_mike`
10. Final status published to `dharma.a2a.fleet`
