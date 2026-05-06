# Merge Control Report — 2026-05-06

## Snapshot
- Worktree: `feat/operating-spine-v2` on `origin/main` @ `4a1cc14`
- Baseline tests (pre-edit): `25 passed` (`test_daily_operating_brief`, `test_human_yds_ledger`, `test_llm_burn`)
- PR source: GitHub live pull list + per-PR pages (used because local `gh` auth is expired)

## Next Merge Candidate
- `none` from the prior queue block (`#137`, `#136`, `#135`, `#138` are already merged into `main`).

## Blocked / Unstable PRs
- `#131` (structural coherence): `mergeable: unstable`, hot runtime touch surface.
- `#117` (module consolidation): `mergeable: unstable`, 59 files / large structural blast radius.

## Stale / Branch-Specific PRs
- `#58`: very large long-lived branch (73 commits, 144 files), high drift from current `main`.
- `#59`: draft, dirty mergeability, very large scope.
- `#99`: targets `chore/phase2-governance-isolation` (not `main`) and depends on branch-local ontology state.

## Risky Hot-Runtime PRs
- `#131` (runtime/task board/state path wiring)
- `#117` (cross-cutting consolidation around cli/orchestrator/routing/ginko)
- `#104` (provenance + API + runtime wiring; useful but not spine-first)

## Recommended Merge Order (revalidated against current reality)
1. Promote AgentOps v0 as a narrow PR.
2. Add KaizenReview bridge (AgentOps report -> Kaizen review artifacts).
3. Verify/patch `daily_operating_brief` ingestion tests for AgentOps/Kaizen/YDS/DocOps.
4. Keep broader queue (`#104/#116/#118/#120/#117/#131`) behind evidence spine completion.
5. Treat `#58/#59/#99` as non-direct merge candidates requiring dedicated rebase/re-scope.

## Next Action (single)
- Start Phase 2 now: promote AgentOps v0 files (`AGENTOPS.md`, `run_agent_work_packet.py`, `test_agent_work_packet.py`) into `main` lineage and run focused validation.
