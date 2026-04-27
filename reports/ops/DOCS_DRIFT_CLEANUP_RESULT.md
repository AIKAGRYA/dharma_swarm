# Docs Drift Cleanup Result

Date: 2026-04-27
Branch: `docs/canonical-drift-cleanup`
Base: `origin/main` at `834b8c20694b05bcbc95f3d781e5cce45c4fea0e`

## Scope

Docs/report cleanup only. No runtime, dashboard, test, or workflow code
was edited.

## Changes

- Added `reports/ops/REPO_STATE_NOW.md` as the current post-PR #28 /
  PR #35 / PR #41 operating-state pointer for agents.
- Updated `CYBERNETIC_LOOP_MAP.md` so Loop 1 no longer claims it dies
  on the old `huggingface_hub` blocker. It now marks Loop 1 as
  PR #28 test-proven partial closure and explicitly withholds live
  daemon closure claims.
- Updated `MODEL_ROUTING_MAP.md` as a routing drift register. It now
  labels the HuggingFace blocker historical/resolved, points routing
  canon to `docs/architecture/MODEL_ROUTING_CANON.md`, and clarifies
  that `AgentConfig` / `AgentState` are current code truth while a
  unified `AgentIdentity` migration is aspirational.
- Updated `INTERFACE_MISMATCH_MAP.md` to remove the stale
  Guardian-auto-update claim and add a docs drift register entry.
- Moved `LIVING_LAYERS.md` to `docs/archive/LIVING_LAYERS.md` and
  marked it historical.
- Updated `docs/archive/README.md` to list the archived living-layers
  document.
- Cleaned `docs/architecture/NAVIGATION.md` frontmatter and added
  current-state pointers. Its counts/line numbers are now labelled as
  approximate navigation aids, not acceptance criteria.
- Updated `docs/governance/CANONICAL_DOC_STACK.md` to point Tier 4
  operators to `reports/ops/REPO_STATE_NOW.md` and to mark
  `LIVING_LAYERS.md` as archived.

## Guardrails

- Did not edit code.
- Did not claim implementation without tests.
- Did not add root-doc sprawl.
- Did not promote stale runtime/dashboard/model surfaces.
- Did not change CI, workflows, or pre-commit behavior.

## Remaining Drift

- `README.md` and `CLAUDE.md` still mention root routing/loop maps, but
  they were outside this task's scoped file list.
- `docs/governance/REPO_GOVERNANCE_AUDIT.md` still has historical
  entries about `LIVING_LAYERS.md`; that audit file was outside this
  scoped cleanup.
- Additional docs-drift automation is still needed for frontmatter,
  duplicate docs, stale numeric claims, and mismatch-map citations.

## Verification

- Manual scoped grep confirmed the old Loop 1 / `MM-01` active-blocker
  claim was removed from the updated maps.
- Git diff was reviewed for file scope before commit.
- Runtime tests were not run because this PR changes docs and reports
  only.
