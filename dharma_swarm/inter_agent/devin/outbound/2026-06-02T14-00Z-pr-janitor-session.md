# PR Janitor Session Report — 2026-06-02 14:00 UTC

**Agent:** devin-6f7af181ec794c09a4aade43d221b93e
**Session:** https://app.devin.ai/sessions/6f7af181ec794c09a4aade43d221b93e
**Authority:** external_worker_evidence_only (Stage 1)

## Queue Summary

| Metric | Before | After |
|---|---|---|
| Total open PRs | 35 | 36 (1 new: #450) |
| MERGEABLE | 2 | 34 |
| CONFLICTING | 33 | 2 (stale GitHub cache) |
| DocOps gate failing | ~30 | 0 (27 fixed this session) |

## Actions Taken

### 1. Rebased 33 CONFLICTING PRs → all now MERGEABLE

All conflicts were in auto-generated DocOps count files (`AUTO_INVENTORY.md`, `SOVEREIGN_MANIFEST.md`). Zero real code conflicts. Resolution: keep main's version during rebase (`git checkout --ours`).

### 2. Fixed DocOps integrity on 27 PR branches

After rebase, the SOVEREIGN_MANIFEST counts were stale (main's counts didn't account for files added by each PR). For each branch:
1. Ran `scripts/docops/check_docops_integrity.py --write-auto-sections`
2. Extracted script's metric output (markdown_files, markdown_total_lines, etc.)
3. Updated SOVEREIGN_MANIFEST.md with correct counts
4. Committed with all pre-commit hooks passing

PRs fixed: #442, #439, #434, #432, #426, #425, #424, #423, #422, #421, #420, #419, #417, #415, #414, #413, #412, #410, #405, #402, #394, #392, #391, #383, #373, #370, #325

### 3. NATS coordination

- Connected to NATS bus (wss://157.245.193.15:8443, user=devin)
- Published `session_start` to `dharma.a2a.fleet`
- Published progress update to `dharma.a2a.fleet`
- Published full report to `dharma.a2a.merge_master_mike`
- JetStream not available (devin user lacks `$js.api` permissions) — used core NATS pub/sub
- 0 inbound messages drained (no pending messages on `dharma.a2a.devin`)

### 4. Identified 6 code PRs needing manifest_check fix

PRs #431, #390, #389, #388, #384, #344 fail the `dharma manifest check` pre-commit hook. These PRs add new modules/files not registered in `ACTIVE_SURFACE_MANIFEST.yaml`. This is author/operator scope, not janitor.

## PR Categories

### Wave 1 — Docs/Research (19 PRs, all MERGEABLE + DocOps passing)
Lowest risk, clear the queue first.

| PR | Title |
|---|---|
| #442 | research(palantir-ontology): auto-grounding for PR #436 |
| #439 | research(palantir-ontology): auto-grounding for PR #435 |
| #434 | research(palantir-ontology): auto-grounding for PR #433 |
| #425 | research(spine-adoption): master spec + codex 5.5 plan |
| #424 | research(palantir-ontology): auto-grounding for PR #388 |
| #423 | research(palantir-ontology): auto-grounding for PR #408 |
| #422 | research(clean-main-audit): v0.0.3.3 audit on d5ebc456 |
| #421 | research(palantir-ontology): auto-grounding for PR #409 |
| #420 | research(palantir-ontology): auto-grounding for PR #418 |
| #419 | research(palantir-ontology): auto-grounding for PR#409 |
| #417 | research(palantir-ontology): auto-grounding for PR#406 |
| #415 | research(palantir-ontology): auto-grounding for PR#406 |
| #414 | research(layer-2): vocabulary inhabitation census |
| #413 | research(palantir-ontology): auto-grounding for PR#409 |
| #410 | research(palantir-ontology): PhD-grade trio grounding |
| #405 | research(palantir-ontology): PhD-grade foundations grounding |
| #373 | docs: Wedge re-survey — 30-day TTFD |
| #370 | docs(reports): autonomous activation architect |
| #426 | seam(spine-adoption): consolidate deliverables |

### Wave 2 — Guardian Fixes (2 PRs)
| PR | Title |
|---|---|
| #383 | fix(guardian): recognize @dataclass-synthesized __init__ |
| #392 | fix(guardian): bulletproof dedup |

### Wave 3 — Spine Scaffolds (5 PRs, H-number order)
Need manifest_check fix first.
| PR | Title |
|---|---|
| #388 | PR-H1: disambiguate ClosureEvidenceReceipt |
| #384 | PR-H2: manifest_check enforces ACTIVE_SURFACE_MANIFEST |
| #389 | PR-H3: provider_registry contract |
| #390 | PR-H4: storage_schema_registry contract |
| #391 | PR-H5: openapi-typescript codegen pipeline |

### Wave 4 — Governance/Design (3 PRs)
| PR | Title |
|---|---|
| #394 | feat(governance): PR quality gates (DRAFT) |
| #402 | design(perplexity-computer): autonomous-loop addendum |
| #412 | ADR-008: ontology api_name grammar (DRAFT) |

### Wave 5 — Feature Code (4 PRs)
| PR | Title |
|---|---|
| #431 | feat(kaizen): bind reviews to runtime truth refs |
| #432 | research(palantir-ontology): auto-grounding for PR #431 |
| #332 | feat(ops): staging promote loop + Hermes heartbeat |
| #323 | fix(providers): dkeys env alias normalization |

### Wave 6 — Legacy/Assessment (2 PRs)
| PR | Title |
|---|---|
| #344 | [codex] Default runtime context through Memory Kernel |
| #325 | [codex] publish Codex toolbelt onboarding (DRAFT) |

## Potential Duplicates

- **#415 vs #417**: Both ground PR#406 — check if one supersedes the other
- **#419 vs #421**: Both ground PR#409 — similar concern
- **#413**: Also grounds PR#409 — triple duplicate?

## Operator Actions Needed

1. **Merge Wave 1** (19 docs PRs): all MERGEABLE, DocOps passing, zero code risk
2. **Fix manifest_check** on 6 code PRs (#431, #390, #389, #388, #384, #344)
3. **Assess duplicates** (#415/#417, #419/#421/#413)
4. **Re-trigger CI** on #323 (CodeQL transient failure — all 21 other checks pass)
5. **Assess #344** (Memory Kernel): CI module-budget pressure, may need decomposition
6. **JetStream permissions**: devin user needs `$js.api.stream.names` publish permission for durable subscription

## Systemic Finding (unchanged from previous session)

100% of merge conflicts originated in auto-generated DocOps count files. No actual code conflicts existed. Post-merge DocOps regeneration would eliminate this pattern.
